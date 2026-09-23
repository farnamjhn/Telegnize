"""Integration test for the Laya adapter.

This one loads real model weights (hundreds of megabytes per checkpoint) and
runs live inference, so it is skipped by default to avoid sustained local CPU
load; everything that depends on the engine is covered against a fake
elsewhere. Set TELEGNIZE_SKIP_MODEL_TESTS=0 to run it deliberately.
"""

import os
import unittest

from application.ports.decision_engine import DecisionQuestion
from domain.models.analysis import DecisionType
from infrastructure.decision_engine.laya_engine import LayaDecisionEngine

SKIP = os.getenv("TELEGNIZE_SKIP_MODEL_TESTS", "1") != "0"


@unittest.skipIf(SKIP, "TELEGNIZE_SKIP_MODEL_TESTS=1")
class TestLayaDecisionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = LayaDecisionEngine()

    def test_construction_does_not_load_the_checkpoints(self):
        self.assertFalse(LayaDecisionEngine().is_ready)

    def test_a_noul_question_comes_back_as_a_boolean(self):
        result = self.engine.predict(
            "Hello there, good morning!",
            [
                DecisionQuestion(
                    key="is_greeting",
                    decision_type=DecisionType.NOUL,
                    instructions="Is this a greeting?",
                )
            ],
        )
        answer = result.answers["is_greeting"]
        self.assertIs(answer.decision_type, DecisionType.NOUL)
        self.assertIs(answer.value, True)
        self.assertGreater(answer.probabilities["true"], 0.5)
        self.assertAlmostEqual(
            answer.probabilities["true"] + answer.probabilities["false"], 1.0, places=3
        )

    def test_a_choice_question_picks_one_of_its_criteria(self):
        question = DecisionQuestion(
            key="tone",
            decision_type=DecisionType.CHOICE,
            instructions="What is the emotional tone of this message?",
            criteria={
                "friendly": "warm, supportive, appreciative",
                "frustrated": "annoyed, complaining, upset",
            },
        )
        result = self.engine.predict(
            "I really appreciate your help with this project!", [question]
        )
        answer = result.answers["tone"]
        self.assertIn(answer.value, question.criteria)
        self.assertEqual(set(answer.probabilities), set(question.criteria))
        self.assertTrue(self.engine.is_ready)

    def test_a_score_question_returns_a_number_on_its_scale(self):
        result = self.engine.predict(
            "This is the single best thing that has ever happened to me.",
            [
                DecisionQuestion(
                    key="enthusiasm",
                    decision_type=DecisionType.SCORE,
                    instructions="How enthusiastic is this message?",
                    levels=("not at all", "somewhat", "very"),
                )
            ],
        )
        answer = result.answers["enthusiasm"]
        self.assertIsInstance(answer.value, float)
        self.assertGreaterEqual(answer.value, 0.0)
        self.assertLessEqual(answer.value, 2.0)

    def test_routing_metadata_is_reported(self):
        result = self.engine.predict(
            "Hello there!",
            [
                DecisionQuestion(
                    key="is_greeting",
                    decision_type=DecisionType.NOUL,
                    instructions="Is this a greeting?",
                )
            ],
        )
        self.assertEqual(result.metadata.get("model"), "english")

    def test_asking_nothing_is_rejected(self):
        from application.ports.decision_engine import DecisionEngineError

        with self.assertRaises(DecisionEngineError):
            self.engine.predict("anything", [])


if __name__ == "__main__":
    unittest.main()
