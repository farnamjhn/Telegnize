import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from application.ports.export_reader import ExportFormatError
from domain.models.language import Language
from domain.models.message import ContentType
from infrastructure.parser.telegram_parser import TelegramJsonParser


def export(messages, **header) -> bytes:
    document = {"name": "Armita", "type": "personal_chat", "id": 12345, **header}
    document["messages"] = messages
    return json.dumps(document).encode("utf-8")


class TestParseSingleMessage(unittest.TestCase):
    def setUp(self):
        self.parser = TelegramJsonParser()

    def test_plain_text_message(self):
        message = self.parser.parse_message(
            {
                "id": 101,
                "type": "message",
                "date": "2026-08-21T10:00:00",
                "from": "Alice",
                "from_id": "user_100",
                "text": "Hello world!",
            }
        )
        self.assertEqual(message.telegram_msg_id, 101)
        self.assertEqual(message.sender_id, "user_100")
        self.assertEqual(message.sender_name, "Alice")
        self.assertEqual(message.text, "Hello world!")
        self.assertEqual(message.normalized_text, "hello world!")
        self.assertIs(message.language, Language.ENGLISH)
        self.assertIs(message.content_type, ContentType.TEXT)
        self.assertFalse(message.is_forwarded)

    def test_entity_list_text_is_flattened(self):
        message = self.parser.parse_message(
            {
                "id": 102,
                "type": "message",
                "date": "2026-08-21T10:05:00",
                "from": "Bob",
                "from_id": "user_200",
                "text": ["This is ", {"type": "bold", "text": "formatted"}, " text."],
            }
        )
        self.assertEqual(message.text, "This is formatted text.")

    def test_media_type_and_reply_link(self):
        message = self.parser.parse_message(
            {
                "id": 103,
                "type": "message",
                "date": "2026-08-21T10:10:00",
                "from": "Alice",
                "from_id": "user_100",
                "reply_to_message_id": 101,
                "media_type": "voice_message",
                "text": "",
            }
        )
        self.assertIs(message.content_type, ContentType.VOICE)
        self.assertEqual(message.reply_to_msg_id, 101)

    def test_forwarded_message(self):
        message = self.parser.parse_message(
            {
                "id": 104,
                "type": "message",
                "date": "2026-08-21T10:15:00",
                "from": "Charlie",
                "from_id": "user_300",
                "forwarded_from": "Alice",
                "text": "Forwarded announcement",
            }
        )
        self.assertTrue(message.is_forwarded)

    def test_unix_timestamp_fallback(self):
        message = self.parser.parse_message(
            {"id": 105, "type": "message", "date_unixtime": "1780000000", "text": "hi"}
        )
        self.assertEqual(message.timestamp, datetime.fromtimestamp(1780000000))

    def test_service_messages_are_skipped(self):
        self.assertIsNone(
            self.parser.parse_message(
                {"id": 105, "type": "service", "actor": "Alice", "action": "invite"}
            )
        )

    def test_messages_without_a_usable_date_are_skipped(self):
        self.assertIsNone(
            self.parser.parse_message({"id": 106, "type": "message", "text": "when?"})
        )

    def test_messages_without_a_usable_id_are_skipped(self):
        self.assertIsNone(
            self.parser.parse_message(
                {"id": "not-a-number", "type": "message", "date": "2026-08-21T10:00:00"}
            )
        )


class TestParseDocuments(unittest.TestCase):
    def setUp(self):
        self.parser = TelegramJsonParser()

    def test_parse_file_skips_service_entries(self):
        document = json.loads(
            export(
                [
                    {
                        "id": 1,
                        "type": "message",
                        "date": "2026-08-21T11:00:00",
                        "from": "User A",
                        "from_id": "user_1",
                        "text": "First chat message",
                    },
                    {
                        "id": 2,
                        "type": "service",
                        "date": "2026-08-21T11:01:00",
                        "actor": "User B",
                        "action": "edit_title",
                    },
                    {
                        "id": 3,
                        "type": "message",
                        "date": "2026-08-21T11:02:00",
                        "from": "User B",
                        "from_id": "user_2",
                        "reply_to_message_id": 1,
                        "text": "Reply to first message",
                    },
                ]
            ).decode()
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as handle:
            json.dump(document, handle)
            path = handle.name
        try:
            parsed = self.parser.parse_file(path)
        finally:
            os.remove(path)

        self.assertEqual([m.telegram_msg_id for m in parsed], [1, 3])
        self.assertEqual(parsed[1].reply_to_msg_id, 1)


class TestStreaming(unittest.TestCase):
    def setUp(self):
        self.parser = TelegramJsonParser()

    def test_extract_metadata_reads_only_the_header(self):
        metadata = self.parser.extract_metadata(io.BytesIO(export([])))
        self.assertEqual(metadata.name, "Armita")
        self.assertEqual(metadata.type, "personal_chat")
        self.assertEqual(metadata.telegram_chat_id, 12345)

    def test_metadata_falls_back_when_the_header_is_absent(self):
        metadata = self.parser.extract_metadata(io.BytesIO(b'{"messages": []}'))
        self.assertEqual(metadata.name, "Exported Chat")
        self.assertEqual(metadata.telegram_chat_id, 0)

    def test_stream_yields_full_batches_then_the_remainder(self):
        stream = io.BytesIO(
            export(
                [
                    {
                        "id": i,
                        "type": "message",
                        "date": "2026-05-27T00:00:00",
                        "from": f"User {i}",
                        "from_id": f"user{i}",
                        "text": f"Message number {i}",
                    }
                    for i in range(1, 11)
                ]
            )
        )
        batches = list(self.parser.stream_messages(stream, chat_id=1, batch_size=4))
        self.assertEqual([len(batch) for batch in batches], [4, 4, 2])
        self.assertEqual(batches[0][0].telegram_msg_id, 1)
        self.assertEqual(batches[2][1].telegram_msg_id, 10)

    def test_a_stream_can_be_read_twice(self):
        stream = io.BytesIO(
            export(
                [
                    {
                        "id": 1,
                        "type": "message",
                        "date": "2026-05-27T00:00:00",
                        "text": "hi",
                    }
                ]
            )
        )
        self.parser.extract_metadata(stream)
        batches = list(self.parser.stream_messages(stream))
        self.assertEqual(len(batches), 1)

    def test_malformed_json_raises_an_export_format_error(self):
        with self.assertRaises(ExportFormatError):
            list(self.parser.stream_messages(io.BytesIO(b'{"messages": [')))

    def test_batch_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            list(self.parser.stream_messages(io.BytesIO(export([])), batch_size=0))


if __name__ == "__main__":
    unittest.main()
