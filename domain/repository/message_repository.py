"""Port for message storage and the aggregate queries analytics needs."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence

from domain.models.message import Message


class IMessageRepository(ABC):
    """Stores messages and answers aggregate questions about them.

    The aggregate methods exist so callers never have to materialise a whole
    chat to compute a statistic: an export can hold millions of messages.
    """

    # --- writes -----------------------------------------------------------
    @abstractmethod
    def save(self, message: Message) -> None:
        """Inserts a message, replacing any existing one with the same key."""

    @abstractmethod
    def save_batch(self, messages: Sequence[Message]) -> int:
        """Inserts a batch in one transaction; returns the number written."""

    # --- reads ------------------------------------------------------------
    @abstractmethod
    def get_by_id(self, message_id: int) -> Message | None:
        """Gets a message by its Telegnize identifier."""

    @abstractmethod
    def get_by_telegram_id(
        self, telegram_msg_id: int, chat_id: int | None = None
    ) -> Message | None:
        """Gets a message by its Telegram identifier, optionally scoped to a chat."""

    @abstractmethod
    def list_messages(
        self,
        chat_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        sender_id: str | None = None,
    ) -> list[Message]:
        """Lists messages chronologically, filtered and paginated."""

    @abstractmethod
    def iter_chat_timeline(self, chat_id: int) -> Iterable[Message]:
        """Yields a chat's messages chronologically without buffering them all."""

    # --- aggregates -------------------------------------------------------
    @abstractmethod
    def count_by_chat(self, chat_id: int) -> int:
        """Counts messages in a chat."""

    @abstractmethod
    def get_date_range(self, chat_id: int) -> tuple[str | None, str | None]:
        """Returns the (first, last) message timestamps of a chat as ISO strings."""

    @abstractmethod
    def get_participant_totals(self, chat_id: int) -> list[dict[str, object]]:
        """Per-sender message, word, char, question, and cold-closure totals."""

    @abstractmethod
    def get_hourly_distribution(self, chat_id: int) -> dict[int, int]:
        """Message counts keyed by hour of day (0-23)."""

    @abstractmethod
    def get_daily_distribution(self, chat_id: int) -> dict[str, int]:
        """Message counts keyed by weekday name."""

    @abstractmethod
    def get_language_distribution(self, chat_id: int) -> dict[str, int]:
        """Message counts keyed by detected language tag."""

    @abstractmethod
    def get_response_latencies(
        self, chat_id: int, within_seconds: int | None = None
    ) -> dict[str, list[float]]:
        """Per-sender response latencies in seconds, for turns they answered.

        ``within_seconds`` replaces both the reply and turn windows with one
        value, which is how an active-session figure is taken: the default
        windows run to hours and count a reply after a night's sleep as a slow
        one.
        """

    @abstractmethod
    def get_response_latency_periods(
        self, chat_id: int, period_format: str
    ) -> dict[str, dict[str, list[float]]]:
        """Response latencies per sender, bucketed by calendar period."""

    @abstractmethod
    def get_turn_taking(self, chat_id: int) -> dict[str, dict[str, int]]:
        """Per-sender message, turn, continuation, and word counts."""

    @abstractmethod
    def get_question_uptake(self, chat_id: int) -> dict[str, dict[str, int]]:
        """Per-sender questions asked, and how many the other party picked up."""

    @abstractmethod
    def get_session_boundaries(
        self, chat_id: int, gap_seconds: int | None = None
    ) -> dict[str, dict[str, int]]:
        """Per-sender counts of conversations opened and closed.

        ``gap_seconds`` overrides what counts as the silence between two
        conversations, so the same query answers both "who starts them" at the
        session gap and "who has the last word" at a tighter one.
        """

    @abstractmethod
    def get_session_shape(self, chat_id: int) -> dict[str, float | None]:
        """Chat-level session count, sizes, silence, and active-day span."""

    @abstractmethod
    def get_hourly_by_sender(self, chat_id: int) -> dict[str, dict[int, int]]:
        """Per sender, message counts keyed by hour of day (0-23)."""

    @abstractmethod
    def get_silence_breaks(self, chat_id: int) -> dict[str, dict[str, float]]:
        """Per sender, how many long silences they ended and the longest one."""

    @abstractmethod
    def get_burst_profile(self, chat_id: int) -> dict[str, dict[str, float]]:
        """Per sender, turn count, long-burst count, longest and mean burst."""

    @abstractmethod
    def get_collisions(self, chat_id: int) -> dict[str, int]:
        """Per sender, messages sent on top of the other person's."""

    @abstractmethod
    def iter_analysis_texts(self, chat_id: int) -> Iterable[tuple[str, str]]:
        """Streams (sender_id, analysis text) chronologically.

        The one non-aggregate read: vocabulary and style matching need the
        words themselves, which SQL cannot tokenize.
        """
