"""Runs typed decisions over messages and conversations, and caches them."""

import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any

from application.decision_questions import CONVERSATION_QUESTIONS, MESSAGE_QUESTIONS
from application.dtos.analysis_dto import DecisionDTO
from application.ports.decision_engine import (
    DecisionQuestion,
    EngineAnswer,
    EngineResult,
    IDecisionEngine,
)
from domain.errors import ChatNotFoundError, MessageNotFoundError
from domain.models.analysis import Decision, DecisionTarget, DecisionType
from domain.models.message import Message
from domain.repository.decision_repository import IDecisionRepository
from domain.repository.message_repository import IMessageRepository

logger = logging.getLogger(__name__)

#: How many recent messages make up the conversation window put to the engine.
DEFAULT_WINDOW_SIZE = 20

#: Most windows a whole-chat reading samples. The engine reads about a
#: thousand tokens of a state and drops the rest, so a whole chat cannot be put
#: to it as one dialogue; it is read as windows spread evenly across the chat
#: instead, and this bounds how long that takes on a large one.
DEFAULT_WHOLE_CHAT_WINDOWS = 40


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
        # The *last* ``limit`` messages: the listing is oldest first.
        total = self._messages.count_by_chat(chat_id)
        state = _dialogue(
            self._messages.list_messages(
                chat_id=chat_id, limit=limit, offset=max(0, total - limit)
            )
        )
        if state is None:
            raise ChatNotFoundError(chat_id)

        result = self._engine.predict(state, questions or CONVERSATION_QUESTIONS)
        return self._persist(result, DecisionTarget.CHAT, chat_id)

    def evaluate_whole_chat(
        self,
        chat_id: int,
        window_size: int = DEFAULT_WINDOW_SIZE,
        max_windows: int = DEFAULT_WHOLE_CHAT_WINDOWS,
        questions: Sequence[DecisionQuestion] | None = None,
    ) -> list[DecisionDTO]:
        """Answers the conversation question set about the chat as a whole.

        Reads up to ``max_windows`` windows of ``window_size`` messages, spread
        evenly from the first message to the last, as one batch, and combines
        the answers: each answer's probabilities are averaged across windows,
        weighted by how many turns a window held. How much of the chat that
        covered is recorded alongside the answers.

        Raises:
            ChatNotFoundError: if the chat holds no readable messages.
            DecisionEngineError: if the engine fails.
        """
        window_size = max(1, window_size)
        total = self._messages.count_by_chat(chat_id)
        windows = [
            state
            for offset in _window_offsets(total, window_size, max(1, max_windows))
            if (
                state := _dialogue(
                    self._messages.list_messages(
                        chat_id=chat_id, limit=window_size, offset=offset
                    )
                )
            )
            is not None
        ]
        if not windows:
            raise ChatNotFoundError(chat_id)

        asked = questions or CONVERSATION_QUESTIONS
        results = self._engine.predict_batch(windows, asked)
        weights = [float(state["turns_count"]) for state in windows]
        combined = EngineResult(
            answers={
                question.key: _combine(
                    question,
                    [result.answers[question.key] for result in results],
                    weights,
                )
                for question in asked
                if all(question.key in result.answers for result in results)
            },
            metadata={
                "scope": "whole_chat",
                "windows": len(windows),
                "window_size": window_size,
                "messages_read": int(sum(weights)),
                "total_messages": total,
            },
        )
        return self._persist(combined, DecisionTarget.CHAT, chat_id)

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


def _dialogue(messages: Sequence[Message]) -> dict[str, Any] | None:
    """A conversation window as the engine reads it, or None if it is empty."""
    turns = [
        f"{message.sender_name}: {message.analysis_text}"
        for message in messages
        if message.analysis_text.strip()
    ]
    if not turns:
        return None
    return {"dialogue": "\n".join(turns), "turns_count": len(turns)}


def _window_offsets(total: int, window_size: int, max_windows: int) -> list[int]:
    """Where each sampled window starts: every window if they fit, otherwise
    ``max_windows`` of them spaced evenly from the first to the last."""
    count = math.ceil(total / window_size)
    if count <= max_windows:
        return [i * window_size for i in range(count)]
    if max_windows == 1:
        return [0]
    step = (count - 1) / (max_windows - 1)
    return sorted({round(i * step) * window_size for i in range(max_windows)})


def _combine(
    question: DecisionQuestion,
    answers: Sequence[EngineAnswer],
    weights: Sequence[float],
) -> EngineAnswer:
    """One answer from many windows' answers to the same question."""
    total_weight = sum(weights) or 1.0
    weighted = list(zip(answers, weights, strict=True))
    names = list(dict.fromkeys(n for a in answers for n in a.probabilities))
    probabilities = {
        name: round(
            sum(a.probabilities.get(name, 0.0) * w for a, w in weighted)
            / total_weight,
            4,
        )
        for name in names
    }

    value: Any
    if question.decision_type is DecisionType.SCORE:
        value = round(
            sum(float(a.value) * w for a, w in weighted) / total_weight,
            4,
        )
        confidence = max(probabilities.values(), default=0.0)
    elif question.decision_type is DecisionType.NOUL:
        p_true = probabilities.get("true", 0.0)
        value = p_true >= 0.5
        confidence = max(p_true, 1.0 - p_true)
    else:
        value = max(probabilities, key=probabilities.__getitem__)
        confidence = probabilities[value]

    return EngineAnswer(
        question_key=question.key,
        decision_type=question.decision_type,
        value=value,
        confidence=round(confidence, 4),
        probabilities=probabilities,
    )
