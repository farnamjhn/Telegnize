"""Shared test fixtures."""

from infrastructure.api.container import Container
from infrastructure.config import Settings
from infrastructure.persistence.database import MEMORY_PATH


def memory_container(**overrides) -> Container:
    """A container backed by a private in-memory database.

    Every repository in it shares one database, so foreign keys between chats
    and messages behave the way they do in production.
    """
    return Container(Settings(db_path=MEMORY_PATH, **overrides))
