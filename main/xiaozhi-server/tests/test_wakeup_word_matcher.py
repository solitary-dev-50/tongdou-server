import unittest

from core.utils.wakeup_word_matcher import (
    matches_wakeup_word,
    normalize_wakeup_word,
)


class WakeupWordMatcherTest(unittest.TestCase):
    def test_chinese_spaces_and_punctuation_are_equivalent(self):
        self.assertEqual(normalize_wakeup_word("你好， 铜豆！"), "你好铜豆")
        self.assertTrue(matches_wakeup_word("你好 铜豆", ["你好铜豆"]))
        self.assertTrue(matches_wakeup_word("你好，铜豆。", ["你好 铜豆"]))

    def test_latin_case_and_spaces_are_equivalent(self):
        self.assertTrue(
            matches_wakeup_word("HELLO tongdou", ["HelloTongDou"])
        )
        self.assertTrue(
            matches_wakeup_word("Hello-TongDou", "你好铜豆;Hello TongDou")
        )

    def test_non_wakeup_text_does_not_match(self):
        configured = ["你好铜豆", "HelloTongDou"]
        self.assertFalse(matches_wakeup_word("铜豆今天天气怎么样", configured))
        self.assertFalse(matches_wakeup_word("嘿，你好呀", configured))
        self.assertFalse(matches_wakeup_word("", configured))
        self.assertFalse(matches_wakeup_word("你好铜豆", None))


if __name__ == "__main__":
    unittest.main()
