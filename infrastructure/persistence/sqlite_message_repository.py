"""SQLite implementation of :class:`IMessageRepository`."""

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

from domain.models.language import Language
from domain.models.message import ContentType, Message
from domain.repository.message_repository import IMessageRepository
from infrastructure.persistence.database import Database

_COLUMNS = (
    "chat_id, telegram_msg_id, sender_id, sender_name, timestamp, "
    "text_content, normalized_text, language, content_type, reply_to_msg_id, "
    "is_forwarded, word_count, char_count, is_question, is_cold_closure, "
    "exclamation_count, emoji_count, affection_count, apology_count, "
    "gratitude_count, self_reference_count, collective_reference_count"
)
_PLACEHOLDERS = ", ".join(f":{name.strip()}" for name in _COLUMNS.split(","))
_UPDATES = ", ".join(
    f"{name.strip()} = EXCLUDED.{name.strip()}"
    for name in _COLUMNS.split(",")
    if name.strip() not in ("chat_id", "telegram_msg_id")
)

_UPSERT = f"""
    INSERT INTO messages ({_COLUMNS}) VALUES ({_PLACEHOLDERS})
    ON CONFLICT(chat_id, telegram_msg_id) DO UPDATE SET {_UPDATES};
"""

# Latency of each message that answers someone else's turn.
#
# A message that replies to a message still in the chat is timed against that
# parent (within a day); otherwise it is timed against whatever came directly
# before it (within six hours), which is how a back-and-forth without explicit
# replies reads. Both run in SQL so a chat of any size costs constant memory.
_LATENCIES = """
    WITH ordered AS (
        SELECT
            id,
            sender_id,
            timestamp,
            reply_to_msg_id,
            LAG(sender_id) OVER turn AS prev_sender_id,
            LAG(timestamp) OVER turn AS prev_timestamp
        FROM messages
        WHERE chat_id = :chat_id
        WINDOW turn AS (ORDER BY timestamp, id)
    ),
    timed AS (
        SELECT
            o.sender_id AS sender_id,
            parent.sender_id IS NOT NULL AS answers_reply,
            CASE
                WHEN parent.sender_id IS NOT NULL AND parent.sender_id <> o.sender_id
                    THEN (julianday(o.timestamp) - julianday(parent.timestamp)) * 86400.0
                WHEN parent.sender_id IS NULL
                     AND o.prev_sender_id IS NOT NULL
                     AND o.prev_sender_id <> o.sender_id
                    THEN (julianday(o.timestamp) - julianday(o.prev_timestamp)) * 86400.0
            END AS latency
        FROM ordered o
        LEFT JOIN messages parent
            ON parent.chat_id = :chat_id
           AND parent.telegram_msg_id = o.reply_to_msg_id
    )
    SELECT sender_id, latency
    FROM timed
    WHERE latency IS NOT NULL
      AND latency >= 0
      AND latency <= CASE WHEN answers_reply THEN :reply_window ELSE :turn_window END;
"""

# Consecutive messages from one sender form a "burst": one uninterrupted turn.
# Several of the queries below are about turns rather than messages, so they all
# build on this fragment, which numbers every message's burst in one pass.
_BURSTS_CTE = """
    ordered AS (
        SELECT
            id,
            sender_id,
            timestamp,
            is_question,
            LAG(sender_id) OVER turn AS prev_sender_id
        FROM messages
        WHERE chat_id = :chat_id
        WINDOW turn AS (ORDER BY timestamp, id)
    ),
    bursts AS (
        SELECT
            *,
            SUM(
                CASE WHEN prev_sender_id IS NULL OR prev_sender_id <> sender_id
                     THEN 1 ELSE 0 END
            ) OVER (ORDER BY timestamp, id) AS burst_no
        FROM ordered
    )
"""

# Per sender: how many messages continue their own turn instead of answering.
# Writing again before the other person has said anything is the behaviour
# usually called double-texting.
_TURN_TAKING = f"""
    WITH {_BURSTS_CTE}
    SELECT
        sender_id,
        COUNT(*)                 AS message_count,
        COUNT(DISTINCT burst_no) AS burst_count,
        SUM(CASE WHEN prev_sender_id = sender_id THEN 1 ELSE 0 END) AS continuations
    FROM bursts
    GROUP BY sender_id;
"""

