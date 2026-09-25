"""Analytics- and decision-shaped payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from domain.models.analysis import (
    ChatAnalytics,
    Decision,
    DecisionTarget,
    DecisionType,
)

_FROM_DOMAIN = ConfigDict(from_attributes=True)


class LatencyPointDTO(BaseModel):
    model_config = _FROM_DOMAIN

    period: str
    median_seconds: float
    reply_count: int


class ResponsivenessDTO(BaseModel):
    model_config = _FROM_DOMAIN

    avg_seconds: float | None = None
    median_seconds: float | None = None
    p90_seconds: float | None = None
    reply_count: int = 0
    question_count: int = 0
    questions_answered_count: int = 0
    questions_answered_percent: float | None = None
    latency_trend: list[LatencyPointDTO] = []
    latency_drift_percent: float | None = None


class EngagementDTO(BaseModel):
    model_config = _FROM_DOMAIN

    opened_count: int = 0
    opened_percent: float | None = None
    closed_count: int = 0
    turn_count: int = 0
    avg_messages_per_turn: float = 0.0
    avg_words_per_turn: float = 0.0
    double_text_percent: float = 0.0
    cold_closure_count: int = 0
    cold_closure_percent: float = 0.0
    voice_message_count: int = 0
    media_count: int = 0


class ExpressionDTO(BaseModel):
    model_config = _FROM_DOMAIN

    exclamation_count: int = 0
    emoji_count: int = 0
    affection_count: int = 0
    apology_count: int = 0
    gratitude_count: int = 0
    self_reference_count: int = 0
    collective_reference_count: int = 0
    absolutist_count: int = 0
    elongation_count: int = 0
    exclamations_per_1k_words: float = 0.0
    affection_per_1k_words: float = 0.0
    apology_per_1k_words: float = 0.0
    gratitude_per_1k_words: float = 0.0
    elongation_per_1k_words: float = 0.0
    emoji_per_100_words: float = 0.0
    absolutism_percent: float = 0.0
    collective_focus_percent: float | None = None


class CircadianDTO(BaseModel):
    """When someone writes, and how fast they answer while still awake."""

    model_config = _FROM_DOMAIN

    hourly_distribution: dict[int, int] = {}
    night_owl_percent: float = 0.0
    peak_hour: int | None = None
    #: Reply times with the overnight gaps taken out — see
    #: ``docs/analytics.md`` for why the unfiltered median is a statement
    #: about sleep rather than about attention.
    active_median_seconds: float | None = None
    active_p90_seconds: float | None = None
    active_reply_count: int = 0
    #: Silences long enough to count as the conversation having stopped, that
    #: this participant was the one to end.
    revived_count: int = 0
    revived_percent: float | None = None


class ControlDTO(BaseModel):
    """Who sets the pace of a conversation, and who ends it."""

    model_config = _FROM_DOMAIN

    burst_count: int = 0
    long_burst_count: int = 0
    long_burst_percent: float = 0.0
    longest_burst: int = 0
    avg_burst_size: float = 0.0
    last_word_count: int = 0
    last_word_percent: float | None = None
    collision_count: int = 0
    collision_percent: float = 0.0


class CompositionDTO(BaseModel):
    """What someone's messages are made of: vocabulary, media, voice."""

    model_config = _FROM_DOMAIN

    unique_word_count: int = 0
    #: Unique words over total words. Falls as a sample grows, so it is only
    #: ever comparable between people who wrote similar amounts.
    type_token_ratio: float | None = None
    #: Moving-average type-token ratio over a fixed window, which does not
    #: fall with sample size and is the figure to compare.
    lexical_diversity: float | None = None
    text_message_count: int = 0
    media_message_count: int = 0
    media_percent: float = 0.0
    link_count: int = 0
    voice_message_count: int = 0
    voice_seconds: int = 0
    avg_voice_seconds: float | None = None
    #: Voice notes whose length the export carried. Zero means the durations
    #: were never imported, not that the notes were empty.
    timed_voice_count: int = 0


class StanceDTO(BaseModel):
    """How someone positions themselves: asking, hedging, going along.

    Named for Hyland's stance-and-engagement framework, which these borrow the
    idea of and none of the coding procedure from.
    """

    model_config = _FROM_DOMAIN

    interrogative_count: int = 0
    questions_per_100_messages: float = 0.0
    hedge_count: int = 0
    hedge_per_1k_words: float = 0.0
    backchannel_count: int = 0
    backchannel_percent: float = 0.0


