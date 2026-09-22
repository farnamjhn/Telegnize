"""The Message entity owns what 'question' and 'cold closure' mean."""

import unittest
from datetime import datetime

from domain.models.language import Language
from domain.models.message import ContentType, Message


def build(**overrides) -> Message:
    defaults = dict(
        id=1,
        telegram_msg_id=1,
        sender_id="u1",
        sender_name="Alice",
        timestamp=datetime(2026, 5, 27, 10, 0, 0),
        text="Hello there",
    )
    return Message(**{**defaults, **overrides})


class TestMessageEntity(unittest.TestCase):
    def test_normalized_text_defaults_to_raw_text(self):
        self.assertEqual(build(text="Hi").normalized_text, "Hi")

    def test_explicit_normalized_text_is_kept(self):
        message = build(text="Hi   There", normalized_text="hi there")
        self.assertEqual(message.normalized_text, "hi there")
        self.assertEqual(message.text, "Hi   There")

    def test_language_and_content_type_are_coerced(self):
        message = build(language="fa", content_type="voice_message")
        self.assertIs(message.language, Language.PERSIAN)
        self.assertIs(message.content_type, ContentType.VOICE)

    def test_unknown_tags_fall_back_instead_of_raising(self):
        message = build(language="klingon", content_type="hologram")
        self.assertIs(message.language, Language.UNKNOWN)
        self.assertIs(message.content_type, ContentType.TEXT)

    def test_question_detection_covers_persian(self):
        self.assertTrue(build(text="کجایی؟").is_question)
        self.assertTrue(build(text="Where are you?").is_question)
        self.assertFalse(build(text="I am here.").is_question)

    def test_cold_closure_ignores_punctuation_and_case(self):
        self.assertTrue(build(text="OK!").is_cold_closure)
        self.assertTrue(build(text="باشه").is_cold_closure)
        self.assertFalse(build(text="ok so what happened next").is_cold_closure)

    def test_counts_read_normalized_text(self):
        message = build(text="Hello   World", normalized_text="hello world")
        self.assertEqual(message.word_count, 2)
        self.assertEqual(message.char_count, len("hello world"))

    def test_forwarded_media_is_not_natural_text(self):
        self.assertFalse(build(is_forwarded=True).is_natural_text)
        self.assertFalse(build(content_type=ContentType.PHOTO).is_natural_text)
        self.assertTrue(build().is_natural_text)


if __name__ == "__main__":
    unittest.main()