# Per sender: how many of their questions the other party picked up. A question
# counts as taken up when the next turn — which by definition belongs to someone
# else — starts inside the uptake window.
#
# That window is deliberately much tighter than the reply window. Measured over
# a day, a conversation of any density answers every question eventually and the
# figure pins at 100%, which says nothing; the question worth asking is whether
# someone responded while the question was still live.
_QUESTION_UPTAKE = f"""
    WITH {_BURSTS_CTE},
    burst_starts AS (
        SELECT burst_no, MIN(timestamp) AS started_at
        FROM bursts
        GROUP BY burst_no
    ),
    answered_at AS (
        SELECT burst_no, LEAD(started_at) OVER (ORDER BY burst_no) AS replied_at
        FROM burst_starts
    )
    SELECT
        b.sender_id AS sender_id,
        COUNT(*)    AS question_count,
        SUM(
            CASE WHEN a.replied_at IS NOT NULL
                  AND (julianday(a.replied_at) - julianday(b.timestamp)) * 86400.0
                      <= :uptake_window
                 THEN 1 ELSE 0 END
        ) AS answered_count
    FROM bursts b
    JOIN answered_at a ON a.burst_no = b.burst_no
    WHERE b.is_question = 1
    GROUP BY b.sender_id;
"""

# A session is a run of messages with no silence longer than :session_gap in it.
# Whoever sends the first message of one started that conversation; whoever
# sends the last had the final word.
_SESSION_BOUNDARIES = """
    WITH ordered AS (
        SELECT
            id,
            sender_id,
            timestamp,
            LAG(timestamp) OVER turn AS prev_timestamp,
            LEAD(timestamp) OVER turn AS next_timestamp
        FROM messages
        WHERE chat_id = :chat_id
        WINDOW turn AS (ORDER BY timestamp, id)
    ),
    marked AS (
        SELECT
            sender_id,
            CASE WHEN prev_timestamp IS NULL
                  OR (julianday(timestamp) - julianday(prev_timestamp)) * 86400.0
                     > :session_gap
                 THEN 1 ELSE 0 END AS opens_session,
            CASE WHEN next_timestamp IS NULL
                  OR (julianday(next_timestamp) - julianday(timestamp)) * 86400.0
                     > :session_gap
                 THEN 1 ELSE 0 END AS closes_session
        FROM ordered
    )
    SELECT
        sender_id,
        SUM(opens_session)  AS opened_count,
        SUM(closes_session) AS closed_count
    FROM marked
    GROUP BY sender_id;
"""

# Chat-level shape of the conversation over time.
_SESSION_SHAPE = """
    WITH ordered AS (
        SELECT
            id,
            timestamp,
            LAG(timestamp) OVER turn AS prev_timestamp
        FROM messages
        WHERE chat_id = :chat_id
        WINDOW turn AS (ORDER BY timestamp, id)
    ),
    numbered AS (
        SELECT
            timestamp,
            (julianday(timestamp) - julianday(prev_timestamp)) AS gap_days,
            SUM(
                CASE WHEN prev_timestamp IS NULL
                      OR (julianday(timestamp) - julianday(prev_timestamp)) * 86400.0
                         > :session_gap
                     THEN 1 ELSE 0 END
            ) OVER (ORDER BY timestamp, id) AS session_no
        FROM ordered
    ),
    per_session AS (
        SELECT
            session_no,
            COUNT(*) AS message_count,
            (julianday(MAX(timestamp)) - julianday(MIN(timestamp))) * 1440.0 AS minutes
        FROM numbered
        GROUP BY session_no
    )
    SELECT
        (SELECT COUNT(*) FROM per_session)                     AS session_count,
        (SELECT AVG(message_count) FROM per_session)           AS avg_session_messages,
        (SELECT AVG(minutes) FROM per_session)                 AS avg_session_minutes,
        (SELECT MAX(gap_days) FROM numbered)                   AS longest_silence_days,
        (SELECT COUNT(DISTINCT date(timestamp)) FROM numbered) AS active_days,
        (SELECT julianday(MAX(timestamp)) - julianday(MIN(timestamp)) FROM numbered)
                                                               AS span_days;
"""


# SQLite's %w is 0=Sunday; Telegnize reports weekday names.
_WEEKDAYS = (
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
)

#: Decimal places kept on a response latency, in seconds.
_LATENCY_PRECISION = 3

#: Longest gap still counted as answering an explicit reply, in seconds.
DEFAULT_REPLY_WINDOW_SECONDS = 24 * 60 * 60
#: Longest gap still counted as answering the previous turn, in seconds.
DEFAULT_TURN_WINDOW_SECONDS = 6 * 60 * 60
#: Silence long enough to treat what follows as a new conversation, in seconds.
DEFAULT_SESSION_GAP_SECONDS = 6 * 60 * 60
#: How long a question stays live for the purpose of counting it answered.
DEFAULT_UPTAKE_WINDOW_SECONDS = 60 * 60


