import json
import os
import tempfile
import unittest

from domain.models.message import ContentType
from infrastructure.parser.telegram_parser import TelegramJsonParser


class TestTelegramJsonParser(unittest.TestCase):
    def setUp(self):
        self.parser = TelegramJsonParser()

    def test_parse_simple_text_message(self):
        msg_dict = {
            "id": 101,
            "type": "message",
            "date": "2026-08-21T10:00:00",
            "from": "Alice",
            "from_id": "user_100",
            "text": "Hello world!"
        }
        msg = self.parser.parse_message_dict(msg_dict)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.telegram_msg_id, 101)
        self.assertEqual(msg.sender_id, "user_100")
        self.assertEqual(msg.sender_name, "Alice")
        self.assertEqual(msg.text, "Hello world!")
        self.assertEqual(msg.content_type, ContentType.TEXT)
        self.assertFalse(msg.is_forwarded)
        self.assertIsNone(msg.reply_to_msg_id)

    def test_parse_formatted_text(self):
        msg_dict = {
            "id": 102,
            "type": "message",
            "date": "2026-08-21T10:05:00",
            "from": "Bob",
            "from_id": "user_200",
            "text": [
                "This is ",
                {"type": "bold", "text": "formatted"},
                " text."
            ]
        }
        msg = self.parser.parse_message_dict(msg_dict)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.text, "This is formatted text.")

    def test_parse_media_and_reply(self):
        voice_msg = {
            "id": 103,
            "type": "message",
            "date": "2026-08-21T10:10:00",
            "from": "Alice",
            "from_id": "user_100",
            "reply_to_message_id": 101,
            "media_type": "voice_message",
            "text": ""
        }
        msg = self.parser.parse_message_dict(voice_msg)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.content_type, ContentType.VOICE)
        self.assertEqual(msg.reply_to_msg_id, 101)
        self.assertIsNotNone(msg.reply_to_id)
        self.assertEqual(msg.reply_to_id.value, 101)

    def test_parse_forwarded_message(self):
        fwd_msg = {
            "id": 104,
            "type": "message",
            "date": "2026-08-21T10:15:00",
            "from": "Charlie",
            "from_id": "user_300",
            "forwarded_from": "Alice",
            "text": "Forwarded announcement"
        }
        msg = self.parser.parse_message_dict(fwd_msg)
        self.assertIsNotNone(msg)
        self.assertTrue(msg.is_forwarded)

    def test_ignore_service_messages(self):
        service_msg = {
            "id": 105,
            "type": "service",
            "date": "2026-08-21T10:20:00",
            "actor": "Alice",
            "action": "invite_members"
        }
        msg = self.parser.parse_message_dict(service_msg)
        self.assertIsNone(msg)

    def test_parse_file(self):
        export_data = {
            "name": "Group Chat",
            "type": "public_supergroup",
            "id": 99999,
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2026-08-21T11:00:00",
                    "from": "User A",
                    "from_id": "user_1",
                    "text": "First chat message"
                },
                {
                    "id": 2,
                    "type": "service",
                    "date": "2026-08-21T11:01:00",
                    "actor": "User B",
                    "action": "edit_title"
                },
                {
                    "id": 3,
                    "type": "message",
                    "date": "2026-08-21T11:02:00",
                    "from": "User B",
                    "from_id": "user_2",
                    "reply_to_message_id": 1,
                    "text": "Reply to first message"
                }
            ]
        }

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump(export_data, f)
            temp_path = f.name

        try:
            parsed = self.parser.parse_file(temp_path)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0].telegram_msg_id, 1)
            self.assertEqual(parsed[0].text, "First chat message")
            self.assertEqual(parsed[1].telegram_msg_id, 3)
            self.assertEqual(parsed[1].reply_to_msg_id, 1)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
