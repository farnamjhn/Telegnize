import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Any, Dict
from pathlib import Path

from domain.models.message import Message, ContentType, MessageId
from domain.repository.message_repository import IMessageRepository


class SQLiteMessageRepository(IMessageRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._shared_connection: Optional[sqlite3.Connection] = None
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Create and configure a SQLite connection contextmanager."""
        if self.db_path == ":memory:":
            if self._shared_connection is None:
                self._shared_connection = sqlite3.connect(":memory:")
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
        """Ensure required tables and indexes exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_msg_id INTEGER UNIQUE NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    text_content TEXT,
                    content_type TEXT NOT NULL DEFAULT 'text',
                    reply_to_msg_id INTEGER,
                    is_forwarded BOOLEAN DEFAULT 0,
                    word_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
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
        reply_id = (
            MessageId(reply_to_msg_id)
            if reply_to_msg_id is not None
            else None
        )

        content_type_val = row["content_type"]
        try:
            content_type = ContentType(content_type_val)
        except ValueError:
            content_type = ContentType.TEXT

        return Message(
            id=row["id"],
            telegram_msg_id=row["telegram_msg_id"],
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            reply_to_msg_id=reply_to_msg_id,
            timestamp=parsed_ts,
            text=row["text_content"] or "",
            content_type=content_type,
            reply_to_id=reply_id,
            is_forwarded=bool(row["is_forwarded"])
        )

    def _to_params(self, message: Message) -> Dict[str, Any]:
        """Helper mapper: Domain Message Entity -> Parameter dictionary."""
        if hasattr(message, "telegram_msg_id") and message.telegram_msg_id is not None:
            tg_id = message.telegram_msg_id
        elif isinstance(message.id, MessageId):
            tg_id = message.id.value
        else:
            tg_id = message.id

        if hasattr(message, "reply_to_msg_id") and message.reply_to_msg_id is not None:
            reply_id_val = message.reply_to_msg_id
        elif message.reply_to_id is not None:
            reply_id_val = message.reply_to_id.value if isinstance(message.reply_to_id, MessageId) else message.reply_to_id
        else:
            reply_id_val = None

        if isinstance(message.timestamp, datetime):
            ts_str = message.timestamp.isoformat()
        else:
            ts_str = str(message.timestamp)

        if isinstance(message.content_type, ContentType):
            ct_str = message.content_type.value
        else:
            ct_str = str(message.content_type)

        return {
            "telegram_msg_id": tg_id,
            "sender_id": message.sender_id,
            "sender_name": message.sender_name,
            "timestamp": ts_str,
            "text_content": message.text or "",
            "content_type": ct_str,
            "reply_to_msg_id": reply_id_val,
            "is_forwarded": int(bool(message.is_forwarded)),
            "word_count": message.word_count,
            "char_count": message.char_count
        }

    def save(self, message: Message) -> None:
        query = """
            INSERT INTO messages (
                telegram_msg_id, sender_id, sender_name, timestamp,
                text_content, content_type, reply_to_msg_id, is_forwarded,
                word_count, char_count
            ) VALUES (
                :telegram_msg_id, :sender_id, :sender_name, :timestamp,
                :text_content, :content_type, :reply_to_msg_id, :is_forwarded,
                :word_count, :char_count
            )
            ON CONFLICT(telegram_msg_id) DO UPDATE SET
                sender_id = EXCLUDED.sender_id,
                sender_name = EXCLUDED.sender_name,
                timestamp = EXCLUDED.timestamp,
                text_content = EXCLUDED.text_content,
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
                telegram_msg_id, sender_id, sender_name, timestamp,
                text_content, content_type, reply_to_msg_id, is_forwarded,
                word_count, char_count
            ) VALUES (
                :telegram_msg_id, :sender_id, :sender_name, :timestamp,
                :text_content, :content_type, :reply_to_msg_id, :is_forwarded,
                :word_count, :char_count
            )
            ON CONFLICT(telegram_msg_id) DO UPDATE SET
                sender_id = EXCLUDED.sender_id,
                sender_name = EXCLUDED.sender_name,
                timestamp = EXCLUDED.timestamp,
                text_content = EXCLUDED.text_content,
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

    def get_by_telegram_id(self, message_telegram_id: int) -> Optional[Message]:
        query = "SELECT * FROM messages WHERE telegram_msg_id = ? LIMIT 1;"
        with self._get_connection() as conn:
            row = conn.execute(query, (message_telegram_id,)).fetchone()
            return self._to_entity(row) if row else None

    def get_all_orderd(self) -> List[Message]:
        query = "SELECT * FROM messages ORDER BY timestamp ASC;"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [self._to_entity(row) for row in rows]

    def get_all_ordered(self) -> List[Message]:
        """Alias for get_all_orderd to support correct spelling."""
        return self.get_all_orderd()

    def close(self) -> None:
        if self._shared_connection:
            self._shared_connection.close()
            self._shared_connection = None

