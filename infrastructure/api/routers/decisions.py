from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from application.dtos.analysis_dto import LayaDecisionDTO
from application.services.decision_service import DecisionService
from infrastructure.api.dependencies import get_decision_service

router = APIRouter(prefix="/decisions", tags=["Laya Decisions"])


class LayaDecisionSchema(BaseModel):
    target_type: str
    target_id: int
    question_key: str
    decision_type: str
    result_value: Any
    confidence: float
    probabilities: Dict[str, float] = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomDecisionRequest(BaseModel):
    state: Any
    questions: Dict[str, Any]


class EvaluateDialogueRequest(BaseModel):
    limit: int = 20
    custom_questions: Optional[Dict[str, Any]] = None


@router.post("/messages/{message_id}", response_model=List[LayaDecisionSchema])
def evaluate_message(
    message_id: int,
    custom_questions: Optional[Dict[str, Any]] = None,
    decision_service: DecisionService = Depends(get_decision_service),
):
    """Evaluates a message with Laya System 1 decision engine and persists decisions."""
    decisions = decision_service.evaluate_message(message_id, questions=custom_questions)
    if not decisions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found or has no evaluatable content.",
        )
    return [LayaDecisionSchema.model_validate(d) for d in decisions]


@router.get("/messages/{message_id}", response_model=List[LayaDecisionSchema])
def get_cached_message_decisions(
    message_id: int,
    decision_service: DecisionService = Depends(get_decision_service),
):
    """Retrieves previously cached Laya decisions for a message."""
    decisions = decision_service.get_cached_decisions("message", message_id)
    return [LayaDecisionSchema.model_validate(d) for d in decisions]


@router.post("/chats/{chat_id}", response_model=List[LayaDecisionSchema])
def evaluate_chat_dialogue(
    chat_id: int,
    payload: Optional[EvaluateDialogueRequest] = None,
    decision_service: DecisionService = Depends(get_decision_service),
):
    """Evaluates recent dialogue window in a chat for dynamic and sentiment."""
    limit = payload.limit if payload else 20
    q = payload.custom_questions if payload else None
    decisions = decision_service.evaluate_chat_window(chat_id, limit=limit, questions=q)
    if not decisions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No dialogue messages found to evaluate for chat {chat_id}.",
        )
    return [LayaDecisionSchema.model_validate(d) for d in decisions]


@router.get("/chats/{chat_id}", response_model=List[LayaDecisionSchema])
def get_cached_chat_decisions(
    chat_id: int,
    decision_service: DecisionService = Depends(get_decision_service),
):
    """Retrieves previously cached Laya decisions for a chat."""
    decisions = decision_service.get_cached_decisions("chat", chat_id)
    return [LayaDecisionSchema.model_validate(d) for d in decisions]


@router.post("/custom")
def evaluate_custom(
    req: CustomDecisionRequest,
    decision_service: DecisionService = Depends(get_decision_service),
):
    """Runs ad-hoc inference with Laya given an arbitrary state and typed questions schema."""
    try:
        return decision_service.evaluate_custom(state=req.state, questions=req.questions)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Laya inference error: {str(e)}",
        )
