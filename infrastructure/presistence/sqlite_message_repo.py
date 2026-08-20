import sqlite3
from pathlib import Path


class SQLiteMessageRepository:
    _db_path: str
    def __init__(self, db_path: str = "chat_analysis.db") :
        self._db_path = db_path

    def _init_db(self):
        schema_path = Path(__file__).parent / "schema.sql"
        with sqlite3.connect(self._db_path) as conn:
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
