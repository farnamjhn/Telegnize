from typing import Any, Dict, List, Optional

from application.dtos.analysis_dto import LayaDecisionDTO
from domain.repository.message_repository import IMessageRepository
from infrastructure.decision_engine.laya_engine import (
    LayaDecisionEngine,
    get_decision_engine,
)


class DecisionService:
    """Orchestrates Laya decision inference, caching, and evaluation workflows."""

    def __init__(
        self,
        message_repo: IMessageRepository,
        engine: Optional[LayaDecisionEngine] = None,
    ):
        self.message_repo = message_repo
        self.engine = engine or get_decision_engine()

    def evaluate_message(
        self,
        message_id: int,
        questions: Optional[Dict[str, Any]] = None,
    ) -> List[LayaDecisionDTO]:
        """Evaluates a message with Laya, caches results, and returns DTOs."""
        msg = self.message_repo.get_by_id(message_id)
        if not msg:
            return []

        decisions = self.engine.evaluate_message(msg, questions=questions)
        for d in decisions:
            self.message_repo.save_laya_decision(d)

        return [
            LayaDecisionDTO(
                target_type=d.target_type,
                target_id=d.target_id,
                question_key=d.question_key,
                decision_type=d.decision_type,
                result_value=d.result_value,
                confidence=d.confidence,
                probabilities=d.probabilities,
            )
            for d in decisions
        ]

    def evaluate_chat_window(
        self,
        chat_id: int,
        limit: int = 20,
        questions: Optional[Dict[str, Any]] = None,
    ) -> List[LayaDecisionDTO]:
        """Evaluates recent conversation window in a chat."""
        messages = self.message_repo.get_by_chat(chat_id, limit=limit, offset=0)
        if not messages:
            return []

        dialogue_turns = [
            {
                "sender": m.sender_name,
                "text": m.normalized_text or m.text,
            }
            for m in messages
            if (m.normalized_text or m.text).strip()
        ]

        decisions = self.engine.evaluate_dialogue(
            chat_id=chat_id,
            dialogue_turns=dialogue_turns,
            questions=questions,
        )

        for d in decisions:
            self.message_repo.save_laya_decision(d)

        return [
            LayaDecisionDTO(
                target_type=d.target_type,
                target_id=d.target_id,
                question_key=d.question_key,
                decision_type=d.decision_type,
                result_value=d.result_value,
                confidence=d.confidence,
                probabilities=d.probabilities,
            )
            for d in decisions
        ]

    def evaluate_custom(self, state: Any, questions: Dict[str, Any]) -> Dict[str, Any]:
        """Runs ad-hoc inference using Laya."""
        return self.engine.predict(state=state, questions=questions)

    def get_cached_decisions(
        self, target_type: str, target_id: int
    ) -> List[LayaDecisionDTO]:
        decisions = self.message_repo.get_laya_decisions(target_type, target_id)
        return [
            LayaDecisionDTO(
                target_type=d.target_type,
                target_id=d.target_id,
                question_key=d.question_key,
                decision_type=d.decision_type,
                result_value=d.result_value,
                confidence=d.confidence,
                probabilities=d.probabilities,
            )
            for d in decisions
        ]
