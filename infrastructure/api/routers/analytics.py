from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from application.dtos.analysis_dto import ChatAnalyticsDTO, ParticipantStatsDTO
from application.services.analytics_service import AnalyticsService
from infrastructure.api.dependencies import get_analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class ParticipantStatsSchema(BaseModel):
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

    class Config:
        from_attributes = True


class ChatAnalyticsSchema(BaseModel):
    chat_id: int
    chat_name: str
    total_messages: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    participants: List[ParticipantStatsSchema]
    hourly_distribution: Dict[int, int]
    daily_distribution: Dict[str, int]
    language_breakdown: Dict[str, int]
    avg_response_time_seconds: Optional[float] = None

    class Config:
        from_attributes = True


@router.get("/{chat_id}", response_model=ChatAnalyticsSchema)
def get_chat_analytics(
    chat_id: int,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Computes comprehensive behavioral, statistical, and latency analytics for a chat."""
    result = analytics_service.compute_chat_analytics(chat_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found.",
        )
    return ChatAnalyticsSchema.model_validate(result)
