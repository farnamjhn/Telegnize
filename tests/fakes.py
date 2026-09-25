"""Test doubles for the application's outbound ports."""

from collections.abc import Mapping, Sequence
from typing import Any

from application.ports.decision_engine import (
    DecisionEngineError,
    DecisionQuestion,
    EngineAnswer,
    EngineResult,
    IDecisionEngine,
)
from domain.models.analysis import DecisionType


class FakeDecisionEngine(IDecisionEngine):
    """Answers every question with its first criterion, recording each call.

    Lets the decision flow be tested without loading several hundred megabytes
    of model weights.
    """

    def __init__(
        self,
        fail_with: str | None = None,
        answers: Mapping[str, Any] | None = None,
    ) -> None:
        self.calls: list[tuple[Any, Sequence[DecisionQuestion]]] = []
        self.batch_calls: list[tuple[list[Any], Sequence[DecisionQuestion]]] = []
        self._fail_with = fail_with
        #: Forced answers by question key, for tests that need a known reading.
        self._answers = dict(answers or {})

    @property
    def is_ready(self) -> bool:
        return True

    def describe(self) -> dict[str, str | None]:
        return {"engine": "fake", "status": "loaded"}

    def predict(
        self, state: Any, questions: Sequence[DecisionQuestion]
    ) -> EngineResult:
        if self._fail_with:
            raise DecisionEngineError(self._fail_with)
        self.calls.append((state, questions))
        return EngineResult(
            answers={
                question.key: self._answer(question) for question in questions
            },
            metadata={"checkpoint": "fake-checkpoint"},
        )

    def predict_batch(
        self, states: Sequence[Any], questions: Sequence[DecisionQuestion]
    ) -> list[EngineResult]:
        # Recorded as well as answered through ``predict``, so ``calls`` still
        # counts every state the engine was shown.
        self.batch_calls.append((list(states), questions))
        return super().predict_batch(states, questions)

    def _answer(self, question: DecisionQuestion) -> EngineAnswer:
        if question.key in self._answers:
            return EngineAnswer(
                question_key=question.key,
                decision_type=question.decision_type,
                value=self._answers[question.key],
                confidence=0.9,
            )
        return self._default_answer(question)

    @staticmethod
    def _default_answer(question: DecisionQuestion) -> EngineAnswer:
        """Answers in the same shapes the real adapter produces."""
        if question.decision_type is DecisionType.CHOICE:
            choices = list(question.criteria)
            value: Any = choices[0]
            probabilities = {name: 1.0 / len(choices) for name in choices}
        elif question.decision_type is DecisionType.NOUL:
            value = True
            probabilities = {"true": 0.9, "false": 0.1}
        else:
            value = float(len(question.levels) - 1) / 2
            probabilities = {str(i): 1.0 / len(question.levels)
                             for i in range(len(question.levels))}
        return EngineAnswer(
            question_key=question.key,
            decision_type=question.decision_type,
            value=value,
            confidence=0.9,
            probabilities=probabilities,
        )
