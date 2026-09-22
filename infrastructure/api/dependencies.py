import os
from typing import Generator

from application.services.analytics_service import AnalyticsService
from application.services.decision_service import DecisionService
from application.services.ingestion_service import IngestionService
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository
from infrastructure.decision_engine.laya_engine import get_decision_engine
from infrastructure.parser.telegram_parser import TelegramJsonParser
from infrastructure.repository.sqlite_chat_repository import SQLiteChatRepository
from infrastructure.repository.sqlite_message_repository import SQLiteMessageRepository

DB_PATH = os.getenv("TELEGNIZE_DB_PATH", "identifier.sqlite")


def get_chat_repo() -> Generator[IChatRepository, None, None]:
    repo = SQLiteChatRepository(db_path=DB_PATH)
    try:
        yield repo
    finally:
        repo.close()


def get_message_repo() -> Generator[IMessageRepository, None, None]:
    repo = SQLiteMessageRepository(db_path=DB_PATH)
    try:
        yield repo
    finally:
        repo.close()


def get_ingestion_service() -> IngestionService:
    chat_repo = SQLiteChatRepository(db_path=DB_PATH)
    msg_repo = SQLiteMessageRepository(db_path=DB_PATH)
    return IngestionService(chat_repo=chat_repo, message_repo=msg_repo)


def get_analytics_service() -> AnalyticsService:
    chat_repo = SQLiteChatRepository(db_path=DB_PATH)
    msg_repo = SQLiteMessageRepository(db_path=DB_PATH)
    return AnalyticsService(chat_repo=chat_repo, message_repo=msg_repo)


def get_decision_service() -> DecisionService:
    msg_repo = SQLiteMessageRepository(db_path=DB_PATH)
    engine = get_decision_engine()
    return DecisionService(message_repo=msg_repo, engine=engine)
