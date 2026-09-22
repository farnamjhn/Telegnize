import unittest
from infrastructure.nlp.normalizer import TextNormalizer


class TestTextNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = TextNormalizer.get_instance()

    def test_detect_language(self):
        self.assertEqual(self.normalizer.detect_language("سلام، چطوری؟"), "fa")
        self.assertEqual(self.normalizer.detect_language("Hello, how are you?"), "en")
        self.assertEqual(self.normalizer.detect_language("123456 !!!"), "other")
        self.assertEqual(self.normalizer.detect_language(""), "unknown")

    def test_normalize_persian(self):
        # Hazm should handle ZWNJ for 'می روم' -> 'می‌روم'
        raw = "سلام   می روم   به خانه ی  دوست"
        norm, lang = self.normalizer.normalize(raw)
        self.assertEqual(lang, "fa")
        self.assertIn("می‌روم", norm)

    def test_normalize_english(self):
        raw = "Hello   World!   How ARE you?"
        norm, lang = self.normalizer.normalize(raw)
        self.assertEqual(lang, "en")
        self.assertEqual(norm, "hello world! how are you?")

    def test_repeated_characters_cleanup(self):
        raw = "سلااااااام دوست مننننن"
        norm, _ = self.normalizer.normalize(raw)
        self.assertNotIn("اااااا", norm)

    def test_is_question(self):
        self.assertTrue(self.normalizer.is_question("چرا اینطوری شد؟"))
        self.assertTrue(self.normalizer.is_question("Why did this happen?"))
        self.assertFalse(self.normalizer.is_question("این یک جمله خبری است."))

    def test_word_count(self):
        self.assertEqual(self.normalizer.word_count("یک دو سه چهار پنج"), 5)
        self.assertEqual(self.normalizer.word_count("one two three four five"), 5)


if __name__ == "__main__":
    unittest.main()
