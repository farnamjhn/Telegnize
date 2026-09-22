"""Port for the decision cache.

Decisions are model output rather than user data, so they live behind their own
port: caching them is an optimisation, and losing the cache costs only time.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from domain.models.analysis import Decision, DecisionTarget


class IDecisionRepository(ABC):
    @abstractmethod
    def save(self, decision: Decision) -> None:
        """Stores a decision, replacing any previous answer to the same question."""

    @abstractmethod
    def save_batch(self, decisions: Sequence[Decision]) -> None:
        """Stores several decisions in one transaction."""

    @abstractmethod
    def list_for_target(
        self, target_type: DecisionTarget, target_id: int
    ) -> list[Decision]:
        """Lists cached decisions about one message or chat."""

    # --- assessment bookkeeping ------------------------------------------
    # These read decisions about a chat's messages in bulk. They reach across
    # to the messages table, because "which of this chat's messages still need
    # answering" and "how did each sender's answers come out" are questions the
    # decisions alone cannot answer.
    @abstractmethod
    def answered_message_ids(
        self, message_ids: Sequence[int], question_key: str
    ) -> set[int]:
        """Which of these messages already have an answer to this question."""

    @abstractmethod
    def count_answered_in_chat(self, chat_id: int, question_key: str) -> int:
        """How many of a chat's messages have an answer to this question."""

    @abstractmethod
    def count_values_by_sender(
        self, chat_id: int, question_key: str
    ) -> dict[str, dict[str, int]]:
        """Per sender, how often each answer to this question came up."""

    @abstractmethod
    def average_value_by_sender(
        self, chat_id: int, question_key: str
    ) -> dict[str, float]:
        """Per sender, the mean numeric answer to a score question."""
