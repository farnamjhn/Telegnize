import unittest
from datetime import datetime, timedelta

from application.services.assessment_service import AssessmentService
from domain.errors import ChatNotFoundError
from domain.models.analysis import DecisionTarget
from domain.models.chat import Chat
from domain.models.message import Message
from tests.conftest import memory_container
from tests.fakes import FakeDecisionEngine

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)


class AssessmentTestCase(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.messages = self.container.message_repository
        self.decisions = self.container.decision_repository
        self.chat = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=99, name="Assessed Chat")
        )

    def tearDown(self):
        self.container.close()

    def service(self, engine=None, page_size=200) -> AssessmentService:
        self.engine = engine or FakeDecisionEngine()
        return AssessmentService(
            chat_repo=self.container.chat_repository,
            message_repo=self.messages,
            decision_repo=self.decisions,
            engine=self.engine,
            page_size=page_size,
        )

    def given_messages(self, *texts_by_sender):
        self.messages.save_batch(
            [
                Message(
                    id=0,
                    chat_id=self.chat.id,
                    telegram_msg_id=index,
                    sender_id=sender,
                    sender_name={"u1": "Alice", "u2": "Bob"}.get(sender, sender),
                    timestamp=BASE_TIME + timedelta(minutes=index),
                    text=text,
                )
                for index, (sender, text) in enumerate(texts_by_sender, start=1)
            ]
        )


class TestAssessmentPass(AssessmentTestCase):
    def test_a_pass_answers_every_question_about_each_message(self):
        self.given_messages(("u1", "hello there"), ("u2", "hi back"))
        progress = self.service().assess_page(self.chat.id)

        self.assertEqual(progress.assessed_now, 2)
        self.assertTrue(progress.is_complete)
        self.assertEqual(progress.coverage_percent, 100.0)

        first = self.messages.list_messages(chat_id=self.chat.id)[0]
        keys = {
            d.question_key
            for d in self.decisions.list_for_target(DecisionTarget.MESSAGE, first.id)
        }
        self.assertLessEqual(
            {"valence", "is_bid", "friction", "is_repair", "sarcasm", "discourse_act"},
            keys,
        )

    def test_a_second_pass_skips_what_is_already_answered(self):
        self.given_messages(("u1", "hello"), ("u2", "hi"))
        service = self.service()
        service.assess_page(self.chat.id)
        calls_after_first = len(self.engine.calls)

        again = service.assess_page(self.chat.id)
        self.assertEqual(again.assessed_now, 0)
        self.assertEqual(again.skipped_already_done, 2)
        self.assertEqual(len(self.engine.calls), calls_after_first)

    def test_paging_reports_where_to_resume(self):
        self.given_messages(*[("u1", f"message {i}") for i in range(5)])
        service = self.service(page_size=2)

        first = service.assess_page(self.chat.id)
        self.assertEqual(first.assessed_now, 2)
        self.assertEqual(first.next_offset, 2)
        self.assertFalse(first.is_complete)

        second = service.assess_page(self.chat.id, offset=first.next_offset)
        self.assertEqual(second.next_offset, 4)
        self.assertFalse(second.is_complete)

        third = service.assess_page(self.chat.id, offset=second.next_offset)
        self.assertTrue(third.is_complete)
        self.assertEqual(third.coverage_percent, 100.0)

    def test_messages_without_text_are_left_alone(self):
        self.given_messages(("u1", ""), ("u2", "   "))
        progress = self.service().assess_page(self.chat.id)
        self.assertEqual(progress.assessed_now, 0)

    def test_an_unknown_chat_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service().assess_page(9999)


class TestBidLinking(AssessmentTestCase):
    def test_a_bid_is_scored_against_the_reply_that_followed(self):
        self.given_messages(("u1", "look at this photo"), ("u2", "haha love it"))
        service = self.service(
            FakeDecisionEngine(answers={"is_bid": True, "turns_toward": True})
        )
        service.assess_page(self.chat.id)

        bid = self.messages.list_messages(chat_id=self.chat.id)[0]
        cached = {
            d.question_key: d.result_value
            for d in self.decisions.list_for_target(DecisionTarget.MESSAGE, bid.id)
        }
        self.assertIs(cached["bid_met"], True)

    def test_a_message_that_is_not_a_bid_is_not_scored_for_uptake(self):
        self.given_messages(("u1", "ok"), ("u2", "sure"))
        self.service(FakeDecisionEngine(answers={"is_bid": False})).assess_page(
            self.chat.id
        )
        bid = self.messages.list_messages(chat_id=self.chat.id)[0]
        keys = {
            d.question_key
            for d in self.decisions.list_for_target(DecisionTarget.MESSAGE, bid.id)
        }
        self.assertNotIn("bid_met", keys)

    def test_a_bid_nobody_replied_to_is_left_unlinked(self):
        self.given_messages(("u1", "look at this"), ("u1", "still here"))
        self.service(FakeDecisionEngine(answers={"is_bid": True})).assess_page(
            self.chat.id
        )
        for message in self.messages.list_messages(chat_id=self.chat.id):
            keys = {
                d.question_key
                for d in self.decisions.list_for_target(
                    DecisionTarget.MESSAGE, message.id
                )
            }
            self.assertNotIn("bid_met", keys)


