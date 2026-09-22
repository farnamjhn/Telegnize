import unittest
from datetime import datetime, timedelta

from domain.errors import ChatNotFoundError
from domain.models.chat import Chat
from domain.models.language import Language
from domain.models.message import Message
from tests.conftest import memory_container

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)


class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.service = self.container.analytics_service
        self.messages = self.container.message_repository
        self.chat = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=1234, name="Test Analytics Chat")
        )

    def tearDown(self):
        self.container.close()

    def given_conversation(self):
        self.messages.save_batch(
            [
                Message(
                    id=0,
                    chat_id=self.chat.id,
                    telegram_msg_id=1,
                    sender_id="u1",
                    sender_name="Alice",
                    timestamp=BASE_TIME,
                    text="سلام، کجایی؟",
                    language=Language.PERSIAN,
                ),
                Message(
                    id=0,
                    chat_id=self.chat.id,
                    telegram_msg_id=2,
                    sender_id="u2",
                    sender_name="Bob",
                    reply_to_msg_id=1,
                    timestamp=BASE_TIME + timedelta(seconds=60),
                    text="سلام، تو راهم",
                    language=Language.PERSIAN,
                ),
                Message(
                    id=0,
                    chat_id=self.chat.id,
                    telegram_msg_id=3,
                    sender_id="u1",
                    sender_name="Alice",
                    reply_to_msg_id=2,
                    timestamp=BASE_TIME + timedelta(seconds=120),
                    text="باشه",
                    language=Language.PERSIAN,
                ),
            ]
        )

    def test_volume_and_linguistic_counters(self):
        self.given_conversation()
        analytics = self.service.compute_chat_analytics(self.chat.id)

        self.assertEqual(analytics.total_messages, 3)
        self.assertEqual(len(analytics.participants), 2)

        alice = next(p for p in analytics.participants if p.sender_id == "u1")
        self.assertEqual(alice.message_count, 2)
        self.assertEqual(alice.question_count, 1)
        self.assertEqual(alice.cold_closure_count, 1)
        self.assertAlmostEqual(alice.message_share_percent, 66.67, places=2)

        bob = next(p for p in analytics.participants if p.sender_id == "u2")
        self.assertEqual(bob.message_count, 1)
        self.assertEqual(bob.avg_response_time_seconds, 60.0)
        self.assertEqual(bob.median_response_time_seconds, 60.0)

    def test_participants_are_ordered_by_volume(self):
        self.given_conversation()
        analytics = self.service.compute_chat_analytics(self.chat.id)
        self.assertEqual([p.sender_id for p in analytics.participants], ["u1", "u2"])

    def test_temporal_and_language_breakdowns(self):
        self.given_conversation()
        analytics = self.service.compute_chat_analytics(self.chat.id)

        self.assertEqual(analytics.hourly_distribution, {10: 3})
        self.assertEqual(analytics.daily_distribution, {"Wednesday": 3})
        self.assertEqual(analytics.language_breakdown, {"fa": 3})
        self.assertEqual(analytics.date_range_start, BASE_TIME)
        self.assertEqual(
            analytics.date_range_end, BASE_TIME + timedelta(seconds=120)
        )
        self.assertEqual(analytics.avg_response_time_seconds, 60.0)

    def test_an_empty_chat_reports_zeroes_rather_than_failing(self):
        analytics = self.service.compute_chat_analytics(self.chat.id)
        self.assertEqual(analytics.total_messages, 0)
        self.assertEqual(analytics.participants, [])
        self.assertIsNone(analytics.avg_response_time_seconds)
        self.assertIsNone(analytics.date_range_start)

    def test_an_unknown_chat_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service.compute_chat_analytics(9999)


if __name__ == "__main__":
    unittest.main()
