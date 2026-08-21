import unittest
import os
from datetime import datetime, timezone
from pathlib import Path

from domain.models.message import Message, ContentType, MessageId
from infrastructure.repository.sqlite_message_repository import SQLiteMessageRepository


class TestSQLiteMessageRepository(unittest.TestCase):
    def setUp(self):
        self.db_path = ":memory:"
        self.repo = SQLiteMessageRepository(self.db_path)

    def tearDown(self):
        self.repo.close()

    def test_save_and_get_by_id(self):
        msg = Message(
            id=0,
            telegram_msg_id=1001,
            sender_id="user_1",
            sender_name="Alice",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 21, 10, 0, 0),
            text="Hello World!",
            content_type=ContentType.TEXT,
            reply_to_id=None,
            is_forwarded=False,
        )
        self.repo.save(msg)

        fetched = self.repo.get_by_id(1)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, 1)
        self.assertEqual(fetched.telegram_msg_id, 1001)
        self.assertEqual(fetched.sender_id, "user_1")
        self.assertEqual(fetched.sender_name, "Alice")
        self.assertEqual(fetched.text, "Hello World!")
        self.assertEqual(fetched.content_type, ContentType.TEXT)
        self.assertFalse(fetched.is_forwarded)
        self.assertIsNone(fetched.reply_to_msg_id)
        self.assertIsNone(fetched.reply_to_id)

    def test_get_by_telegram_id(self):
        msg = Message(
            id=0,
            telegram_msg_id=2002,
            sender_id="user_2",
            sender_name="Bob",
            reply_to_msg_id=1001,
            timestamp=datetime(2026, 8, 21, 10, 5, 0),
            text="Replying to your message",
            content_type=ContentType.TEXT,
            reply_to_id=MessageId(1001),
            is_forwarded=False,
        )
        self.repo.save(msg)

        fetched = self.repo.get_by_telegram_id(2002)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.telegram_msg_id, 2002)
        self.assertEqual(fetched.reply_to_msg_id, 1001)
        self.assertIsNotNone(fetched.reply_to_id)
        self.assertEqual(fetched.reply_to_id.value, 1001)

    def test_save_batch_and_get_all_ordered(self):
        msg1 = Message(
            id=0,
            telegram_msg_id=1,
            sender_id="u1",
            sender_name="User 1",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 21, 12, 0, 0),
            text="Second message",
        )
        msg2 = Message(
            id=0,
            telegram_msg_id=2,
            sender_id="u2",
            sender_name="User 2",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 21, 11, 0, 0),
            text="First message",
        )

        self.repo.save_batch([msg1, msg2])

        all_msgs = self.repo.get_all_ordered()
        self.assertEqual(len(all_msgs), 2)
        self.assertEqual(all_msgs[0].telegram_msg_id, 2)
        self.assertEqual(all_msgs[1].telegram_msg_id, 1)

    def test_upsert_on_conflict(self):
        msg = Message(
            id=0,
            telegram_msg_id=500,
            sender_id="u1",
            sender_name="Original Name",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 21, 10, 0, 0),
            text="Original text",
        )
        self.repo.save(msg)

        first_fetched = self.repo.get_by_telegram_id(500)
        self.assertEqual(first_fetched.text, "Original text")

        updated_msg = Message(
            id=0,
            telegram_msg_id=500,
            sender_id="u1",
            sender_name="Updated Name",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 21, 10, 0, 0),
            text="Updated text",
        )
        self.repo.save(updated_msg)

        second_fetched = self.repo.get_by_telegram_id(500)
        self.assertEqual(second_fetched.id, first_fetched.id)
        self.assertEqual(second_fetched.sender_name, "Updated Name")
        self.assertEqual(second_fetched.text, "Updated text")

    def test_file_database_creation(self):
        temp_file = "temp_test_db/chat.db"
        if os.path.exists(temp_file):
            os.remove(temp_file)

        file_repo = SQLiteMessageRepository(temp_file)
        msg = Message(
            id=0,
            telegram_msg_id=999,
            sender_id="u1",
            sender_name="Test",
            reply_to_msg_id=None,
            timestamp=datetime.now(),
            text="File test",
        )
        file_repo.save(msg)
        fetched = file_repo.get_by_telegram_id(999)
        self.assertIsNotNone(fetched)
        file_repo.close()

        if os.path.exists(temp_file):
            os.remove(temp_file)
            if os.path.exists("temp_test_db"):
                os.rmdir("temp_test_db")


if __name__ == "__main__":
    unittest.main()
