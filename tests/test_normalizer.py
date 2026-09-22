import unittest

from domain.models.language import Language
from infrastructure.nlp.normalizer import TextNormalizer


class TestTextNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = TextNormalizer()

    def test_detect_language(self):
        self.assertIs(self.normalizer.detect_language("سلام، چطوری؟"), Language.PERSIAN)
        self.assertIs(
            self.normalizer.detect_language("Hello, how are you?"), Language.ENGLISH
        )
        self.assertIs(self.normalizer.detect_language("123456 !!!"), Language.OTHER)
        self.assertIs(self.normalizer.detect_language(""), Language.UNKNOWN)

    def test_detect_mixed_script(self):
        self.assertIs(
            self.normalizer.detect_language("سلام hello دوست friend"), Language.MIXED
        )

    def test_normalize_persian_applies_half_space(self):
        norm, language = self.normalizer.normalize("سلام   می روم   به خانه ی  دوست")
        self.assertIs(language, Language.PERSIAN)
        self.assertIn("می‌روم", norm)

    def test_normalize_english_folds_case_and_whitespace(self):
        norm, language = self.normalizer.normalize("Hello   World!   How ARE you?")
        self.assertIs(language, Language.ENGLISH)
        self.assertEqual(norm, "hello world! how are you?")

    def test_repeated_characters_are_collapsed(self):
        norm, _ = self.normalizer.normalize("سلااااااام دوست مننننن")
        self.assertNotIn("اااااا", norm)

    def test_blank_text_is_unknown(self):
        self.assertEqual(self.normalizer.normalize("   "), ("", Language.UNKNOWN))

    def test_is_question_handles_both_scripts(self):
        self.assertTrue(self.normalizer.is_question("چرا اینطوری شد؟"))
        self.assertTrue(self.normalizer.is_question("Why did this happen?"))
        self.assertFalse(self.normalizer.is_question("این یک جمله خبری است."))

    def test_word_count_is_unicode_aware(self):
        self.assertEqual(self.normalizer.word_count("یک دو سه چهار پنج"), 5)
        self.assertEqual(self.normalizer.word_count("one two three four five"), 5)


if __name__ == "__main__":
    unittest.main()