class TestAggregation(AssessmentTestCase):
    def test_nothing_assessed_yet_reports_zero_coverage(self):
        self.given_messages(("u1", "hello"))
        assessment = self.service().get_assessment(self.chat.id)
        self.assertEqual(assessment.coverage_percent, 0.0)
        self.assertEqual(assessment.participants, [])
        self.assertEqual(assessment.total_messages, 1)

    def test_valence_counts_and_the_positive_to_negative_ratio(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(3)])
        self.service(FakeDecisionEngine(answers={"valence": "positive"})).assess_page(
            self.chat.id
        )
        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.positive_count, 3)
        self.assertEqual(alice.negative_count, 0)
        # No negatives means no ratio, rather than an infinite one.
        self.assertIsNone(alice.positivity_ratio)

    def test_a_mixed_chat_produces_a_ratio(self):
        self.given_messages(("u1", "lovely"), ("u1", "fine"))
        service = self.service(FakeDecisionEngine(answers={"valence": "positive"}))
        service.assess_page(self.chat.id, limit=1)
        # Second message reads negative.
        self.service(
            FakeDecisionEngine(answers={"valence": "negative"})
        ).assess_page(self.chat.id, offset=1)

        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.positive_count, 1)
        self.assertEqual(alice.negative_count, 1)
        self.assertEqual(alice.positivity_ratio, 1.0)

    def test_friction_and_repair_rates(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(4)])
        self.service(
            FakeDecisionEngine(answers={"friction": "contempt", "is_repair": True})
        ).assess_page(self.chat.id)

        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.contempt_count, 4)
        self.assertEqual(alice.criticism_count, 0)
        self.assertEqual(alice.friction_percent, 100.0)
        self.assertEqual(alice.repair_count, 4)
        self.assertEqual(alice.repair_percent, 100.0)

    def test_friction_labelled_none_is_not_counted_as_friction(self):
        self.given_messages(("u1", "hello"))
        self.service(FakeDecisionEngine(answers={"friction": "none"})).assess_page(
            self.chat.id
        )
        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.friction_percent, 0.0)

    def test_sarcasm_is_averaged_across_the_scale(self):
        self.given_messages(("u1", "sure, great"), ("u1", "wonderful"))
        self.service(FakeDecisionEngine(answers={"sarcasm": 2.0})).assess_page(
            self.chat.id
        )
        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.avg_sarcasm_score, 2.0)

    def test_curiosity_counts_open_questions_per_thousand_words(self):
        self.given_messages(("u1", "one two three four five"))
        self.service(
            FakeDecisionEngine(
                answers={"discourse_act": "open_question_or_vulnerability"}
            )
        ).assess_page(self.chat.id)
        alice = self.service().get_assessment(self.chat.id).participants[0]
        self.assertEqual(alice.open_question_count, 1)
        self.assertEqual(alice.curiosity_per_1k_words, 200.0)

    def test_bid_uptake_rate(self):
        self.given_messages(("u1", "look"), ("u2", "nice"), ("u1", "and this"))
        self.service(
            FakeDecisionEngine(answers={"is_bid": True, "turns_toward": True})
        ).assess_page(self.chat.id)

        assessment = self.service().get_assessment(self.chat.id)
        alice = next(p for p in assessment.participants if p.sender_id == "u1")
        self.assertEqual(alice.bid_count, 2)
        # Only the first of Alice's bids had a reply inside the page to score.
        self.assertEqual(alice.bids_met_count, 1)
        self.assertEqual(alice.bids_met_percent, 100.0)

    def test_coverage_is_reported_against_the_whole_chat(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(4)])
        self.service().assess_page(self.chat.id, limit=2)
        assessment = self.service().get_assessment(self.chat.id)
        self.assertEqual(assessment.assessed_messages, 2)
        self.assertEqual(assessment.total_messages, 4)
        self.assertEqual(assessment.coverage_percent, 50.0)

    def test_an_unknown_chat_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service().get_assessment(9999)


if __name__ == "__main__":
    unittest.main()