class SQLiteMessageRepository(IMessageRepository):
    def __init__(
        self,
        database: Database,
        reply_window_seconds: int = DEFAULT_REPLY_WINDOW_SECONDS,
        turn_window_seconds: int = DEFAULT_TURN_WINDOW_SECONDS,
        session_gap_seconds: int = DEFAULT_SESSION_GAP_SECONDS,
        uptake_window_seconds: int = DEFAULT_UPTAKE_WINDOW_SECONDS,
    ) -> None:
        self._db = database
        self._reply_window = reply_window_seconds
        self._turn_window = turn_window_seconds
        self._session_gap = session_gap_seconds
        self._uptake_window = uptake_window_seconds

    # --- mapping ----------------------------------------------------------
    @staticmethod
    def _to_entity(row) -> Message:
        return Message(
            id=row["id"],
            chat_id=row["chat_id"],
            telegram_msg_id=row["telegram_msg_id"],
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            timestamp=_parse_timestamp(row["timestamp"]),
            text=row["text_content"] or "",
            normalized_text=row["normalized_text"] or row["text_content"] or "",
            language=Language.coerce(row["language"]),
            content_type=ContentType.coerce(row["content_type"]),
            reply_to_msg_id=row["reply_to_msg_id"],
            is_forwarded=bool(row["is_forwarded"]),
        )

    @staticmethod
    def _to_params(message: Message) -> dict[str, Any]:
        markers = message.markers
        return {
            "chat_id": message.chat_id or 1,
            "telegram_msg_id": message.telegram_msg_id,
            "sender_id": message.sender_id,
            "sender_name": message.sender_name,
            "timestamp": message.timestamp.isoformat(sep=" "),
            "text_content": message.text,
            "normalized_text": message.normalized_text,
            "language": str(message.language),
            "content_type": str(message.content_type),
            "reply_to_msg_id": message.reply_to_msg_id,
            "is_forwarded": int(message.is_forwarded),
            "word_count": message.word_count,
            "char_count": message.char_count,
            "is_question": int(message.is_question),
            "is_cold_closure": int(message.is_cold_closure),
            "exclamation_count": markers.exclamations,
            "emoji_count": markers.emoji,
            "affection_count": markers.affection,
            "apology_count": markers.apology,
            "gratitude_count": markers.gratitude,
            "self_reference_count": markers.self_reference,
            "collective_reference_count": markers.collective_reference,
        }

    # --- writes -----------------------------------------------------------
    def save(self, message: Message) -> None:
        with self._db.connect() as conn:
            conn.execute(_UPSERT, self._to_params(message))

    def save_batch(self, messages: Sequence[Message]) -> int:
        if not messages:
            return 0
        params = [self._to_params(message) for message in messages]
        with self._db.connect() as conn:
            conn.executemany(_UPSERT, params)
        return len(params)

    # --- reads ------------------------------------------------------------
    def get_by_id(self, message_id: int) -> Message | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?;", (message_id,)
            ).fetchone()
        return self._to_entity(row) if row else None

    def get_by_telegram_id(
        self, telegram_msg_id: int, chat_id: int | None = None
    ) -> Message | None:
        sql = "SELECT * FROM messages WHERE telegram_msg_id = ?"
        params: list[Any] = [telegram_msg_id]
        if chat_id is not None:
            sql += " AND chat_id = ?"
            params.append(chat_id)
        with self._db.connect() as conn:
            row = conn.execute(f"{sql} LIMIT 1;", params).fetchone()
        return self._to_entity(row) if row else None

    def list_messages(
        self,
        chat_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        sender_id: str | None = None,
    ) -> list[Message]:
        sql = "SELECT * FROM messages"
        filters: list[str] = []
        params: list[Any] = []
        if chat_id is not None:
            filters.append("chat_id = ?")
            params.append(chat_id)
        if sender_id is not None:
            filters.append("sender_id = ?")
            params.append(sender_id)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY timestamp ASC, id ASC LIMIT ? OFFSET ?;"
        params += [limit, offset]

        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._to_entity(row) for row in rows]

    def iter_chat_timeline(self, chat_id: int) -> Iterator[Message]:
        with self._db.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? "
                "ORDER BY timestamp ASC, id ASC;",
                (chat_id,),
            )
            for row in cursor:
                yield self._to_entity(row)

    # --- aggregates -------------------------------------------------------
    def count_by_chat(self, chat_id: int) -> int:
        with self._db.connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM messages WHERE chat_id = ?;", (chat_id,)
            ).fetchone()[0]

    def get_date_range(self, chat_id: int) -> tuple[str | None, str | None]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM messages "
                "WHERE chat_id = ?;",
                (chat_id,),
            ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def get_participant_totals(self, chat_id: int) -> list[dict[str, object]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    sender_id,
                    MAX(sender_name)      AS sender_name,
                    COUNT(*)              AS message_count,
                    SUM(word_count)       AS word_count,
                    SUM(char_count)       AS char_count,
                    SUM(is_question)      AS question_count,
                    SUM(is_cold_closure)  AS cold_closure_count,
                    SUM(exclamation_count)          AS exclamation_count,
                    SUM(emoji_count)                AS emoji_count,
                    SUM(affection_count)            AS affection_count,
                    SUM(apology_count)              AS apology_count,
                    SUM(gratitude_count)            AS gratitude_count,
                    SUM(self_reference_count)       AS self_reference_count,
                    SUM(collective_reference_count) AS collective_reference_count,
                    SUM(content_type = 'voice_message')                AS voice_count,
                    SUM(content_type NOT IN ('text', 'voice_message')) AS media_count
                FROM messages
                WHERE chat_id = ?
                GROUP BY sender_id
                ORDER BY message_count DESC;
                """,
                (chat_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_hourly_distribution(self, chat_id: int) -> dict[int, int]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour, "
                "COUNT(*) AS total FROM messages WHERE chat_id = ? "
                "GROUP BY hour ORDER BY hour;",
                (chat_id,),
            ).fetchall()
        return {row["hour"]: row["total"] for row in rows if row["hour"] is not None}

    def get_daily_distribution(self, chat_id: int) -> dict[str, int]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT CAST(strftime('%w', timestamp) AS INTEGER) AS weekday, "
                "COUNT(*) AS total FROM messages WHERE chat_id = ? "
                "GROUP BY weekday ORDER BY weekday;",
                (chat_id,),
            ).fetchall()
        return {
            _WEEKDAYS[row["weekday"]]: row["total"]
            for row in rows
            if row["weekday"] is not None
        }

    def get_language_distribution(self, chat_id: int) -> dict[str, int]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT language, COUNT(*) AS total FROM messages "
                "WHERE chat_id = ? GROUP BY language;",
                (chat_id,),
            ).fetchall()
        return {row["language"]: row["total"] for row in rows}

    def get_turn_taking(self, chat_id: int) -> dict[str, dict[str, int]]:
        with self._db.connect() as conn:
            rows = conn.execute(_TURN_TAKING, {"chat_id": chat_id}).fetchall()
        return {row["sender_id"]: dict(row) for row in rows}

    def get_question_uptake(self, chat_id: int) -> dict[str, dict[str, int]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                _QUESTION_UPTAKE,
                {"chat_id": chat_id, "uptake_window": self._uptake_window},
            ).fetchall()
        return {row["sender_id"]: dict(row) for row in rows}

    def get_session_boundaries(self, chat_id: int) -> dict[str, dict[str, int]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                _SESSION_BOUNDARIES,
                {"chat_id": chat_id, "session_gap": self._session_gap},
            ).fetchall()
        return {row["sender_id"]: dict(row) for row in rows}

    def get_session_shape(self, chat_id: int) -> dict[str, float | None]:
        with self._db.connect() as conn:
            row = conn.execute(
                _SESSION_SHAPE,
                {"chat_id": chat_id, "session_gap": self._session_gap},
            ).fetchone()
        return dict(row) if row else {}

    def get_response_latencies(self, chat_id: int) -> dict[str, list[float]]:
        # julianday() works in fractional days, so the seconds it yields carry
        # float noise well below the resolution a reply latency means anything
        # at; round it off rather than leaking 59.99999 into every statistic.
        latencies: dict[str, list[float]] = {}
        with self._db.connect() as conn:
            rows = conn.execute(
                _LATENCIES,
                {
                    "chat_id": chat_id,
                    "reply_window": self._reply_window,
                    "turn_window": self._turn_window,
                },
            )
            for row in rows:
                latencies.setdefault(row["sender_id"], []).append(
                    round(float(row["latency"]), _LATENCY_PRECISION)
                )
        return latencies


def _parse_timestamp(value: Any) -> datetime:
    """Reads a timestamp column, which SQLite hands back as text."""
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
