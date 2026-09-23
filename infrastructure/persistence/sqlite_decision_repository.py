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

    # --- assessment bookkeeping ------------------------------------------
    def answered_message_ids(
        self, message_ids: Sequence[int], question_key: str
    ) -> set[int]:
        if not message_ids:
            return set()
        placeholders = ", ".join("?" * len(message_ids))
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT target_id FROM decisions "
                f"WHERE target_type = 'message' AND question_key = ? "
                f"AND target_id IN ({placeholders});",
                (question_key, *message_ids),
            ).fetchall()
        return {row["target_id"] for row in rows}

    def count_answered_in_chat(self, chat_id: int, question_key: str) -> int:
        with self._db.connect() as conn:
            return conn.execute(
                f"SELECT COUNT(*) {_JOIN_MESSAGES};",
                {"chat_id": chat_id, "question_key": question_key},
            ).fetchone()[0]

    def count_values_by_sender(
        self, chat_id: int, question_key: str
    ) -> dict[str, dict[str, int]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT m.sender_id AS sender_id, d.result_value AS value, "
                f"COUNT(*) AS total {_JOIN_MESSAGES} "
                f"GROUP BY m.sender_id, d.result_value;",
                {"chat_id": chat_id, "question_key": question_key},
            ).fetchall()

        counts: dict[str, dict[str, int]] = {}
        for row in rows:
            # Values are stored as JSON, so "positive" arrives quoted and a
            # noul arrives as true/false rather than a Python bool.
            value = _load_json(row["value"], default=row["value"])
            key = str(value).lower() if isinstance(value, bool) else str(value)
            counts.setdefault(row["sender_id"], {})[key] = row["total"]
        return counts

    def average_value_by_sender(
        self, chat_id: int, question_key: str
    ) -> dict[str, float]:
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT m.sender_id AS sender_id, "
                f"AVG(CAST(d.result_value AS REAL)) AS mean, COUNT(*) AS total "
                f"{_JOIN_MESSAGES} GROUP BY m.sender_id;",
                {"chat_id": chat_id, "question_key": question_key},
            ).fetchall()
        return {
            row["sender_id"]: float(row["mean"])
            for row in rows
            if row["mean"] is not None
        }


#: Decisions about messages are joined back to the message they describe, which
#: is what carries the chat and the sender.
_JOIN_MESSAGES = """
    FROM decisions d
    JOIN messages m ON m.id = d.target_id
    WHERE d.target_type = 'message'
      AND m.chat_id = :chat_id
      AND d.question_key = :question_key
"""


def _load_json(raw: Any, default: Any) -> Any:
    """Decodes a JSON column, falling back rather than failing a whole read."""
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Ignoring malformed JSON in decisions table: %r", raw)
        return default
