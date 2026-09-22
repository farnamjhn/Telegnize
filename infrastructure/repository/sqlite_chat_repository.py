import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from domain.models.chat import Chat
from domain.repository.chat_repository import IChatRepository


class SQLiteChatRepository(IChatRepository):
    def __init__(self, db_path: str = "identifier.sqlite"):
        self.db_path = db_path
        self._shared_connection: Optional[sqlite3.Connection] = None
        self._init_db()

    @contextmanager
    def _get_connection(self):
        if self.db_path == ":memory:":
            if self._shared_connection is None:
                self._shared_connection = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared_connection.row_factory = sqlite3.Row
                self._shared_connection.execute("PRAGMA foreign_keys = ON;")
            with self._shared_connection as conn:
                yield conn
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def _init_db(self) -> None:
        schema_path = Path(__file__).parent.parent / "presistence" / "schema.sql"
        with self._get_connection() as conn:
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
                """)

    def _to_entity(self, row: sqlite3.Row) -> Chat:
        created_at_raw = row["created_at"]
        if isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = None
        else:
            created_at = created_at_raw

        return Chat(
            id=row["id"],
            telegram_chat_id=row["telegram_chat_id"],
            name=row["name"],
            type=row["type"],
            total_messages=row["total_messages"],
            created_at=created_at,
        )

    def save(self, chat: Chat) -> Chat:
        query = """
            INSERT INTO chats (telegram_chat_id, name, type, total_messages)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_chat_id) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                total_messages = EXCLUDED.total_messages
            RETURNING id;
        """
        with self._get_connection() as conn:
            cur = conn.execute(
                query,
                (chat.telegram_chat_id, chat.name, chat.type, chat.total_messages),
            )
            row = cur.fetchone()
            if row:
                chat.id = row[0]
            return chat

    def get_by_id(self, chat_id: int) -> Optional[Chat]:
        query = "SELECT * FROM chats WHERE id = ? LIMIT 1;"
        with self._get_connection() as conn:
            row = conn.execute(query, (chat_id,)).fetchone()
            return self._to_entity(row) if row else None

    def get_by_telegram_id(self, telegram_chat_id: int) -> Optional[Chat]:
        query = "SELECT * FROM chats WHERE telegram_chat_id = ? LIMIT 1;"
        with self._get_connection() as conn:
            row = conn.execute(query, (telegram_chat_id,)).fetchone()
            return self._to_entity(row) if row else None

    def list_all(self) -> List[Chat]:
        query = "SELECT * FROM chats ORDER BY id DESC;"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [self._to_entity(r) for r in rows]

    def update_message_count(self, chat_id: int, count: int) -> None:
        query = "UPDATE chats SET total_messages = ? WHERE id = ?;"
        with self._get_connection() as conn:
            conn.execute(query, (count, chat_id))

    def delete(self, chat_id: int) -> bool:
        query = "DELETE FROM chats WHERE id = ?;"
        with self._get_connection() as conn:
            cur = conn.execute(query, (chat_id,))
            return cur.rowcount > 0

    def close(self) -> None:
        if self._shared_connection:
            self._shared_connection.close()
            self._shared_connection = None
