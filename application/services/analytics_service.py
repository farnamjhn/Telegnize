"""Computes the behavioural profile of a stored chat.

Everything here comes from aggregate queries, so analysing a chat costs the
same whether it holds a thousand messages or a million. What the figures do and
do not support is set out in ``docs/analytics.md``; the short version is that
they describe observable behaviour — timing, volume, wording — and none of them
is a measurement of a relationship.
"""

import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from statistics import fmean, median

from application.dtos.analysis_dto import (
    BalanceDTO,
    ChatAnalyticsDTO,
    ConversationRhythmDTO,
    EngagementDTO,
    ExpressionDTO,
    LatencyPointDTO,
    ParticipantStatsDTO,
    ResponsivenessDTO,
)
from domain.errors import ChatNotFoundError
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository

_ROUNDING = 2
_WORDS_PER_RATE_UNIT = 1000

#: Hours counted as late night, when people tend to write more freely.
LATE_NIGHT_HOURS = range(0, 5)

#: Above this span, the latency trend is bucketed by month instead of week, so
#: a chat running for years does not return hundreds of points.
_MONTHLY_TREND_ABOVE_DAYS = 180
_WEEKLY_PERIOD_FORMAT = "%Y-W%W"
_MONTHLY_PERIOD_FORMAT = "%Y-%m"


