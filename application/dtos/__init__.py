"""Data transfer objects shared by services and the API layer.

These are Pydantic models so the API can serve them directly: keeping a third
set of near-identical response schemas in the routers bought nothing but drift.
The domain entities stay framework-free; conversion happens here.
"""

from application.dtos.analysis_dto import (
    ChatAnalyticsDTO,
    DecisionDTO,
    ParticipantStatsDTO,
)
from application.dtos.chat_dto import ChatDTO, ImportSummaryDTO
from application.dtos.message_dto import MessageDTO

__all__ = [
    "ChatAnalyticsDTO",
    "ChatDTO",
    "DecisionDTO",
    "ImportSummaryDTO",
    "MessageDTO",
    "ParticipantStatsDTO",
]
