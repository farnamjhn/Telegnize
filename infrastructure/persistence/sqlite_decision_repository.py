"""SQLite implementation of :class:`IDecisionRepository`."""

import json
import logging
from collections.abc import Sequence
from typing import Any

from domain.models.analysis import Decision, DecisionTarget, DecisionType
from domain.repository.decision_repository import IDecisionRepository
from infrastructure.persistence.database import Database

logger = logging.getLogger(__name__)

_UPSERT = """
    INSERT INTO decisions (
        target_type, target_id, question_key, decision_type,
        result_value, confidence, probabilities, engine_metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(target_type, target_id, question_key) DO UPDATE SET
        decision_type   = EXCLUDED.decision_type,
        result_value    = EXCLUDED.result_value,
        confidence      = EXCLUDED.confidence,
        probabilities   = EXCLUDED.probabilities,
        engine_metadata = EXCLUDED.engine_metadata,
        created_at      = CURRENT_TIMESTAMP;
"""


class SQLiteDecisionRepository(IDecisionRepository):
    def __init__(self, database: Database) -> None:
        self._db = database

    @staticmethod
    def _to_params(decision: Decision) -> tuple:
        return (
            str(decision.target_type),
            decision.target_id,
            decision.question_key,
            str(decision.decision_type),
            json.dumps(decision.result_value),
            decision.confidence,
            json.dumps(decision.probabilities),
            json.dumps(decision.engine_metadata, default=str),
        )

    @staticmethod
    def _to_entity(row) -> Decision:
        return Decision(
            target_type=DecisionTarget(row["target_type"]),
            target_id=row["target_id"],
            question_key=row["question_key"],
            decision_type=DecisionType.coerce(row["decision_type"]),
            result_value=_load_json(row["result_value"], default=row["result_value"]),
            confidence=float(row["confidence"] or 0.0),
            probabilities=_load_json(row["probabilities"], default={}),
            engine_metadata=_load_json(row["engine_metadata"], default={}),
        )

    def save(self, decision: Decision) -> None:
        with self._db.connect() as conn:
            conn.execute(_UPSERT, self._to_params(decision))

    def save_batch(self, decisions: Sequence[Decision]) -> None:
        if not decisions:
            return
        with self._db.connect() as conn:
            conn.executemany(_UPSERT, [self._to_params(d) for d in decisions])

    def list_for_target(
        self, target_type: DecisionTarget, target_id: int
    ) -> list[Decision]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE target_type = ? AND target_id = ? "
                "ORDER BY question_key;",
                (str(target_type), target_id),
            ).fetchall()
        return [self._to_entity(row) for row in rows]


def _load_json(raw: Any, default: Any) -> Any:
    """Decodes a JSON column, falling back rather than failing a whole read."""
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Ignoring malformed JSON in decisions table: %r", raw)
        return default