class AnalyticsService:
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

        total_words = sum(int(row["word_count"] or 0) for row in totals)
        latencies = self._messages.get_response_latencies(chat_id)
        trends = self._messages.get_response_latency_periods(
            chat_id, self._period_format(chat_id)
        )
        turn_taking = self._messages.get_turn_taking(chat_id)
        uptake = self._messages.get_question_uptake(chat_id)
        boundaries = self._messages.get_session_boundaries(chat_id)
        hourly = self._messages.get_hourly_distribution(chat_id)
        first_seen, last_seen = self._messages.get_date_range(chat_id)

        total_openings = sum(
            int(row.get("opened_count") or 0) for row in boundaries.values()
        )

        participants = [
            self._participant(
                row,
                total_messages=total_messages,
                total_words=total_words,
                total_openings=total_openings,
                latencies=latencies.get(row["sender_id"], []),
                trend=trends.get(row["sender_id"], {}),
                turns=turn_taking.get(row["sender_id"], {}),
                uptake=uptake.get(row["sender_id"], {}),
                boundaries=boundaries.get(row["sender_id"], {}),
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
            hourly_distribution=hourly,
            daily_distribution=self._messages.get_daily_distribution(chat_id),
            language_breakdown=self._messages.get_language_distribution(chat_id),
            avg_response_time_seconds=_rounded_mean(all_latencies),
            rhythm=self._rhythm(chat_id, hourly, total_messages),
            balance=self._balance(participants),
        )

    # --- participants -----------------------------------------------------
    def _participant(
        self,
        row: Mapping[str, object],
        *,
        total_messages: int,
        total_words: int,
        total_openings: int,
        latencies: Sequence[float],
        trend: Mapping[str, Sequence[float]],
        turns: Mapping[str, int],
        uptake: Mapping[str, int],
        boundaries: Mapping[str, int],
    ) -> ParticipantStatsDTO:
        message_count = int(row["message_count"])
        word_count = int(row["word_count"] or 0)

        return ParticipantStatsDTO(
            sender_id=str(row["sender_id"]),
            sender_name=str(row["sender_name"]),
            message_count=message_count,
            word_count=word_count,
            char_count=int(row["char_count"] or 0),
            avg_words_per_message=round(word_count / message_count, _ROUNDING),
            message_share_percent=_percent(message_count, total_messages),
            word_share_percent=_percent(word_count, total_words),
            responsiveness=self._responsiveness(latencies, trend, uptake),
            engagement=self._engagement(
                row, message_count, total_openings, turns, boundaries
            ),
            expression=self._expression(row, word_count),
        )

    @staticmethod
    def _responsiveness(
        latencies: Sequence[float],
        trend: Mapping[str, Sequence[float]],
        uptake: Mapping[str, int],
    ) -> ResponsivenessDTO:
        asked = int(uptake.get("question_count") or 0)
        answered = int(uptake.get("answered_count") or 0)
        points = [
            LatencyPointDTO(
                period=period,
                median_seconds=round(median(values), _ROUNDING),
                reply_count=len(values),
            )
            for period, values in sorted(trend.items())
        ]
        return ResponsivenessDTO(
            avg_seconds=_rounded_mean(latencies),
            median_seconds=round(median(latencies), _ROUNDING) if latencies else None,
            p90_seconds=_percentile(latencies, 0.9),
            reply_count=len(latencies),
            question_count=asked,
            questions_answered_count=answered,
            questions_answered_percent=_percent(answered, asked) if asked else None,
            latency_trend=points,
            latency_drift_percent=_drift(
                [point.median_seconds for point in points]
            ),
        )

    @staticmethod
    def _engagement(
        row: Mapping[str, object],
        message_count: int,
        total_openings: int,
        turns: Mapping[str, int],
        boundaries: Mapping[str, int],
    ) -> EngagementDTO:
        turn_count = int(turns.get("burst_count") or 0)
        turn_words = int(turns.get("word_count") or 0)
        opened = int(boundaries.get("opened_count") or 0)
        cold_closures = int(row["cold_closure_count"] or 0)
        return EngagementDTO(
            opened_count=opened,
            opened_percent=_percent(opened, total_openings) if total_openings else None,
            closed_count=int(boundaries.get("closed_count") or 0),
            turn_count=turn_count,
            avg_messages_per_turn=(
                round(message_count / turn_count, _ROUNDING) if turn_count else 0.0
            ),
            avg_words_per_turn=(
                round(turn_words / turn_count, _ROUNDING) if turn_count else 0.0
            ),
            double_text_percent=_percent(
                int(turns.get("continuations") or 0), message_count
            ),
            cold_closure_count=cold_closures,
            cold_closure_percent=_percent(cold_closures, message_count),
            voice_message_count=int(row["voice_count"] or 0),
            media_count=int(row["media_count"] or 0),
        )

    @staticmethod
    def _expression(row: Mapping[str, object], word_count: int) -> ExpressionDTO:
        def count(column: str) -> int:
            return int(row[column] or 0)

        def rate(column: str) -> float:
            if not word_count:
                return 0.0
            return round(
                count(column) / word_count * _WORDS_PER_RATE_UNIT, _ROUNDING
            )

        self_reference = count("self_reference_count")
        collective = count("collective_reference_count")
        first_person = self_reference + collective

        return ExpressionDTO(
            exclamation_count=count("exclamation_count"),
            emoji_count=count("emoji_count"),
            affection_count=count("affection_count"),
            apology_count=count("apology_count"),
            gratitude_count=count("gratitude_count"),
            self_reference_count=self_reference,
            collective_reference_count=collective,
            absolutist_count=count("absolutist_count"),
            elongation_count=count("elongation_count"),
            exclamations_per_1k_words=rate("exclamation_count"),
            affection_per_1k_words=rate("affection_count"),
            apology_per_1k_words=rate("apology_count"),
            gratitude_per_1k_words=rate("gratitude_count"),
            elongation_per_1k_words=rate("elongation_count"),
            emoji_per_100_words=(
                round(count("emoji_count") / word_count * 100, _ROUNDING)
                if word_count
                else 0.0
            ),
            absolutism_percent=_percent(count("absolutist_count"), word_count),
            collective_focus_percent=(
                _percent(collective, first_person) if first_person else None
            ),
        )

    def _period_format(self, chat_id: int) -> str:
        """Picks week or month buckets to suit how long the chat runs."""
        shape = self._messages.get_session_shape(chat_id)
        span = float(shape.get("span_days") or 0.0)
        return (
            _MONTHLY_PERIOD_FORMAT
            if span > _MONTHLY_TREND_ABOVE_DAYS
            else _WEEKLY_PERIOD_FORMAT
        )

    # --- chat-level -------------------------------------------------------
    def _rhythm(
        self, chat_id: int, hourly: Mapping[int, int], total_messages: int
    ) -> ConversationRhythmDTO:
        shape = self._messages.get_session_shape(chat_id)
        active_days = int(shape.get("active_days") or 0)
        # A chat inside a single day spans zero days but covers one.
        span_days = max(1, math.ceil(float(shape.get("span_days") or 0.0)))
        late_night = sum(hourly.get(hour, 0) for hour in LATE_NIGHT_HOURS)

        return ConversationRhythmDTO(
            session_count=int(shape.get("session_count") or 0),
            avg_messages_per_session=round(
                float(shape.get("avg_session_messages") or 0.0), _ROUNDING
            ),
            avg_session_minutes=round(
                float(shape.get("avg_session_minutes") or 0.0), _ROUNDING
            ),
            active_days=active_days,
            span_days=span_days,
            active_day_percent=_percent(active_days, span_days),
            longest_silence_days=round(
                float(shape.get("longest_silence_days") or 0.0), _ROUNDING
            ),
            late_night_percent=_percent(late_night, total_messages),
        )

    @staticmethod
    def _balance(participants: Sequence[ParticipantStatsDTO]) -> BalanceDTO:
        medians = [
            p.responsiveness.median_seconds
            for p in participants
            if p.responsiveness.median_seconds
        ]
        return BalanceDTO(
            message_balance_percent=_evenness([p.message_count for p in participants]),
            word_balance_percent=_evenness([p.word_count for p in participants]),
            initiation_balance_percent=_evenness(
                [p.engagement.opened_count for p in participants]
            ),
            response_time_ratio=(
                round(max(medians) / min(medians), _ROUNDING)
                if len(medians) > 1 and min(medians) > 0
                else None
            ),
        )


def _percent(part: float, whole: float) -> float:
    return round(part / whole * 100, _ROUNDING) if whole else 0.0


def _rounded_mean(values: Sequence[float]) -> float | None:
    return round(fmean(values), _ROUNDING) if values else None


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    """The value below which ``fraction`` of the sample falls.

    Nearest-rank rather than an interpolating percentile: with the handful of
    replies some participants have, interpolating invents precision.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(fraction * len(ordered)) - 1)
    return round(ordered[rank], _ROUNDING)


def _drift(series: Sequence[float]) -> float | None:
    """Percentage change from the first half of a series to the second.

    Positive means the usual reply time grew — the participant is answering
    more slowly than they were. Needs at least two periods to say anything.
    """
    if len(series) < 2:
        return None
    midpoint = len(series) // 2
    earlier, later = series[:midpoint], series[midpoint:]
    if not earlier or not later:
        return None
    baseline = median(earlier)
    if baseline <= 0:
        return None
    return round((median(later) - baseline) / baseline * 100, _ROUNDING)


def _evenness(shares: Sequence[int]) -> float:
    """How evenly a total is split, as a percentage.

    Normalised Shannon entropy: 100 when every participant contributes the same
    amount, falling toward 0 as one of them accounts for everything. Unlike a
    two-way ratio it stays meaningful for group chats.
    """
    total = sum(shares)
    present = [value for value in shares if value > 0]
    if total <= 0 or len(present) < 2:
        return 100.0 if total > 0 else 0.0

    entropy = -sum((value / total) * math.log(value / total) for value in present)
    return round(entropy / math.log(len(shares)) * 100, _ROUNDING)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
