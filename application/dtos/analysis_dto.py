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


class ParticipantStatsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class ChatAnalyticsDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_domain(cls, analytics: ChatAnalytics) -> "ChatAnalyticsDTO":
        return cls.model_validate(analytics)


class DecisionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_type: DecisionTarget
    target_id: int
    question_key: str
    decision_type: DecisionType
    result_value: Any
    confidence: float
    probabilities: dict[str, float] = {}
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, decision: Decision) -> "DecisionDTO":
        return cls.model_validate(decision)
