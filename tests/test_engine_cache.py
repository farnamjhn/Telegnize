"""Tests for the answer cache in front of the decision engine.

All of these run against the fake engine: what is being tested is how often the
engine is asked, not what it says.
"""

import unittest
from datetime import datetime, timedelta

from application.decision_questions import ASSESSMENT_QUESTIONS, MESSAGE_QUESTIONS
from application.ports.decision_engine import DecisionQuestion
from application.services.assessment_service import AssessmentService
from domain.models.analysis import DecisionType
from domain.models.chat import Chat
from domain.models.message import Message
from infrastructure.decision_engine.caching_engine import CachingDecisionEngine
from tests.conftest import memory_container
from tests.fakes import FakeDecisionEngine

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)

TONE = DecisionQuestion(
    key="tone",
    decision_type=DecisionType.CHOICE,
    instructions="What is the emotional tone of this message?",
    criteria={"warm": "warm", "cold": "cold"},
)


class TestAnswerCache(unittest.TestCase):
    def setUp(self):
        self.inner = FakeDecisionEngine()
        self.engine = CachingDecisionEngine(self.inner)

    def test_the_same_state_is_only_put_to_the_engine_once(self):
        state = {"sender": "Alice", "text": "😭😭"}
        first = self.engine.predict(state, [TONE])
        second = self.engine.predict(state, [TONE])

        self.assertEqual(len(self.inner.calls), 1)
        self.assertEqual(second.answers["tone"].value, first.answers["tone"].value)
        self.assertEqual((self.engine.hits, self.engine.misses), (1, 1))

    def test_an_equal_state_hits_even_as_a_different_object(self):
        self.engine.predict({"sender": "Alice", "text": "ok"}, [TONE])
        self.engine.predict({"text": "ok", "sender": "Alice"}, [TONE])
        self.assertEqual(len(self.inner.calls), 1)

    def test_a_different_state_is_a_different_question(self):
        self.engine.predict({"text": "ok"}, [TONE])
        self.engine.predict({"text": "not ok"}, [TONE])
        self.assertEqual(len(self.inner.calls), 2)

    def test_changing_the_questions_is_not_answered_from_the_cache(self):
        self.engine.predict("hello", MESSAGE_QUESTIONS)
        self.engine.predict("hello", ASSESSMENT_QUESTIONS)
        self.assertEqual(len(self.inner.calls), 2)

    def test_changing_a_question_in_place_is_not_answered_from_the_cache(self):
        self.engine.predict("hello", [TONE])
        reworded = DecisionQuestion(
            key=TONE.key,
            decision_type=TONE.decision_type,
            instructions="How warm is this message?",
            criteria=TONE.criteria,
        )
        self.engine.predict("hello", [reworded])
        self.assertEqual(len(self.inner.calls), 2)

    def test_the_least_recently_used_answer_is_evicted_first(self):
        engine = CachingDecisionEngine(self.inner, max_entries=2)
        for text in ("one", "two"):
            engine.predict(text, [TONE])
        engine.predict("one", [TONE])   # keeps "one", so "two" is oldest
        engine.predict("three", [TONE])  # evicts "two"

        engine.predict("one", [TONE])
        self.assertEqual(len(self.inner.calls), 3)
        engine.predict("two", [TONE])
        self.assertEqual(len(self.inner.calls), 4)

    def test_a_caller_editing_its_result_does_not_edit_the_cache(self):
        first = self.engine.predict("hello", [TONE])
        first.metadata["checkpoint"] = "edited"
        first.answers.clear()

        second = self.engine.predict("hello", [TONE])
        self.assertEqual(second.metadata["checkpoint"], "fake-checkpoint")
        self.assertIn("tone", second.answers)

    def test_a_state_that_does_not_serialise_is_answered_uncached(self):
        circular: dict = {"text": "hello"}
        circular["self"] = circular

        self.engine.predict(circular, [TONE])
        self.engine.predict(circular, [TONE])
        self.assertEqual(len(self.inner.calls), 2)

    def test_it_reports_the_engine_behind_it_and_its_own_hit_rate(self):
        self.engine.predict("hello", [TONE])
        self.engine.predict("hello", [TONE])

        described = self.engine.describe()
        self.assertEqual(described["engine"], "fake")
        self.assertIn("1 hits, 1 misses", described["answer_cache"])
        self.assertTrue(self.engine.is_ready)


class TestAssessmentWithTheCache(unittest.TestCase):
    """The case the cache exists for: a chat that repeats itself."""

    def setUp(self):
        self.container = memory_container()
        self.inner = FakeDecisionEngine()
        self.chat = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=99, name="Repetitive Chat")
        )

    def tearDown(self):
        self.container.close()

    def given_messages(self, *texts_by_sender):
        self.container.message_repository.save_batch(
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

    def service(self, engine) -> AssessmentService:
        return AssessmentService(
            chat_repo=self.container.chat_repository,
            message_repo=self.container.message_repository,
            decision_repo=self.container.decision_repository,
            engine=engine,
            page_size=200,
        )

    def test_a_repeated_message_is_answered_once_and_stored_for_each(self):
        self.given_messages(("u1", "😭😭"), ("u1", "😭😭"), ("u1", "😭😭"))
        service = self.service(CachingDecisionEngine(self.inner))

        progress = service.assess_page(self.chat.id)

        self.assertEqual(progress.assessed_now, 3)
        self.assertEqual(progress.coverage_percent, 100.0)
        # Every message is still answered; only the engine was spared.
        self.assertEqual(len(self.inner.calls), 1)

    def test_the_same_text_from_another_sender_is_asked_again(self):
        self.given_messages(("u1", "ok"), ("u2", "ok"))
        self.service(CachingDecisionEngine(self.inner)).assess_page(self.chat.id)
        # The sender is part of what the engine is shown, so it is a new state.
        states = [state for state, _ in self.inner.calls]
        self.assertIn({"sender": "Alice", "text": "ok"}, states)
        self.assertIn({"sender": "Bob", "text": "ok"}, states)


if __name__ == "__main__":
    unittest.main()
