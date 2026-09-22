import unittest
from datetime import datetime, timedelta

from application.services.analytics_service import AnalyticsService
from domain.models.chat import Chat
from domain.models.message import ContentType, Message
from infrastructure.repository.sqlite_chat_repository import SQLiteChatRepository
from infrastructure.repository.sqlite_message_repository import SQLiteMessageRepository


class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.chat_repo = SQLiteChatRepository(":memory:")
        self.message_repo = SQLiteMessageRepository(":memory:")
        self.service = AnalyticsService(self.chat_repo, self.message_repo)

    def tearDown(self):
        self.chat_repo.close()
        self.message_repo.close()

    def test_compute_analytics(self):
        # Create chat
        chat = Chat(id=0, telegram_chat_id=1234, name="Test Analytics Chat")
        saved_chat = self.chat_repo.save(chat)

        base_time = datetime(2026, 5, 27, 10, 0, 0)
        # Message 1 from Alice: Question
        m1 = Message(
            id=0,
            telegram_msg_id=1,
            sender_id="u1",
            sender_name="Alice",
            reply_to_msg_id=None,
            timestamp=base_time,
            text="سلام، کجایی؟",
            chat_id=saved_chat.id,
            language="fa",
        )
        # Message 2 from Bob: Reply 60 seconds later
        m2 = Message(
            id=0,
            telegram_msg_id=2,
            sender_id="u2",
            sender_name="Bob",
            reply_to_msg_id=1,
            timestamp=base_time + timedelta(seconds=60),
            text="سلام، تو راهم",
            chat_id=saved_chat.id,
            language="fa",
        )
        # Message 3 from Alice: Cold closure
        m3 = Message(
            id=0,
            telegram_msg_id=3,
            sender_id="u1",
            sender_name="Alice",
            reply_to_msg_id=2,
            timestamp=base_time + timedelta(seconds=120),
            text="باشه",
            chat_id=saved_chat.id,
            language="fa",
        )

        self.message_repo.save_batch([m1, m2, m3])

        analytics = self.service.compute_chat_analytics(saved_chat.id)
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.total_messages, 3)
        self.assertEqual(len(analytics.participants), 2)

        alice_stats = next(p for p in analytics.participants if p.sender_id == "u1")
        self.assertEqual(alice_stats.message_count, 2)
        self.assertEqual(alice_stats.question_count, 1)
        self.assertEqual(alice_stats.cold_closure_count, 1)

        bob_stats = next(p for p in analytics.participants if p.sender_id == "u2")
        self.assertEqual(bob_stats.message_count, 1)
        self.assertEqual(bob_stats.avg_response_time_seconds, 60.0)


if __name__ == "__main__":
    unittest.main()
