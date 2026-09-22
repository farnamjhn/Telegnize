"""SQLite implementation of :class:`IChatRepository`."""

from datetime import datetime

from domain.models.chat import Chat
from domain.repository.chat_repository import IChatRepository
from infrastructure.persistence.database import Database


class SQLiteChatRepository(IChatRepository):
    def __init__(self, database: Database) -> None:
        self._db = database

    @staticmethod
    def _to_entity(row) -> Chat:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        return Chat(
            id=row["id"],
            telegram_chat_id=row["telegram_chat_id"],
            name=row["name"],
            type=row["type"],
            total_messages=row["total_messages"],
            created_at=created_at,
        )

    def save(self, chat: Chat) -> Chat:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO chats (telegram_chat_id, name, type, total_messages)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_chat_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    total_messages = EXCLUDED.total_messages
                RETURNING id, created_at;
                """,
                (chat.telegram_chat_id, chat.name, chat.type, chat.total_messages),
            ).fetchone()
        if row is not None:
            chat.id = row["id"]
        return chat

    def get_by_id(self, chat_id: int) -> Chat | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM chats WHERE id = ? LIMIT 1;", (chat_id,)
            ).fetchone()
        return self._to_entity(row) if row else None

    def get_by_telegram_id(self, telegram_chat_id: int) -> Chat | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM chats WHERE telegram_chat_id = ? LIMIT 1;",
                (telegram_chat_id,),
            ).fetchone()
        return self._to_entity(row) if row else None

    def list_all(self) -> list[Chat]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM chats ORDER BY id DESC;").fetchall()
        return [self._to_entity(row) for row in rows]

    def update_message_count(self, chat_id: int, count: int) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE chats SET total_messages = ? WHERE id = ?;", (count, chat_id)
            )

    def delete(self, chat_id: int) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute("DELETE FROM chats WHERE id = ?;", (chat_id,))
            return cursor.rowcount > 0
