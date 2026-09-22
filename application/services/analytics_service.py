from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from application.dtos.analysis_dto import ChatAnalyticsDTO, ParticipantStatsDTO
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository


class AnalyticsService:
    """Calculates comprehensive behavioral, statistical, and temporal analytics on stored chats."""

    def __init__(self, chat_repo: IChatRepository, message_repo: IMessageRepository):
        self.chat_repo = chat_repo
        self.message_repo = message_repo

    def compute_chat_analytics(self, chat_id: int) -> Optional[ChatAnalyticsDTO]:
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            return None

        messages = self.message_repo.get_chat_timeline(chat_id)
        if not messages:
            return ChatAnalyticsDTO(
                chat_id=chat.id,
                chat_name=chat.name,
                total_messages=0,
                date_range_start=None,
                date_range_end=None,
                participants=[],
                hourly_distribution={},
                daily_distribution={},
                language_breakdown={},
                avg_response_time_seconds=None,
            )

        total_messages = len(messages)
        start_date = messages[0].timestamp
        end_date = messages[-1].timestamp

        # Participant data aggregators
        sender_messages = defaultdict(list)
        msg_id_map = {}
        hourly_dist = defaultdict(int)
        daily_dist = defaultdict(int)
        lang_dist = defaultdict(int)

        for msg in messages:
            sender_messages[msg.sender_id].append(msg)
            msg_id_map[msg.telegram_msg_id] = msg

            # Hourly & Daily breakdown
            hourly_dist[msg.timestamp.hour] += 1
            weekday_name = msg.timestamp.strftime("%A")
            daily_dist[weekday_name] += 1

            # Language breakdown
            lang = msg.language or "unknown"
            lang_dist[lang] += 1

        # Response latency calculation
        # 1. Direct replies (reply_to_msg_id)
        # 2. Sequential turn-taking (consecutive messages with differing senders < 6 hours apart)
        participant_latencies = defaultdict(list)
        all_latencies = []

        for i, msg in enumerate(messages):
            # Check direct reply
            if msg.reply_to_msg_id and msg.reply_to_msg_id in msg_id_map:
                parent = msg_id_map[msg.reply_to_msg_id]
                if parent.sender_id != msg.sender_id:
                    delta = (msg.timestamp - parent.timestamp).total_seconds()
                    if 0 <= delta <= 86400:  # within 24 hours
                        participant_latencies[msg.sender_id].append(delta)
                        all_latencies.append(delta)
            elif i > 0:
                prev = messages[i - 1]
                if prev.sender_id != msg.sender_id:
                    delta = (msg.timestamp - prev.timestamp).total_seconds()
                    if 0 <= delta <= 21600:  # within 6 hours
                        participant_latencies[msg.sender_id].append(delta)
                        all_latencies.append(delta)

        # Build ParticipantStats
        participants_stats: List[ParticipantStatsDTO] = []
        for sender_id, p_msgs in sender_messages.items():
            sender_name = p_msgs[0].sender_name
            p_count = len(p_msgs)
            p_words = sum(m.word_count for m in p_msgs)
            p_chars = sum(m.char_count for m in p_msgs)
            p_questions = sum(1 for m in p_msgs if m.is_question)
            p_cold = sum(1 for m in p_msgs if m.is_cold_closure)
            avg_words = round(p_words / p_count, 2) if p_count > 0 else 0.0
            share_pct = round((p_count / total_messages) * 100, 2)

            lats = participant_latencies.get(sender_id, [])
            avg_lat = round(sum(lats) / len(lats), 2) if lats else None

            participants_stats.append(
                ParticipantStatsDTO(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_count=p_count,
                    word_count=p_words,
                    char_count=p_chars,
                    question_count=p_questions,
                    cold_closure_count=p_cold,
                    avg_words_per_message=avg_words,
                    message_share_percent=share_pct,
                    avg_response_time_seconds=avg_lat,
                )
            )

        # Sort participants by message count descending
        participants_stats.sort(key=lambda x: x.message_count, reverse=True)

        overall_avg_latency = (
            round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else None
        )

        return ChatAnalyticsDTO(
            chat_id=chat.id,
            chat_name=chat.name,
            total_messages=total_messages,
            date_range_start=start_date,
            date_range_end=end_date,
            participants=participants_stats,
            hourly_distribution=dict(hourly_dist),
            daily_distribution=dict(daily_dist),
            language_breakdown=dict(lang_dist),
            avg_response_time_seconds=overall_avg_latency,
        )
