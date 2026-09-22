"""Chat analytics endpoints."""

from fastapi import APIRouter

from application.dtos.analysis_dto import ChatAnalyticsDTO
from infrastructure.api.dependencies import AnalyticsServiceDep

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/{chat_id}",
    response_model=ChatAnalyticsDTO,
    summary="Behavioural and statistical profile of a chat",
)
def get_chat_analytics(
    chat_id: int, analytics_service: AnalyticsServiceDep
) -> ChatAnalyticsDTO:
    return analytics_service.compute_chat_analytics(chat_id)
