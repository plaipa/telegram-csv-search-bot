import re
import string
import unittest

from csvbot.i18n import DEFAULT, LANGS, MESSAGES


def fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class MessagesTest(unittest.TestCase):
    def test_every_language_is_complete_and_consistent(self):
        for key, texts in MESSAGES.items():
            self.assertIn(DEFAULT, texts, key)
            if key == "lang_prompt":  # one multilingual text
                continue
            for lang in LANGS:
                self.assertIn(lang, texts, f"{key} is missing {lang}")
                self.assertEqual(fields(texts[lang]), fields(texts[DEFAULT]), f"{key}/{lang} placeholders")
                for tag in ("b", "code"):  # these messages are sent as HTML
                    self.assertEqual(texts[lang].count(f"<{tag}>"), texts[lang].count(f"</{tag}>"), f"{key}/{lang}")

    def test_no_stray_braces(self):
        for key, texts in MESSAGES.items():
            for lang, text in texts.items():
                self.assertFalse(re.search(r"\{[^}a-z_:,0-9]", text), f"{key}/{lang}")


if __name__ == "__main__":
    unittest.main()
