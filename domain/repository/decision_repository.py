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
