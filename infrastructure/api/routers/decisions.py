"""Typed decision endpoints."""

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from application.dtos.analysis_dto import DecisionDTO
from application.ports.decision_engine import DecisionQuestion
from application.services.decision_service import (
    DEFAULT_WINDOW_SIZE,
    questions_from_payload,
)
from domain.models.analysis import DecisionTarget
from infrastructure.api.dependencies import DecisionServiceDep

router = APIRouter(prefix="/decisions", tags=["Decisions"])

QuestionSpec = Mapping[str, Any]


class QuestionOverride(BaseModel):
    """Replaces the built-in question set for one request."""

    questions: dict[str, QuestionSpec] | None = Field(
        default=None,
        description="Question key to {type, instructions, criteria}. "
        "Omit to use Telegnize's own question set.",
    )


class EvaluateDialogueRequest(QuestionOverride):
    limit: int = Field(DEFAULT_WINDOW_SIZE, ge=1, le=200)


class CustomDecisionRequest(BaseModel):
    state: Any
    questions: dict[str, QuestionSpec]


@router.post(
    "/messages/{message_id}",
    response_model=list[DecisionDTO],
    summary="Evaluate one message",
)
def evaluate_message(
    message_id: int,
    decision_service: DecisionServiceDep,
    payload: QuestionOverride | None = None,
) -> list[DecisionDTO]:
    questions = questions_from_payload(payload.questions if payload else None)
    return decision_service.evaluate_message(message_id, questions=questions)


@router.get(
    "/messages/{message_id}",
    response_model=list[DecisionDTO],
    summary="Read cached decisions about a message",
)
def get_cached_message_decisions(
    message_id: int, decision_service: DecisionServiceDep
) -> list[DecisionDTO]:
    return decision_service.get_cached(DecisionTarget.MESSAGE, message_id)


@router.post(
    "/chats/{chat_id}",
    response_model=list[DecisionDTO],
    summary="Evaluate a chat's recent conversation window",
)
def evaluate_chat_dialogue(
    chat_id: int,
    decision_service: DecisionServiceDep,
    payload: EvaluateDialogueRequest | None = None,
) -> list[DecisionDTO]:
    questions = questions_from_payload(payload.questions if payload else None)
    return decision_service.evaluate_chat_window(
        chat_id,
        limit=payload.limit if payload else DEFAULT_WINDOW_SIZE,
        questions=questions,
    )


@router.get(
    "/chats/{chat_id}",
    response_model=list[DecisionDTO],
    summary="Read cached decisions about a chat",
)
def get_cached_chat_decisions(
    chat_id: int, decision_service: DecisionServiceDep
) -> list[DecisionDTO]:
    return decision_service.get_cached(DecisionTarget.CHAT, chat_id)


@router.post("/custom", summary="Evaluate an ad-hoc question set")
def evaluate_custom(
    request: CustomDecisionRequest, decision_service: DecisionServiceDep
) -> dict[str, Any]:
    """Answers arbitrary typed questions about arbitrary state, without caching."""
    questions = DecisionQuestion.many_from_mapping(request.questions)
    return decision_service.evaluate_custom(request.state, questions)
