"""Analytical read models derived from stored chats."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class Responsiveness:
    """How readily one participant answers the other.

    Perceived responsiveness — the sense that the other person notices and
    replies — is what these numbers circle, but they measure timing and uptake,
    not whether a reply was any good.
    """

    #: Latency is heavily skewed by a few long gaps, so the median says more
    #: about the usual experience than the mean, and p90 about the worst of it.
    avg_seconds: float | None = None
    median_seconds: float | None = None
    p90_seconds: float | None = None
    reply_count: int = 0
    question_count: int = 0
    #: Questions this person asked that the other party took up in time.
    questions_answered_count: int = 0
    questions_answered_percent: float | None = None


@dataclass(frozen=True)
class Engagement:
    """Who carries the conversation, and how they hold the floor."""

    #: Conversations this person started after a silence, and ended.
    opened_count: int = 0
    opened_percent: float | None = None
    closed_count: int = 0
    #: Uninterrupted runs of their own messages.
    turn_count: int = 0
    avg_messages_per_turn: float = 0.0
    #: Share of their messages that continued their own turn rather than
    #: answering — writing again before the other person has said anything.
    double_text_percent: float = 0.0
    #: Whole messages that are a bare acknowledgement.
    cold_closure_count: int = 0
    cold_closure_percent: float = 0.0
    voice_message_count: int = 0
    media_count: int = 0


@dataclass(frozen=True)
class Expression:
    """What this participant's wording carries.

    Counts come from the marker lists in :mod:`domain.models.lexicons` and are
    observations about wording, not measurements of feeling. Rates are per
    thousand words, because someone who writes more has more of everything.
    """

    exclamation_count: int = 0
    emoji_count: int = 0
    affection_count: int = 0
    apology_count: int = 0
    gratitude_count: int = 0
    self_reference_count: int = 0
    collective_reference_count: int = 0

    exclamations_per_1k_words: float = 0.0
    emoji_per_1k_words: float = 0.0
    affection_per_1k_words: float = 0.0
    apology_per_1k_words: float = 0.0
    gratitude_per_1k_words: float = 0.0
    #: Share of first-person reference that is "we" rather than "I". A pair who
    #: talk about themselves as a unit sit high; this says nothing on its own
    #: about whether that is a good thing.
    collective_focus_percent: float | None = None


@dataclass(frozen=True)
class ParticipantStats:
    """Per-participant behavioural summary for a single chat."""

    sender_id: str
    sender_name: str
    message_count: int
    word_count: int
    char_count: int
    avg_words_per_message: float
    message_share_percent: float
    word_share_percent: float
    responsiveness: Responsiveness = field(default_factory=Responsiveness)
    engagement: Engagement = field(default_factory=Engagement)
    expression: Expression = field(default_factory=Expression)


@dataclass(frozen=True)
class ConversationRhythm:
    """The shape of the conversation over time.

    A session is a run of messages with no silence in it longer than the
    configured gap — roughly, one sitting.
    """

    session_count: int = 0
    avg_messages_per_session: float = 0.0
    avg_session_minutes: float = 0.0
    #: Days with at least one message, against the days the chat spans.
    active_days: int = 0
    span_days: int = 0
    active_day_percent: float = 0.0
    #: The longest the conversation went quiet, in days.
    longest_silence_days: float = 0.0
    #: Share of messages sent between midnight and 05:00, when people tend to
    #: write more freely than they would in daylight.
    late_night_percent: float = 0.0


@dataclass(frozen=True)
class Balance:
    """How evenly the conversation is shared.

    Each figure is a normalised entropy over the participants' shares: 100 when
    everyone contributes equally, falling toward 0 as one person dominates. It
    generalises past two participants, which a simple ratio would not.
    """

    message_balance_percent: float = 100.0
    word_balance_percent: float = 100.0
    initiation_balance_percent: float = 100.0
    #: Slowest participant's median reply time over the fastest's. 1.0 means
    #: they answer each other at the same pace.
    response_time_ratio: float | None = None


@dataclass(frozen=True)
class ChatAnalytics:
    """Volume, temporal, linguistic, and latency profile of one chat."""

    chat_id: int
    chat_name: str
    total_messages: int
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    participants: list[ParticipantStats] = field(default_factory=list)
    hourly_distribution: dict[int, int] = field(default_factory=dict)
    daily_distribution: dict[str, int] = field(default_factory=dict)
    language_breakdown: dict[str, int] = field(default_factory=dict)
    avg_response_time_seconds: float | None = None
    rhythm: ConversationRhythm = field(default_factory=ConversationRhythm)
    balance: Balance = field(default_factory=Balance)


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
