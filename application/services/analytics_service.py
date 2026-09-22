"""Computes the behavioural profile of a stored chat."""

from collections.abc import Sequence
from datetime import datetime
from statistics import fmean, median

from application.dtos.analysis_dto import ChatAnalyticsDTO, ParticipantStatsDTO
from domain.errors import ChatNotFoundError
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository

_ROUNDING = 2


class AnalyticsService:
    """Assembles volume, temporal, linguistic, and latency statistics.

    Every figure comes from an aggregate query, so the cost of analysing a chat
    does not grow with how much of it has to be held in memory — only the
    per-participant summary is materialised, and there are few participants.
    """

    def __init__(
        self, chat_repo: IChatRepository, message_repo: IMessageRepository
    ) -> None:
        self._chats = chat_repo
        self._messages = message_repo

    def compute_chat_analytics(self, chat_id: int) -> ChatAnalyticsDTO:
        """Builds the analytics profile for one chat.

        Raises:
            ChatNotFoundError: if no such chat has been imported.
        """
        chat = self._chats.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)

        totals = self._messages.get_participant_totals(chat_id)
        total_messages = sum(int(row["message_count"]) for row in totals)
        if total_messages == 0:
            return ChatAnalyticsDTO(
                chat_id=chat.id, chat_name=chat.name, total_messages=0
            )

        latencies = self._messages.get_response_latencies(chat_id)
        first_seen, last_seen = self._messages.get_date_range(chat_id)

        participants = [
            self._to_participant_stats(
                row, total_messages, latencies.get(row["sender_id"], [])
            )
            for row in totals
        ]
        participants.sort(key=lambda p: p.message_count, reverse=True)

        all_latencies = [value for values in latencies.values() for value in values]

        return ChatAnalyticsDTO(
            chat_id=chat.id,
            chat_name=chat.name,
            total_messages=total_messages,
            date_range_start=_parse_timestamp(first_seen),
            date_range_end=_parse_timestamp(last_seen),
            participants=participants,
            hourly_distribution=self._messages.get_hourly_distribution(chat_id),
            daily_distribution=self._messages.get_daily_distribution(chat_id),
            language_breakdown=self._messages.get_language_distribution(chat_id),
            avg_response_time_seconds=_rounded_mean(all_latencies),
        )

    @staticmethod
    def _to_participant_stats(
        row: dict, total_messages: int, latencies: Sequence[float]
    ) -> ParticipantStatsDTO:
        message_count = int(row["message_count"])
        word_count = int(row["word_count"] or 0)
        return ParticipantStatsDTO(
            sender_id=str(row["sender_id"]),
            sender_name=str(row["sender_name"]),
            message_count=message_count,
            word_count=word_count,
            char_count=int(row["char_count"] or 0),
            question_count=int(row["question_count"] or 0),
            cold_closure_count=int(row["cold_closure_count"] or 0),
            avg_words_per_message=round(word_count / message_count, _ROUNDING),
            message_share_percent=round(
                message_count / total_messages * 100, _ROUNDING
            ),
            avg_response_time_seconds=_rounded_mean(latencies),
            median_response_time_seconds=(
                round(median(latencies), _ROUNDING) if latencies else None
            ),
        )


def _rounded_mean(values: Sequence[float]) -> float | None:
    return round(fmean(values), _ROUNDING) if values else None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