class StyleMatchingDTO(BaseModel):
    """Linguistic Style Matching across adjacent turns.

    Function words — the grammatical scaffolding nobody picks deliberately —
    converge between people who are engaged with each other. This is that
    convergence as a percentage, plus the per-category figures it averages.
    """

    model_config = _FROM_DOMAIN

    lsm_percent: float | None = None
    by_category: dict[str, float] = {}
    turn_pairs: int = 0


class ParticipantStatsDTO(BaseModel):
    model_config = _FROM_DOMAIN

    sender_id: str
    sender_name: str
    message_count: int
    word_count: int
    char_count: int
    avg_words_per_message: float
    message_share_percent: float
    word_share_percent: float
    responsiveness: ResponsivenessDTO
    engagement: EngagementDTO
    expression: ExpressionDTO
    circadian: CircadianDTO = CircadianDTO()
    control: ControlDTO = ControlDTO()
    composition: CompositionDTO = CompositionDTO()
    stance: StanceDTO = StanceDTO()


class ConversationRhythmDTO(BaseModel):
    model_config = _FROM_DOMAIN

    session_count: int = 0
    avg_messages_per_session: float = 0.0
    avg_session_minutes: float = 0.0
    active_days: int = 0
    span_days: int = 0
    active_day_percent: float = 0.0
    longest_silence_days: float = 0.0
    late_night_percent: float = 0.0
    #: Silences long enough to count as the conversation having stopped.
    silence_count: int = 0


class BalanceDTO(BaseModel):
    model_config = _FROM_DOMAIN

    message_balance_percent: float = 100.0
    word_balance_percent: float = 100.0
    initiation_balance_percent: float = 100.0
    response_time_ratio: float | None = None


class ChatAnalyticsDTO(BaseModel):
    model_config = _FROM_DOMAIN

    chat_id: int
    chat_name: str
    total_messages: int
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    participants: list[ParticipantStatsDTO] = []
    hourly_distribution: dict[int, int] = {}
    daily_distribution: dict[str, int] = {}
    language_breakdown: dict[str, int] = {}
    avg_response_time_seconds: float | None = None
    rhythm: ConversationRhythmDTO = ConversationRhythmDTO()
    balance: BalanceDTO = BalanceDTO()
    style_matching: StyleMatchingDTO = StyleMatchingDTO()

    @classmethod
    def from_domain(cls, analytics: ChatAnalytics) -> "ChatAnalyticsDTO":
        return cls.model_validate(analytics)


class DecisionDTO(BaseModel):
    model_config = _FROM_DOMAIN

    target_type: DecisionTarget
    target_id: int
    question_key: str
    decision_type: DecisionType
    result_value: Any
    confidence: float
    probabilities: dict[str, float] = {}
    #: What the engine said about how it answered — which checkpoint, and for
    #: a whole-chat reading how much of the chat it covered.
    engine_metadata: dict[str, Any] = {}
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, decision: Decision) -> "DecisionDTO":
        return cls.model_validate(decision)


class ParticipantAssessmentDTO(BaseModel):
    model_config = _FROM_DOMAIN

    sender_id: str
    sender_name: str
    assessed_message_count: int = 0
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    positivity_ratio: float | None = None
    bid_count: int = 0
    bids_met_count: int = 0
    bids_met_percent: float | None = None
    criticism_count: int = 0
    defensiveness_count: int = 0
    contempt_count: int = 0
    friction_percent: float = 0.0
    repair_count: int = 0
    repair_percent: float = 0.0
    avg_sarcasm_score: float | None = None
    statement_count: int = 0
    closed_question_count: int = 0
    open_question_count: int = 0
    curiosity_per_1k_words: float = 0.0


class RelationalAssessmentDTO(BaseModel):
    model_config = _FROM_DOMAIN

    chat_id: int
    chat_name: str
    total_messages: int = 0
    assessed_messages: int = 0
    coverage_percent: float = 0.0
    participants: list[ParticipantAssessmentDTO] = []


class AssessmentProgressDTO(BaseModel):
    model_config = _FROM_DOMAIN

    chat_id: int
    assessed_now: int
    skipped_already_done: int
    next_offset: int
    is_complete: bool
    coverage_percent: float


class AssessmentRunDTO(BaseModel):
    """How far a background assessment run has got. Poll it while it works."""

    model_config = _FROM_DOMAIN

    chat_id: int
    state: str
    is_active: bool
    page_size: int
    max_pages: int | None = None
    started_offset: int
    next_offset: int
    pages: int
    assessed: int
    skipped: int
    coverage_percent: float
    elapsed_seconds: float
    last_page_seconds: float | None = None
    seconds_per_message: float | None = None
    error: str | None = None
