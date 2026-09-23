"""Composition root: builds the object graph once per process.

Previously each request constructed its own repositories, and each of those
re-ran the schema script against a brand-new connection. The container builds
the database, repositories, and services once and hands the same instances to
every request; repositories borrow a connection per operation, so sharing them
across FastAPI's worker threads is safe.
"""

from functools import cached_property

from application.ports.decision_engine import IDecisionEngine
from application.ports.export_reader import IExportReader
from application.ports.text_normalizer import ITextNormalizer
from application.services.analytics_service import AnalyticsService
from application.services.assessment_service import AssessmentService
from application.services.chat_service import ChatService
from application.services.decision_service import DecisionService
from application.services.ingestion_service import IngestionService
from application.services.message_service import MessageService
from domain.repository.chat_repository import IChatRepository
from domain.repository.decision_repository import IDecisionRepository
from domain.repository.message_repository import IMessageRepository
from infrastructure.config import Settings
from infrastructure.decision_engine.caching_engine import CachingDecisionEngine
from infrastructure.decision_engine.laya_engine import LayaDecisionEngine
from infrastructure.nlp.normalizer import get_normalizer
from infrastructure.parser.telegram_parser import TelegramJsonParser
from infrastructure.persistence.database import Database
from infrastructure.persistence.sqlite_chat_repository import SQLiteChatRepository
from infrastructure.persistence.sqlite_decision_repository import (
    SQLiteDecisionRepository,
)
from infrastructure.persistence.sqlite_message_repository import (
    SQLiteMessageRepository,
)


class Container:
    """Lazily builds and caches the application's collaborators."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    # --- adapters ---------------------------------------------------------
    @cached_property
    def database(self) -> Database:
        return Database(self.settings.db_path)

    @cached_property
    def normalizer(self) -> ITextNormalizer:
        return get_normalizer()

    @cached_property
    def export_reader(self) -> IExportReader:
        return TelegramJsonParser(normalizer=self.normalizer)

    @cached_property
    def decision_engine(self) -> IDecisionEngine:
        """The engine, behind an answer cache unless one is configured away.

        The cache belongs here rather than inside the adapter: it is true of
        any engine that the same question about the same state has the same
        answer, and holding it at the composition root is what lets one cache
        serve every service that asks.
        """
        engine: IDecisionEngine = LayaDecisionEngine(
            preload=self.settings.preload_decision_engine,
            resident_checkpoints=self.settings.resident_checkpoints,
        )
        if self.settings.decision_cache_entries <= 0:
            return engine
        return CachingDecisionEngine(
            engine, max_entries=self.settings.decision_cache_entries
        )

    # --- repositories -----------------------------------------------------
    @cached_property
    def chat_repository(self) -> IChatRepository:
        return SQLiteChatRepository(self.database)

    @cached_property
    def message_repository(self) -> IMessageRepository:
        return SQLiteMessageRepository(
            self.database,
            reply_window_seconds=self.settings.reply_window_seconds,
            turn_window_seconds=self.settings.turn_window_seconds,
            session_gap_seconds=self.settings.session_gap_seconds,
            uptake_window_seconds=self.settings.uptake_window_seconds,
            silence_seconds=self.settings.silence_seconds,
            collision_seconds=self.settings.collision_seconds,
            burst_floor=self.settings.burst_floor,
        )

    @cached_property
    def decision_repository(self) -> IDecisionRepository:
        return SQLiteDecisionRepository(self.database)

    # --- services ---------------------------------------------------------
    @cached_property
    def chat_service(self) -> ChatService:
        return ChatService(self.chat_repository)

    @cached_property
    def message_service(self) -> MessageService:
        return MessageService(self.message_repository, self.normalizer)

    @cached_property
    def ingestion_service(self) -> IngestionService:
        return IngestionService(
            chat_repo=self.chat_repository,
            message_repo=self.message_repository,
            reader=self.export_reader,
            batch_size=self.settings.ingest_batch_size,
        )

    @cached_property
    def analytics_service(self) -> AnalyticsService:
        return AnalyticsService(
            self.chat_repository,
            self.message_repository,
            active_session_seconds=self.settings.active_session_seconds,
            last_word_gap_seconds=self.settings.last_word_gap_seconds,
        )

    @cached_property
    def assessment_service(self) -> AssessmentService:
        return AssessmentService(
            chat_repo=self.chat_repository,
            message_repo=self.message_repository,
            decision_repo=self.decision_repository,
            engine=self.decision_engine,
            page_size=self.settings.assessment_page_size,
        )

    @cached_property
    def decision_service(self) -> DecisionService:
        return DecisionService(
            message_repo=self.message_repository,
            decision_repo=self.decision_repository,
            engine=self.decision_engine,
        )

    # --- lifecycle --------------------------------------------------------
    def close(self) -> None:
        if "database" in self.__dict__:
            self.database.close()
