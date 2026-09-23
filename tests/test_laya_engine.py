"""Integration test for the Laya adapter.

This one loads real model weights (hundreds of megabytes per checkpoint) and
runs live inference, so it is skipped by default to avoid sustained local CPU
load; everything that depends on the engine is covered against a fake
elsewhere. Set TELEGNIZE_SKIP_MODEL_TESTS=0 to run it deliberately.

How the adapter configures the router is checked separately, against a stub, so
that part always runs.
"""

import os
import sys
import types
import unittest
from typing import ClassVar

from application.ports.decision_engine import DecisionQuestion
from domain.models.analysis import DecisionType
from infrastructure.decision_engine.laya_engine import (
    RESIDENT_CHECKPOINTS,
    LayaDecisionEngine,
)

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


class StubRouter:
    """Stands in for ``laya.Router``, recording how it was built."""

    built: ClassVar[list["StubRouter"]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        StubRouter.built.append(self)

    def predict(self, state, questions):
        return {"answers": {}, "routing": {"model": "stub"}}


class TestRouterConfiguration(unittest.TestCase):
    """Always runs: Laya is stubbed out, so no weights are loaded."""

    def setUp(self):
        StubRouter.built = []
        self._saved = sys.modules.get("laya")
        stub = types.ModuleType("laya")
        stub.Router = StubRouter
        sys.modules["laya"] = stub

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("laya", None)
        else:
            sys.modules["laya"] = self._saved

    def ask(self, engine: LayaDecisionEngine) -> StubRouter:
        engine.predict(
            "anything",
            [
                DecisionQuestion(
                    key="is_greeting",
                    decision_type=DecisionType.NOUL,
                    instructions="Is this a greeting?",
                )
            ],
        )
        return StubRouter.built[-1]

    def test_both_routed_checkpoints_may_stay_resident(self):
        # The router evicts on every switch at one, and this adapter routes
        # between two checkpoints by script, so one is a rebuild per switch.
        self.assertGreaterEqual(RESIDENT_CHECKPOINTS, 2)
        self.assertEqual(self.ask(LayaDecisionEngine()).kwargs["max_loaded"], 2)

    def test_the_resident_count_can_be_turned_down(self):
        engine = LayaDecisionEngine(resident_checkpoints=1)
        self.assertEqual(self.ask(engine).kwargs["max_loaded"], 1)

    def test_a_nonsensical_resident_count_still_leaves_one_checkpoint(self):
        engine = LayaDecisionEngine(resident_checkpoints=0)
        self.assertEqual(self.ask(engine).kwargs["max_loaded"], 1)

    def test_preloading_is_passed_to_the_router(self):
        engine = LayaDecisionEngine(preload=True)
        self.assertTrue(StubRouter.built[-1].kwargs["preload"])
        self.assertTrue(engine.is_ready)

    def test_the_router_is_built_once_and_reused(self):
        engine = LayaDecisionEngine()
        self.ask(engine)
        self.ask(engine)
        self.assertEqual(len(StubRouter.built), 1)


if __name__ == "__main__":
    unittest.main()
