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


GREETING = DecisionQuestion(
    key="is_greeting",
    decision_type=DecisionType.NOUL,
    instructions="Is this a greeting?",
)


class StubRouter:
    """Stands in for ``laya.Router``, recording how it was built."""

    built: ClassVar[list["StubRouter"]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        StubRouter.built.append(self)

    def predict(self, state, questions, **overrides):
        self.predicted = overrides
        return {"answers": {}, "routing": {"model": "stub"}}

    def predict_batch(self, requests, batch_size=None):
        self.requests = list(requests)
        self.batch_size = batch_size
        return [
            {
                "answers": {
                    key: {"type": "noul", "noul": 0.8, "confidence": 0.8}
                    for key in request["questions"]
                },
                "routing": {"model": "stub", "index": index},
            }
            for index, request in enumerate(requests)
        ]


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

    def test_a_batch_is_one_router_call_in_order(self):
        engine = LayaDecisionEngine(batch_size=7)
        results = engine.predict_batch(["a", "b", "c"], [GREETING])
        router = StubRouter.built[-1]

        self.assertEqual([r["state"] for r in router.requests], ["a", "b", "c"])
        self.assertEqual(router.batch_size, 7)
        self.assertEqual([r.metadata["index"] for r in results], [0, 1, 2])
        self.assertIs(results[0].answers["is_greeting"].value, True)

    def test_an_empty_batch_loads_nothing(self):
        self.assertEqual(LayaDecisionEngine().predict_batch([], [GREETING]), [])
        self.assertEqual(StubRouter.built, [])

    def test_without_a_fine_tune_the_stock_checkpoints_are_used(self):
        router = self.ask(LayaDecisionEngine())
        self.assertIsNone(router.kwargs["models"])
        self.assertEqual(router.kwargs["default"], "english")

    def test_a_fine_tune_replaces_only_the_multilingual_checkpoint(self):
        engine = LayaDecisionEngine(custom_model_path="ckpt")
        router = self.ask(engine)
        self.assertEqual(router.kwargs["models"], {"multilingual": "ckpt"})
        # Text Laya cannot place goes to the fine-tune.
        self.assertEqual(router.kwargs["default"], "multilingual")
        self.assertEqual(router.predicted, {})

        engine.predict_batch(["a"], [GREETING])
        self.assertNotIn("model", router.requests[0])

    def test_a_fine_tune_for_english_pins_every_request_to_it(self):
        engine = LayaDecisionEngine(
            custom_model_path="ckpt", custom_model_for_english=True
        )
        router = self.ask(engine)
        # One route name for the fine-tune, so its weights load once.
        self.assertEqual(router.kwargs["models"], {"multilingual": "ckpt"})
        self.assertEqual(router.predicted, {"model": "multilingual"})

        engine.predict_batch(["a"], [GREETING])
        self.assertEqual(router.requests[0]["model"], "multilingual")

    def test_the_router_is_built_once_and_reused(self):
        engine = LayaDecisionEngine()
        self.ask(engine)
        self.ask(engine)
        self.assertEqual(len(StubRouter.built), 1)


if __name__ == "__main__":
    unittest.main()
