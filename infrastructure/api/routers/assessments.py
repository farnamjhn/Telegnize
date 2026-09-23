"""Relational assessment endpoints.

Assessment runs the decision engine over a chat's messages, which is slow
enough that it is paged: each POST works through one page and says where to
resume. The GET reports the aggregate over whatever has been assessed so far.
"""

from fastapi import APIRouter, Query

from application.dtos.analysis_dto import (
    AssessmentProgressDTO,
    RelationalAssessmentDTO,
)
from infrastructure.api.dependencies import AssessmentServiceDep

router = APIRouter(prefix="/assessments", tags=["Assessment"])


@router.post(
    "/{chat_id}",
    response_model=AssessmentProgressDTO,
    summary="Assess one page of a chat's messages",
)
def assess_chat_page(
    chat_id: int,
    assessment_service: AssessmentServiceDep,
    offset: int = Query(0, ge=0, description="Where in the chat to resume"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Messages to assess in this call"
    ),
) -> AssessmentProgressDTO:
    """Runs the question set over a page, skipping messages already answered.

    How long that takes is a property of the machine, not of this endpoint, so
    time one small page before committing to a long run. Call it again with the
    returned ``next_offset`` until ``is_complete``.
    """
    return assessment_service.assess_page(chat_id, offset=offset, limit=limit)


@router.get(
    "/{chat_id}",
    response_model=RelationalAssessmentDTO,
    summary="Read the assessment built so far",
)
def get_assessment(
    chat_id: int, assessment_service: AssessmentServiceDep
) -> RelationalAssessmentDTO:
    """Aggregates the cached answers. Read every figure against `coverage_percent`."""
    return assessment_service.get_assessment(chat_id)
