import json
import io
import unittest
from infrastructure.parser.telegram_parser import TelegramJsonParser


class TestStreamingParser(unittest.TestCase):
    def setUp(self):
        self.parser = TelegramJsonParser()

    def test_extract_metadata(self):
        data = {
            "name": "Dana",
            "type": "personal_chat",
            "id": 12345,
            "messages": []
        }
        stream = io.BytesIO(json.dumps(data).encode("utf-8"))
        meta = self.parser.extract_chat_metadata(stream)
        self.assertEqual(meta["name"], "Dana")
        self.assertEqual(meta["type"], "personal_chat")
        self.assertEqual(meta["id"], 12345)

    def test_stream_messages_batches(self):
        messages = [
            {
                "id": i,
                "type": "message",
                "date": "2026-05-27T00:00:00",
                "from": f"User {i}",
                "from_id": f"user{i}",
                "text": f"Message number {i}"
            }
            for i in range(1, 11)
        ]
        data = {
            "name": "Test Chat",
            "type": "personal_chat",
            "id": 999,
            "messages": messages
        }
        stream = io.BytesIO(json.dumps(data).encode("utf-8"))

        batches = list(self.parser.stream_messages(stream, chat_id=1, batch_size=4))
        # 10 messages with batch_size=4 -> batches of size 4, 4, 2
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0]), 4)
        self.assertEqual(len(batches[1]), 4)
        self.assertEqual(len(batches[2]), 2)
        self.assertEqual(batches[0][0].telegram_msg_id, 1)
        self.assertEqual(batches[2][1].telegram_msg_id, 10)


if __name__ == "__main__":
    unittest.main()
