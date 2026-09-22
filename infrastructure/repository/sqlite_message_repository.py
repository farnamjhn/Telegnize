import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.models.message import ContentType, Message, MessageId
from domain.models.analysis import LayaDecisionResult
from domain.repository.message_repository import IMessageRepository


class SQLiteMessageRepository(IMessageRepository):
    def __init__(self, db_path: str = "identifier.sqlite"):
        self.db_path = db_path
        self._shared_connection: Optional[sqlite3.Connection] = None
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Create and configure a SQLite connection contextmanager."""
        if self.db_path == ":memory:":
            if self._shared_connection is None:
                self._shared_connection = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared_connection.row_factory = sqlite3.Row
                self._shared_connection.execute("PRAGMA journal_mode = WAL;")
                self._shared_connection.execute("PRAGMA foreign_keys = ON;")
            with self._shared_connection as conn:
                yield conn
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def _init_db(self) -> None:
        """Ensure required tables and indexes exist with migration support."""
        schema_path = Path(__file__).parent.parent / "presistence" / "schema.sql"
        with self._get_connection() as conn:
            # Check existing messages table columns if table exists
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
            if cur.fetchone():
                cols = [r[1] for r in conn.execute("PRAGMA table_info(messages);").fetchall()]
                if "chat_id" not in cols:
                    conn.execute("ALTER TABLE messages ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 1;")
                if "normalized_text" not in cols:
                    conn.execute("ALTER TABLE messages ADD COLUMN normalized_text TEXT;")
                if "language" not in cols:
                    conn.execute("ALTER TABLE messages ADD COLUMN language TEXT DEFAULT 'unknown';")
                if "content_type" not in cols:
                    conn.execute("ALTER TABLE messages ADD COLUMN content_type TEXT NOT NULL DEFAULT 'text';")

            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
            else:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS chats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_chat_id INTEGER UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL DEFAULT 'personal_chat',
                        total_messages INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL DEFAULT 1,
                        telegram_msg_id INTEGER NOT NULL,
                        sender_id TEXT NOT NULL,
                        sender_name TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        text_content TEXT,
                        normalized_text TEXT,
                        language TEXT DEFAULT 'unknown',
                        content_type TEXT NOT NULL DEFAULT 'text',
                        reply_to_msg_id INTEGER,
                        is_forwarded BOOLEAN DEFAULT 0,
                        word_count INTEGER DEFAULT 0,
                        char_count INTEGER DEFAULT 0,
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                        UNIQUE(chat_id, telegram_msg_id)
                    );
                """)
            # Ensure default chat exists for standalone messages or tests without explicit chat
            conn.execute("""
                INSERT OR IGNORE INTO chats (id, telegram_chat_id, name, type)
                VALUES (1, 0, 'Default Chat', 'personal_chat');
            """)

    def _to_entity(self, row: sqlite3.Row) -> Message:
        """Helper mapper: SQLite Row -> Domain Message Entity."""
        raw_ts = row["timestamp"]
        if isinstance(raw_ts, str):
            try:
                parsed_ts = datetime.fromisoformat(raw_ts)
            except ValueError:
                parsed_ts = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        else:
            parsed_ts = raw_ts

        reply_to_msg_id = row["reply_to_msg_id"]
        reply_id = MessageId(reply_to_msg_id) if reply_to_msg_id is not None else None

        content_type_val = row["content_type"]
        try:
            content_type = ContentType(content_type_val)
        except ValueError:
            content_type = ContentType.TEXT

        raw_text = row["text_content"] or ""
        norm_text = row["normalized_text"] if "normalized_text" in row.keys() else raw_text

        return Message(
            id=row["id"],
            telegram_msg_id=row["telegram_msg_id"],
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            reply_to_msg_id=reply_to_msg_id,
            timestamp=parsed_ts,
            text=raw_text,
            content_type=content_type,
            reply_to_id=reply_id,
            is_forwarded=bool(row["is_forwarded"]),
            chat_id=row["chat_id"] if "chat_id" in row.keys() else 1,
            raw_text=raw_text,
            normalized_text=norm_text or raw_text,
            language=row["language"] if "language" in row.keys() else "unknown",
        )

    def _to_params(self, message: Message) -> Dict[str, Any]:
        """Helper mapper: Domain Message Entity -> Parameter dictionary."""
        tg_id = message.telegram_msg_id if hasattr(message, "telegram_msg_id") else message.id
        if isinstance(tg_id, MessageId):
            tg_id = tg_id.value

        if message.reply_to_msg_id is not None:
            reply_id_val = message.reply_to_msg_id
        elif message.reply_to_id is not None:
            reply_id_val = message.reply_to_id.value if isinstance(message.reply_to_id, MessageId) else message.reply_to_id
        else:
            reply_id_val = None

        ts_str = message.timestamp.isoformat() if isinstance(message.timestamp, datetime) else str(message.timestamp)
        ct_str = message.content_type.value if isinstance(message.content_type, ContentType) else str(message.content_type)

        chat_id_val = getattr(message, "chat_id", 1) or 1
        raw_text = message.raw_text or message.text or ""
        norm_text = message.normalized_text or raw_text
        lang = getattr(message, "language", "unknown") or "unknown"

        return {
            "chat_id": chat_id_val,
            "telegram_msg_id": tg_id,
            "sender_id": message.sender_id,
            "sender_name": message.sender_name,
            "timestamp": ts_str,
            "text_content": raw_text,
            "normalized_text": norm_text,
            "language": lang,
            "content_type": ct_str,
            "reply_to_msg_id": reply_id_val,
            "is_forwarded": int(bool(message.is_forwarded)),
            "word_count": message.word_count,
            "char_count": message.char_count,
        }

    def save(self, message: Message) -> None:
        query = """
            INSERT INTO messages (
                chat_id, telegram_msg_id, sender_id, sender_name, timestamp,
                text_content, normalized_text, language, content_type,
                reply_to_msg_id, is_forwarded, word_count, char_count
            ) VALUES (
                :chat_id, :telegram_msg_id, :sender_id, :sender_name, :timestamp,
                :text_content, :normalized_text, :language, :content_type,
                :reply_to_msg_id, :is_forwarded, :word_count, :char_count
            )
            ON CONFLICT(chat_id, telegram_msg_id) DO UPDATE SET
                sender_id = EXCLUDED.sender_id,
                sender_name = EXCLUDED.sender_name,
                timestamp = EXCLUDED.timestamp,
                text_content = EXCLUDED.text_content,
                normalized_text = EXCLUDED.normalized_text,
                language = EXCLUDED.language,
                content_type = EXCLUDED.content_type,
                reply_to_msg_id = EXCLUDED.reply_to_msg_id,
                is_forwarded = EXCLUDED.is_forwarded,
                word_count = EXCLUDED.word_count,
                char_count = EXCLUDED.char_count;
        """
        with self._get_connection() as conn:
            conn.execute(query, self._to_params(message))

    def save_batch(self, messages: List[Message]) -> None:
        if not messages:
            return

        query = """
            INSERT INTO messages (
                chat_id, telegram_msg_id, sender_id, sender_name, timestamp,
                text_content, normalized_text, language, content_type,
                reply_to_msg_id, is_forwarded, word_count, char_count
            ) VALUES (
                :chat_id, :telegram_msg_id, :sender_id, :sender_name, :timestamp,
                :text_content, :normalized_text, :language, :content_type,
                :reply_to_msg_id, :is_forwarded, :word_count, :char_count
            )
            ON CONFLICT(chat_id, telegram_msg_id) DO UPDATE SET
                sender_id = EXCLUDED.sender_id,
                sender_name = EXCLUDED.sender_name,
                timestamp = EXCLUDED.timestamp,
                text_content = EXCLUDED.text_content,
                normalized_text = EXCLUDED.normalized_text,
                language = EXCLUDED.language,
                content_type = EXCLUDED.content_type,
                reply_to_msg_id = EXCLUDED.reply_to_msg_id,
                is_forwarded = EXCLUDED.is_forwarded,
                word_count = EXCLUDED.word_count,
                char_count = EXCLUDED.char_count;
        """
        params = [self._to_params(msg) for msg in messages]
        with self._get_connection() as conn:
            conn.executemany(query, params)

    def get_by_id(self, message_id: int) -> Optional[Message]:
        query = "SELECT * FROM messages WHERE id = ? LIMIT 1;"
        with self._get_connection() as conn:
            row = conn.execute(query, (message_id,)).fetchone()
            return self._to_entity(row) if row else None

    def get_by_telegram_id(self, message_telegram_id: int, chat_id: Optional[int] = None) -> Optional[Message]:
        if chat_id is not None:
            query = "SELECT * FROM messages WHERE telegram_msg_id = ? AND chat_id = ? LIMIT 1;"
            params = (message_telegram_id, chat_id)
        else:
            query = "SELECT * FROM messages WHERE telegram_msg_id = ? LIMIT 1;"
            params = (message_telegram_id,)

        with self._get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return self._to_entity(row) if row else None

    def get_all_orderd(self) -> List[Message]:
        query = "SELECT * FROM messages ORDER BY timestamp ASC;"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [self._to_entity(row) for row in rows]

    def get_all_ordered(self) -> List[Message]:
        return self.get_all_orderd()

    def get_by_chat(
        self,
        chat_id: int,
        limit: int = 100,
        offset: int = 0,
        sender_id: Optional[str] = None,
    ) -> List[Message]:
        if sender_id:
            query = """
                SELECT * FROM messages
                WHERE chat_id = ? AND sender_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?;
            """
            params = (chat_id, sender_id, limit, offset)
        else:
            query = """
                SELECT * FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?;
            """
            params = (chat_id, limit, offset)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._to_entity(r) for r in rows]

    def count_by_chat(self, chat_id: int) -> int:
        query = "SELECT COUNT(*) FROM messages WHERE chat_id = ?;"
        with self._get_connection() as conn:
            cur = conn.execute(query, (chat_id,))
            return cur.fetchone()[0]

    def get_chat_timeline(self, chat_id: int) -> List[Message]:
        query = "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp ASC;"
        with self._get_connection() as conn:
            rows = conn.execute(query, (chat_id,)).fetchall()
            return [self._to_entity(r) for r in rows]

    def get_participants_summary(self, chat_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT
                sender_id,
                sender_name,
                COUNT(*) as msg_count,
                SUM(word_count) as total_words,
                SUM(char_count) as total_chars
            FROM messages
            WHERE chat_id = ?
            GROUP BY sender_id, sender_name
            ORDER BY msg_count DESC;
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (chat_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_hourly_activity(self, chat_id: int) -> Dict[int, int]:
        query = """
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as cnt
            FROM messages
            WHERE chat_id = ?
            GROUP BY hour
            ORDER BY hour ASC;
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (chat_id,)).fetchall()
            return {int(r["hour"]): int(r["cnt"]) for r in rows if r["hour"] is not None}

    def get_language_distribution(self, chat_id: int) -> Dict[str, int]:
        query = """
            SELECT language, COUNT(*) as cnt
            FROM messages
            WHERE chat_id = ?
            GROUP BY language;
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (chat_id,)).fetchall()
            return {str(r["language"]): int(r["cnt"]) for r in rows}

    def save_laya_decision(self, decision: LayaDecisionResult) -> None:
        query = """
            INSERT INTO laya_decisions (
                target_type, target_id, question_key, decision_type,
                result_value, confidence, probabilities
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_type, target_id, question_key) DO UPDATE SET
                decision_type = EXCLUDED.decision_type,
                result_value = EXCLUDED.result_value,
                confidence = EXCLUDED.confidence,
                probabilities = EXCLUDED.probabilities,
                created_at = CURRENT_TIMESTAMP;
        """
        with self._get_connection() as conn:
            conn.execute(
                query,
                (
                    decision.target_type,
                    decision.target_id,
                    decision.question_key,
                    decision.decision_type,
                    str(decision.result_value),
                    decision.confidence,
                    json.dumps(decision.probabilities),
                ),
            )

    def get_laya_decisions(self, target_type: str, target_id: int) -> List[LayaDecisionResult]:
        query = "SELECT * FROM laya_decisions WHERE target_type = ? AND target_id = ?;"
        with self._get_connection() as conn:
            rows = conn.execute(query, (target_type, target_id)).fetchall()
            results = []
            for r in rows:
                probs = {}
                if r["probabilities"]:
                    try:
                        probs = json.loads(r["probabilities"])
                    except Exception:
                        pass
                results.append(
                    LayaDecisionResult(
                        target_type=r["target_type"],
                        target_id=r["target_id"],
                        question_key=r["question_key"],
                        decision_type=r["decision_type"],
                        result_value=r["result_value"],
                        confidence=float(r["confidence"]) if r["confidence"] is not None else 0.0,
                        probabilities=probs,
                    )
                )
            return results

    def close(self) -> None:
        if self._shared_connection:
            self._shared_connection.close()
            self._shared_connection = None
