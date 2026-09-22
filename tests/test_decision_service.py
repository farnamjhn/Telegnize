import unittest
from datetime import datetime

from application.decision_questions import CONVERSATION_QUESTIONS, MESSAGE_QUESTIONS
from application.ports.decision_engine import DecisionQuestion
from application.services.decision_service import (
    DecisionService,
    questions_from_payload,
)
from domain.errors import ChatNotFoundError, MessageNotFoundError
from domain.models.analysis import DecisionTarget, DecisionType
from domain.models.message import Message
from tests.conftest import memory_container
from tests.fakes import FakeDecisionEngine


class TestDecisionService(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.engine = FakeDecisionEngine()
        self.messages = self.container.message_repository
        self.service = DecisionService(
            message_repo=self.messages,
            decision_repo=self.container.decision_repository,
            engine=self.engine,
        )

    def tearDown(self):
        self.container.close()

    def given_message(self, text="I really appreciate your help!") -> int:
        self.messages.save(
            Message(
                id=0,
                telegram_msg_id=101,
                sender_id="u1",
                sender_name="Alice",
                timestamp=datetime(2026, 5, 27, 10, 0, 0),
                text=text,
            )
        )
        return self.messages.get_by_telegram_id(101).id

    def test_evaluating_a_message_answers_the_default_question_set(self):
        message_id = self.given_message()
        decisions = self.service.evaluate_message(message_id)

        self.assertEqual(
            {d.question_key for d in decisions},
            {q.key for q in MESSAGE_QUESTIONS},
        )
        tone = next(d for d in decisions if d.question_key == "tone")
        self.assertIs(tone.target_type, DecisionTarget.MESSAGE)
        self.assertEqual(tone.target_id, message_id)
        self.assertIs(tone.decision_type, DecisionType.CHOICE)

    def test_the_engine_sees_the_normalized_text(self):
        self.service.evaluate_message(self.given_message("Hello   THERE"))
        state, _ = self.engine.calls[0]
        self.assertEqual(state["text"], "Hello   THERE")
        self.assertEqual(state["sender"], "Alice")

    def test_decisions_are_cached_and_readable_afterwards(self):
        message_id = self.given_message()
        self.service.evaluate_message(message_id)

        cached = self.service.get_cached(DecisionTarget.MESSAGE, message_id)
        self.assertEqual(
            {d.question_key for d in cached}, {q.key for q in MESSAGE_QUESTIONS}
        )

    def test_re_evaluating_replaces_rather_than_accumulates(self):
        message_id = self.given_message()
        self.service.evaluate_message(message_id)
        self.service.evaluate_message(message_id)
        self.assertEqual(
            len(self.service.get_cached(DecisionTarget.MESSAGE, message_id)),
            len(MESSAGE_QUESTIONS),
        )

    def test_noul_answers_stay_boolean_through_the_cache(self):
        message_id = self.given_message()
        self.service.evaluate_message(message_id)
        cached = {
            d.question_key: d.result_value
            for d in self.service.get_cached(DecisionTarget.MESSAGE, message_id)
        }
        self.assertIs(cached["is_conflict"], True)

    def test_a_custom_question_set_overrides_the_default(self):
        questions = [
            DecisionQuestion(
                key="urgency",
                decision_type=DecisionType.NOUL,
                instructions="Is this urgent?",
            )
        ]
        decisions = self.service.evaluate_message(
            self.given_message(), questions=questions
        )
        self.assertEqual([d.question_key for d in decisions], ["urgency"])

    def test_an_unknown_message_raises(self):
        with self.assertRaises(MessageNotFoundError):
            self.service.evaluate_message(9999)

    def test_chat_window_builds_a_dialogue_transcript(self):
        self.given_message("First")
        self.messages.save(
            Message(
                id=0,
                telegram_msg_id=102,
                sender_id="u2",
                sender_name="Bob",
                timestamp=datetime(2026, 5, 27, 10, 1, 0),
                text="Second",
            )
        )
        decisions = self.service.evaluate_chat_window(1)

        state, questions = self.engine.calls[0]
        self.assertEqual(state["dialogue"], "Alice: First\nBob: Second")
        self.assertEqual(state["turns_count"], 2)
        self.assertEqual(
            [q.key for q in questions], [q.key for q in CONVERSATION_QUESTIONS]
        )
        self.assertTrue(all(d.target_type is DecisionTarget.CHAT for d in decisions))

    def test_a_chat_with_nothing_to_read_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service.evaluate_chat_window(1)

    def test_custom_evaluation_is_not_cached(self):
        questions = [
            DecisionQuestion(
                key="sentiment",
                decision_type=DecisionType.CHOICE,
                instructions="What is the sentiment?",
                criteria={"positive": "praise", "negative": "complaint"},
            )
        ]
        result = self.service.evaluate_custom("Thank you!", questions)
        self.assertIn("sentiment", result["answers"])
        self.assertEqual(self.service.get_cached(DecisionTarget.CHAT, 1), [])


class TestQuestionsFromPayload(unittest.TestCase):
    def test_none_means_use_the_default_set(self):
        self.assertIsNone(questions_from_payload(None))
        self.assertIsNone(questions_from_payload({}))

    def test_a_payload_becomes_typed_questions(self):
        questions = questions_from_payload(
            {
                "sentiment": {
                    "type": "choice",
                    "instructions": "What is the sentiment?",
                    "criteria": {"positive": "praise", "negative": "complaint"},
                }
            }
        )
        self.assertEqual(len(questions), 1)
        self.assertIs(questions[0].decision_type, DecisionType.CHOICE)
        self.assertEqual(questions[0].key, "sentiment")

    def test_a_choice_question_needs_alternatives(self):
        with self.assertRaises(ValueError):
            questions_from_payload(
                {"tone": {"type": "choice", "instructions": "?", "criteria": {"a": "x"}}}
            )


if __name__ == "__main__":
    unittest.main()
