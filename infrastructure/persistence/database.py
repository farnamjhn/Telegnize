"""SQLite connection management and schema setup.

A single ``Database`` owns the schema and hands out connections; repositories
hold one and borrow a connection per operation. Before this existed each
repository opened its own connection *and* re-ran the whole DDL script on every
construction, which meant once per HTTP request, and repositories pointed at
``:memory:`` could not see each other's tables.
"""

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

MEMORY_PATH = ":memory:"

_SCHEMA_FILE = Path(__file__).with_name("schema.sql")

# Columns added after the first release, applied to databases created earlier.
# Each entry is (table, column, DDL fragment).
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("messages", "chat_id", "INTEGER NOT NULL DEFAULT 1"),
    ("messages", "normalized_text", "TEXT NOT NULL DEFAULT ''"),
    ("messages", "language", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("messages", "content_type", "TEXT NOT NULL DEFAULT 'text'"),
    ("messages", "word_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "char_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "is_question", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "is_cold_closure", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "exclamation_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "emoji_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "affection_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "apology_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "gratitude_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "self_reference_count", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "collective_reference_count", "INTEGER NOT NULL DEFAULT 0"),
    ("decisions", "engine_metadata", "TEXT NOT NULL DEFAULT '{}'"),
]


class Database:
    """Owns a SQLite database file and the connections onto it.

    File-backed databases get a fresh connection per operation, so the object is
    safe to share across FastAPI's worker threads. ``:memory:`` databases keep
    one shared connection instead, because a second connection would open a
    second, empty database.
    """

    def __init__(self, path: str = MEMORY_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._memory_connection: sqlite3.Connection | None = None
        self._initialize()

    # --- connections ------------------------------------------------------
    @property
    def is_in_memory(self) -> bool:
        return self.path == MEMORY_PATH

    def _new_connection(self) -> sqlite3.Connection:
        if not self.is_in_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.path,
            check_same_thread=not self.is_in_memory,
            isolation_level="DEFERRED",
        )
        conn.row_factory = sqlite3.Row
        if not self.is_in_memory:
            # WAL lets readers run while a batch import writes. It is a no-op
            # for in-memory databases, which reject it on some builds.
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yields a connection wrapped in a transaction.

        The transaction commits on a clean exit and rolls back on an exception.
        """
        if self.is_in_memory:
            with self._lock:
                if self._memory_connection is None:
                    self._memory_connection = self._new_connection()
                with self._memory_connection as conn:
                    yield conn
            return

        conn = self._new_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # --- schema -----------------------------------------------------------
    def _initialize(self) -> None:
        """Creates the schema and brings older database files up to date."""
        with self.connect() as conn:
            self._rename_legacy_tables(conn)
            conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
            self._apply_column_migrations(conn)

    @staticmethod
    def _rename_legacy_tables(conn: sqlite3.Connection) -> None:
        """Renames pre-0.3 tables so the schema script can take over."""
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }
        if "laya_decisions" in existing and "decisions" not in existing:
            logger.info("Migrating table 'laya_decisions' to 'decisions'.")
            conn.execute("ALTER TABLE laya_decisions RENAME TO decisions;")

    @staticmethod
    def _apply_column_migrations(conn: sqlite3.Connection) -> None:
        """Adds columns missing from databases created by an earlier version."""
        for table, column, ddl in _MIGRATIONS:
            columns = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table});")
            }
            if not columns:  # table does not exist yet
                continue
            if column not in columns:
                logger.info("Adding column %s.%s.", table, column)
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl};")

    # --- lifecycle --------------------------------------------------------
    def close(self) -> None:
        """Closes the shared in-memory connection, if there is one."""
        with self._lock:
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None
