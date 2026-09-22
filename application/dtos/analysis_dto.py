from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ParticipantStatsDTO:
    sender_id: str
    sender_name: str
    message_count: int
    word_count: int
    char_count: int
    question_count: int
    cold_closure_count: int
    avg_words_per_message: float
    message_share_percent: float
    avg_response_time_seconds: Optional[float] = None


@dataclass
class ChatAnalyticsDTO:
    chat_id: int
    chat_name: str
    total_messages: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    participants: List[ParticipantStatsDTO]
    hourly_distribution: Dict[int, int]
    daily_distribution: Dict[str, int]
    language_breakdown: Dict[str, int]
    avg_response_time_seconds: Optional[float] = None


@dataclass
class LayaDecisionDTO:
    target_type: str
    target_id: int
    question_key: str
    decision_type: str
    result_value: Any
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    created_at: Optional[datetime] = None
