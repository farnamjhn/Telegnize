"""Laya adapter for :class:`IDecisionEngine`.

Laya answers a whole question set in one non-autoregressive forward pass and
routes between an English and a multilingual checkpoint by itself. This module
is the only place that knows Laya's wire format: it translates typed questions
into Laya's nested-dict schema and its raw answers back into
:class:`EngineAnswer`.
"""

import logging
import threading
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

logger = logging.getLogger(__name__)

#: P(true) at or above which a noul question is answered "yes".
NOUL_THRESHOLD = 0.5

# Where each answer type carries its value in Laya's response.
_VALUE_KEYS: dict[DecisionType, str] = {
    DecisionType.CHOICE: "choice",
    DecisionType.SCORE: "score",
    DecisionType.NOUL: "noul",
}


class LayaDecisionEngine(IDecisionEngine):
    """Wraps ``laya.Router``, loading the checkpoints on first prediction.

    Construction is cheap and does no I/O: the checkpoints are hundreds of
    megabytes, so an app that never asks a question never pays for them.
    """

    def __init__(self, preload: bool = False) -> None:
        self._preload = preload
        self._router: Any | None = None
        self._lock = threading.Lock()
        if preload:
            self._ensure_router()

    # --- lifecycle --------------------------------------------------------
    def _ensure_router(self) -> Any:
        if self._router is None:
            with self._lock:
                if self._router is None:
                    from laya import Router  # imported late: heavy, optional

                    logger.info("Loading Laya router (preload=%s).", self._preload)
                    self._router = Router(preload=self._preload)
        return self._router

    @property
    def is_ready(self) -> bool:
        return self._router is not None

    def describe(self) -> dict[str, str | None]:
        return {
            "engine": "laya",
            "status": "loaded" if self.is_ready else "not_loaded",
        }

    # --- prediction -------------------------------------------------------
    def predict(
        self,
        state: Any,
        questions: Sequence[DecisionQuestion],
    ) -> EngineResult:
        if not questions:
            raise DecisionEngineError("At least one question is required.")

        schema = {q.key: _to_laya_schema(q) for q in questions}
        expected = {q.key: q.decision_type for q in questions}

        try:
            raw = self._ensure_router().predict(state=state, questions=schema)
        except Exception as error:  # laya raises a variety of library errors
            logger.exception("Laya prediction failed.")
            raise DecisionEngineError(str(error)) from error

        return EngineResult(
            answers=_to_answers(raw.get("answers", {}), expected),
            metadata=dict(raw.get("routing", {})),
        )


def _to_laya_schema(question: DecisionQuestion) -> dict[str, Any]:
    """Renders a question in Laya's schema.

    Laya reads a score question's rungs from an ordered list and every other
    type's options from a mapping, both under the key ``criteria``.
    """
    schema: dict[str, Any] = {
        "type": str(question.decision_type),
        "instructions": question.instructions,
    }
    if question.decision_type is DecisionType.SCORE:
        schema["criteria"] = list(question.levels)
    elif question.criteria:
        schema["criteria"] = dict(question.criteria)
    return schema


def _to_answers(
    raw_answers: Mapping[str, Mapping[str, Any]],
    expected: Mapping[str, DecisionType],
) -> dict[str, EngineAnswer]:
    answers: dict[str, EngineAnswer] = {}
    for key, payload in raw_answers.items():
        decision_type = DecisionType.coerce(payload.get("type") or expected.get(key))
        raw_value = payload.get(_VALUE_KEYS[decision_type], payload.get("value"))
        probabilities = {
            str(name): float(score)
            for name, score in (payload.get("probabilities") or {}).items()
        }

        if decision_type is DecisionType.NOUL:
            # Laya answers a noul with P(true) and no distribution. Callers
            # asked a yes/no question, so they get a bool, with the number it
            # was read off kept alongside it.
            probability = float(raw_value or 0.0)
            value: Any = probability >= NOUL_THRESHOLD
            probabilities = {"true": probability, "false": round(1.0 - probability, 4)}
        else:
            value = raw_value

        answers[key] = EngineAnswer(
            question_key=key,
            decision_type=decision_type,
            value=value,
            confidence=float(payload.get("confidence") or 0.0),
            probabilities=probabilities,
        )
    return answers
