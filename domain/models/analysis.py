"""Analytical read models derived from stored chats."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class ParticipantStats:
    """Per-participant behavioural summary for a single chat."""

    sender_id: str
    sender_name: str
    message_count: int
    word_count: int
    char_count: int
    question_count: int
    cold_closure_count: int
    avg_words_per_message: float
    message_share_percent: float
    avg_response_time_seconds: float | None = None
    median_response_time_seconds: float | None = None


@dataclass(frozen=True)
class ChatAnalytics:
    """Volume, temporal, linguistic, and latency profile of one chat."""

    chat_id: int
    chat_name: str
    total_messages: int
    date_range_start: datetime | None
    date_range_end: datetime | None
    participants: list[ParticipantStats] = field(default_factory=list)
    hourly_distribution: dict[int, int] = field(default_factory=dict)
    daily_distribution: dict[str, int] = field(default_factory=dict)
    language_breakdown: dict[str, int] = field(default_factory=dict)
    avg_response_time_seconds: float | None = None


class DecisionTarget(StrEnum):
    """What a cached decision was computed about."""

    MESSAGE = "message"
    CHAT = "chat"


class DecisionType(StrEnum):
    """The typed answer shapes the decision engine can return."""

    CHOICE = "choice"
    SCORE = "score"
    NOUL = "noul"

    @classmethod
    def coerce(cls, value: "str | DecisionType | None") -> "DecisionType":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError:
            return cls.CHOICE


@dataclass
class Decision:
    """One typed decision about a message or a chat.

    Engine-agnostic on purpose: the domain records *what was decided*, while
    which model produced it is an infrastructure concern recorded in
    ``engine_metadata``.
    """

    target_type: DecisionTarget
    target_id: int
    question_key: str
    decision_type: DecisionType
    result_value: Any
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    engine_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        self.target_type = DecisionTarget(self.target_type)
        self.decision_type = DecisionType.coerce(self.decision_type)
