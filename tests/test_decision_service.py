import unittest
from datetime import datetime, timedelta

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

    def given_chat(self, count: int) -> None:
        self.messages.save_batch(
            [
                Message(
                    id=0,
                    telegram_msg_id=1000 + i,
                    sender_id="u1" if i % 2 else "u2",
                    sender_name="Alice" if i % 2 else "Bob",
                    timestamp=datetime(2026, 5, 27, 10, 0, 0) + timedelta(minutes=i),
                    text=f"line {i}",
                )
                for i in range(count)
            ]
        )

    def test_the_recent_window_is_the_newest_messages(self):
        self.given_chat(10)
        self.service.evaluate_chat_window(1, limit=3)
        state, _ = self.engine.calls[0]
        self.assertEqual(
            state["dialogue"], "Alice: line 7\nBob: line 8\nAlice: line 9"
        )

    def test_the_whole_chat_is_read_as_windows_in_one_batch(self):
        self.given_chat(10)
        decisions = self.service.evaluate_whole_chat(1, window_size=4)

        self.assertEqual(len(self.engine.batch_calls), 1)
        windows = self.engine.batch_calls[0][0]
        self.assertEqual([w["turns_count"] for w in windows], [4, 4, 2])
        self.assertTrue(windows[0]["dialogue"].startswith("Bob: line 0"))
        self.assertTrue(windows[-1]["dialogue"].endswith("Alice: line 9"))

        self.assertEqual(
            {d.question_key for d in decisions},
            {q.key for q in CONVERSATION_QUESTIONS},
        )
        self.assertTrue(all(d.target_type is DecisionTarget.CHAT for d in decisions))
        self.assertEqual(
            decisions[0].engine_metadata,
            {
                "scope": "whole_chat",
                "windows": 3,
                "window_size": 4,
                "messages_read": 10,
                "total_messages": 10,
            },
        )

    def test_a_long_chat_is_sampled_from_first_window_to_last(self):
        self.given_chat(100)
        decisions = self.service.evaluate_whole_chat(1, window_size=5, max_windows=4)

        windows = self.engine.batch_calls[0][0]
        self.assertEqual(len(windows), 4)
        self.assertTrue(windows[0]["dialogue"].startswith("Bob: line 0\n"))
        self.assertTrue(windows[-1]["dialogue"].endswith("Alice: line 99"))
        self.assertEqual(decisions[0].engine_metadata["messages_read"], 20)

    def test_whole_chat_answers_are_the_weighted_average_of_the_windows(self):
        from application.ports.decision_engine import EngineAnswer
        from application.services.decision_service import _combine

        question = CONVERSATION_QUESTIONS[1]  # overall_sentiment
        answers = [
            EngineAnswer(
                question_key=question.key,
                decision_type=question.decision_type,
                value="positive",
                probabilities={"positive": 0.6, "neutral": 0.3, "tense": 0.1},
            ),
            EngineAnswer(
                question_key=question.key,
                decision_type=question.decision_type,
                value="tense",
                probabilities={"positive": 0.0, "neutral": 0.2, "tense": 0.8},
            ),
        ]
        # The tense window held three times the turns.
        combined = _combine(question, answers, [1.0, 3.0])
        self.assertEqual(combined.value, "tense")
        self.assertEqual(combined.probabilities["positive"], 0.15)
        self.assertEqual(combined.probabilities["tense"], 0.625)
        self.assertEqual(combined.confidence, 0.625)

    def test_a_chat_with_nothing_to_read_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service.evaluate_chat_window(1)
        with self.assertRaises(ChatNotFoundError):
            self.service.evaluate_whole_chat(1)

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
