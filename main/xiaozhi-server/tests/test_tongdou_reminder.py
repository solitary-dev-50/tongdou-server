import base64
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from core.reminder.announcement import (
    fallback_announcement,
    generate_reminder_announcement,
)
from core.reminder.bitmap_renderer import (
    BITMAP_SIZE,
    render_reminder_bitmap,
    render_reminder_bitmap_base64,
)


class FakeLlm:
    def __init__(self, response):
        self.response_text = response

    def response(self, session_id, dialogue):
        midpoint = len(self.response_text) // 2
        yield self.response_text[:midpoint]
        yield self.response_text[midpoint:]


class TongDouReminderAnnouncementTest(unittest.TestCase):
    def test_model_answer_is_used_only_when_exact_text_is_preserved(self):
        text = "下午三点给妈妈打电话"
        result = generate_reminder_announcement(
            FakeLlm(f"到点啦，{text}，可别又忘了。"), "session", text, "zh-CN"
        )
        self.assertEqual(result, f"到点啦，{text}，可别又忘了。")

    def test_changed_reminder_text_falls_back_to_exact_body(self):
        text = "服用 5 毫升药"
        result = generate_reminder_announcement(
            FakeLlm("该服用五毫升药了。"), "session", text, "zh-CN"
        )
        self.assertEqual(result, f"到时间啦，{text}")

    def test_fallback_uses_device_locale(self):
        self.assertEqual(
            fallback_announcement("позвонить маме", "ru-RU"),
            "Напоминание: позвонить маме",
        )


class TongDouReminderBitmapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "C:/Windows/Fonts/msyh.ttc",
        )
        cls.font_path = next((path for path in candidates if Path(path).is_file()), None)

    def test_bitmap_has_fixed_device_format(self):
        if self.font_path is None:
            self.skipTest("没有可用于测试的中文字体")
        with patch.dict(os.environ, {"TONGDOU_REMINDER_FONT": self.font_path}):
            bitmap = render_reminder_bitmap("下午三点给妈妈打电话")
            encoded = render_reminder_bitmap_base64("下午三点给妈妈打电话")
        self.assertEqual(len(bitmap), BITMAP_SIZE)
        self.assertTrue(any(bitmap))
        self.assertEqual(base64.b64decode(encoded), bitmap)

    def test_supported_language_samples_fit(self):
        if self.font_path is None:
            self.skipTest("没有可用于测试的多语言字体")
        samples = (
            "Call mom at three in the afternoon",
            "Позвонить маме в три часа",
            "下午三点给妈妈打电话",
        )
        with patch.dict(os.environ, {"TONGDOU_REMINDER_FONT": self.font_path}):
            for sample in samples:
                with self.subTest(sample=sample):
                    self.assertEqual(len(render_reminder_bitmap(sample)), BITMAP_SIZE)


if __name__ == "__main__":
    unittest.main()
