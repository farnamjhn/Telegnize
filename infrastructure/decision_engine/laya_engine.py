import logging
from typing import Any, Dict, List, Optional, Union
from laya import Router

from domain.models.analysis import LayaDecisionResult
from domain.models.message import Message
from infrastructure.decision_engine.schemas import (
    MESSAGE_TONE_QUESTIONS,
    CONVERSATION_DYNAMIC_QUESTIONS,
)

logger = logging.getLogger(__name__)


class LayaDecisionEngine:
    """Non-autoregressive System 1 decision engine wrapping Laya with multilingual routing."""

    _instance: Optional["LayaDecisionEngine"] = None

    def __init__(self, preload: bool = False):
        self._router = Router(preload=preload)

    @classmethod
    def get_instance(cls) -> "LayaDecisionEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def predict(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Runs single forward-pass inference over state and questions."""
        return self._router.predict(state=state, questions=questions)

    def evaluate_message(
        self,
        message: Message,
        questions: Optional[Dict[str, Any]] = None,
    ) -> List[LayaDecisionResult]:
        """Evaluates a single Message entity using Laya and returns LayaDecisionResult records."""
        q_set = questions or MESSAGE_TONE_QUESTIONS
        text_content = message.normalized_text or message.text
        if not text_content:
            return []

        state = {
            "sender": message.sender_name,
            "text": text_content,
            "is_question": message.is_question,
        }

        try:
            res = self.predict(state=state, questions=q_set)
        except Exception as e:
            logger.error(f"Laya prediction failed for message {message.telegram_msg_id}: {e}")
            raise e

        decisions: List[LayaDecisionResult] = []
        answers = res.get("answers", {})
        routing = res.get("routing", {})

        for q_key, answer_data in answers.items():
            q_type = answer_data.get("type", "choice")
            if q_type == "choice":
                val = answer_data.get("choice")
            elif q_type == "noul":
                val = answer_data.get("noul")
            elif q_type == "score":
                val = answer_data.get("score")
            else:
                val = str(answer_data.get("value", ""))

            decisions.append(
                LayaDecisionResult(
                    target_type="message",
                    target_id=message.id or message.telegram_msg_id,
                    question_key=q_key,
                    decision_type=q_type,
                    result_value=val,
                    confidence=float(answer_data.get("confidence", 0.0)),
                    probabilities=answer_data.get("probabilities", {}),
                    routing_metadata=routing,
                )
            )

        return decisions

    def evaluate_dialogue(
        self,
        chat_id: int,
        dialogue_turns: List[Dict[str, str]],
        questions: Optional[Dict[str, Any]] = None,
    ) -> List[LayaDecisionResult]:
        """Evaluates a conversation snippet (turns of dialogue) and returns decisions."""
        q_set = questions or CONVERSATION_DYNAMIC_QUESTIONS
        formatted_dialogue = "\n".join(
            f"{turn.get('sender', 'User')}: {turn.get('text', '')}"
            for turn in dialogue_turns
        )

        state = {
            "dialogue": formatted_dialogue,
            "turns_count": len(dialogue_turns),
        }

        res = self.predict(state=state, questions=q_set)

        decisions: List[LayaDecisionResult] = []
        answers = res.get("answers", {})
        routing = res.get("routing", {})

        for q_key, answer_data in answers.items():
            q_type = answer_data.get("type", "choice")
            if q_type == "choice":
                val = answer_data.get("choice")
            elif q_type == "noul":
                val = answer_data.get("noul")
            elif q_type == "score":
                val = answer_data.get("score")
            else:
                val = str(answer_data.get("value", ""))

            decisions.append(
                LayaDecisionResult(
                    target_type="chat",
                    target_id=chat_id,
                    question_key=q_key,
                    decision_type=q_type,
                    result_value=val,
                    confidence=float(answer_data.get("confidence", 0.0)),
                    probabilities=answer_data.get("probabilities", {}),
                    routing_metadata=routing,
                )
            )

        return decisions


def get_decision_engine() -> LayaDecisionEngine:
    return LayaDecisionEngine.get_instance()
