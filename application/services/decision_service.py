"""Runs typed decisions over messages and conversations, and caches them."""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from application.decision_questions import CONVERSATION_QUESTIONS, MESSAGE_QUESTIONS
from application.dtos.analysis_dto import DecisionDTO
from application.ports.decision_engine import (
    DecisionQuestion,
    EngineResult,
    IDecisionEngine,
)
from domain.errors import ChatNotFoundError, MessageNotFoundError
from domain.models.analysis import Decision, DecisionTarget
from domain.repository.decision_repository import IDecisionRepository
from domain.repository.message_repository import IMessageRepository

logger = logging.getLogger(__name__)

#: How many recent messages make up the conversation window put to the engine.
DEFAULT_WINDOW_SIZE = 20


class DecisionService:
    """Turns stored conversations into engine questions and caches the answers.

    Cached answers are keyed by (target, question), so re-asking the same
    question about the same message is free and changing the question set does
    not invalidate unrelated answers.
    """

    def __init__(
        self,
        message_repo: IMessageRepository,
        decision_repo: IDecisionRepository,
        engine: IDecisionEngine,
    ) -> None:
        self._messages = message_repo
        self._decisions = decision_repo
        self._engine = engine

    # --- evaluation -------------------------------------------------------
    def evaluate_message(
        self,
        message_id: int,
        questions: Sequence[DecisionQuestion] | None = None,
    ) -> list[DecisionDTO]:
        """Answers the message question set about one stored message.

        Raises:
            MessageNotFoundError: if the message does not exist.
            DecisionEngineError: if the engine fails.
        """
        message = self._messages.get_by_id(message_id)
        if message is None:
            raise MessageNotFoundError(message_id)

        state = {
            "sender": message.sender_name,
            "text": message.analysis_text,
            "is_question": message.is_question,
        }
        result = self._engine.predict(state, questions or MESSAGE_QUESTIONS)
        return self._persist(result, DecisionTarget.MESSAGE, message.id)

    def evaluate_chat_window(
        self,
        chat_id: int,
        limit: int = DEFAULT_WINDOW_SIZE,
        questions: Sequence[DecisionQuestion] | None = None,
    ) -> list[DecisionDTO]:
        """Answers the conversation question set about a chat's recent turns.

        Raises:
            ChatNotFoundError: if the chat holds no readable messages.
            DecisionEngineError: if the engine fails.
        """
        messages = self._messages.list_messages(chat_id=chat_id, limit=limit)
        turns = [
            f"{message.sender_name}: {message.analysis_text}"
            for message in messages
            if message.analysis_text.strip()
        ]
        if not turns:
            raise ChatNotFoundError(chat_id)

        state = {"dialogue": "\n".join(turns), "turns_count": len(turns)}
        result = self._engine.predict(state, questions or CONVERSATION_QUESTIONS)
        return self._persist(result, DecisionTarget.CHAT, chat_id)

    def evaluate_custom(
        self, state: Any, questions: Sequence[DecisionQuestion]
    ) -> dict[str, Any]:
        """Answers an ad-hoc question set without caching the result.

        Raises:
            DecisionEngineError: if the engine fails.
        """
        result = self._engine.predict(state, questions)
        return {
            "answers": {
                key: {
                    "type": answer.decision_type,
                    "value": answer.value,
                    "confidence": answer.confidence,
                    "probabilities": answer.probabilities,
                }
                for key, answer in result.answers.items()
            },
            "metadata": result.metadata,
        }

    # --- cache ------------------------------------------------------------
    def get_cached(
        self, target_type: DecisionTarget, target_id: int
    ) -> list[DecisionDTO]:
        decisions = self._decisions.list_for_target(target_type, target_id)
        return [DecisionDTO.from_domain(decision) for decision in decisions]

    def _persist(
        self, result: EngineResult, target_type: DecisionTarget, target_id: int
    ) -> list[DecisionDTO]:
        decisions = [
            Decision(
                target_type=target_type,
                target_id=target_id,
                question_key=answer.question_key,
                decision_type=answer.decision_type,
                result_value=answer.value,
                confidence=answer.confidence,
                probabilities=answer.probabilities,
                engine_metadata=result.metadata,
            )
            for answer in result.answers.values()
        ]
        self._decisions.save_batch(decisions)
        return [DecisionDTO.from_domain(decision) for decision in decisions]


def questions_from_payload(
    payload: Mapping[str, Mapping[str, Any]] | None,
) -> Sequence[DecisionQuestion] | None:
    """Builds a question set from an API payload, or None to use the default."""
    if not payload:
        return None
    return DecisionQuestion.many_from_mapping(payload)
