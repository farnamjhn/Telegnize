"""Port for the typed decision engine.

The application layer asks questions and reads typed answers; which model
answers them, and in what wire format, stays behind this interface.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.models.analysis import DecisionType


class DecisionEngineError(RuntimeError):
    """Raised when the decision engine cannot answer a question set."""


@dataclass(frozen=True)
class DecisionQuestion:
    """One typed question to put to the engine.

    What defines the answer space depends on the type: a ``CHOICE`` question
    carries ``criteria``, one description per allowed choice; a ``SCORE``
    question carries ``levels``, the ordered descriptions of its rungs; a
    ``NOUL`` question needs neither, though ``criteria`` may describe what
    "true" and "false" mean. Getting this wrong used to surface as an opaque
    crash inside the model, so it is checked here instead.
    """

    key: str
    decision_type: DecisionType
    instructions: str
    criteria: Mapping[str, str] = field(default_factory=dict)
    levels: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.instructions.strip():
            raise ValueError(f"Question {self.key!r} needs instructions.")
        if self.decision_type is DecisionType.CHOICE and len(self.criteria) < 2:
            raise ValueError(
                f"Choice question {self.key!r} needs at least two criteria."
            )
        if self.decision_type is DecisionType.SCORE and len(self.levels) < 2:
            raise ValueError(f"Score question {self.key!r} needs at least two levels.")

    @classmethod
    def from_mapping(cls, key: str, spec: Mapping[str, Any]) -> "DecisionQuestion":
        """Builds a question from the nested-dict form used by API payloads."""
        return cls(
            key=key,
            decision_type=DecisionType.coerce(spec.get("type")),
            instructions=str(spec.get("instructions", "")),
            criteria=dict(spec.get("criteria") or {}),
            levels=tuple(spec.get("levels") or ()),
        )

    @classmethod
    def many_from_mapping(
        cls, spec: Mapping[str, Mapping[str, Any]]
    ) -> list["DecisionQuestion"]:
        return [cls.from_mapping(key, value) for key, value in spec.items()]


@dataclass(frozen=True)
class EngineAnswer:
    """The engine's typed answer to a single question.

    ``value`` is typed to match the question: the chosen key for ``CHOICE``,
    a bool for ``NOUL``, a number for ``SCORE``. ``probabilities`` carries the
    distribution the value was read off, so nothing the engine knew is lost.
    """

    question_key: str
    decision_type: DecisionType
    value: Any
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineResult:
    """A full engine response: one answer per question, plus routing metadata."""

    answers: dict[str, EngineAnswer] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class IDecisionEngine(ABC):
    @abstractmethod
    def predict(
        self,
        state: Any,
        questions: Sequence[DecisionQuestion],
    ) -> EngineResult:
        """Answers every question about ``state`` in a single forward pass.

        Raises:
            DecisionEngineError: if the underlying model fails.
        """

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Whether the engine has loaded and can serve a prediction immediately."""

    @abstractmethod
    def describe(self) -> dict[str, str | None]:
        """Identifies the engine and checkpoints backing it, for health reporting."""
