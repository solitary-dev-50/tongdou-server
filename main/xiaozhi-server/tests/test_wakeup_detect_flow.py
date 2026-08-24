import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.handle.textHandler.listenMessageHandler import ListenTextMessageHandler


class _Logger:
    def bind(self, **_kwargs):
        return self

    def info(self, *_args, **_kwargs):
        pass


class _Connection:
    def __init__(self):
        self.config = {
            "wakeup_words": ["你好铜豆", "HelloTongDou"],
            "enable_greeting": True,
        }
        self.logger = _Logger()
        self.conversation_active = False
        self.client_have_voice = True
        self.last_activity_time = 0

    def reset_audio_states(self):
        pass


class WakeupDetectFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_wakeup_text_reaches_the_fast_greeting_entry(self):
        conn = _Connection()
        start_to_chat = AsyncMock()
        report = Mock()

        with patch(
            "core.handle.textHandler.listenMessageHandler.startToChat",
            start_to_chat,
        ), patch(
            "core.handle.textHandler.listenMessageHandler.enqueue_asr_report",
            report,
        ):
            await ListenTextMessageHandler().handle(
                conn,
                {"type": "listen", "state": "detect", "text": "你好，铜豆"},
            )

        report.assert_called_once_with(conn, "你好，铜豆", [])
        start_to_chat.assert_awaited_once_with(conn, "你好，铜豆")
        self.assertTrue(conn.just_woken_up)

    async def test_non_wakeup_detect_text_keeps_the_text_entry_behavior(self):
        conn = _Connection()
        start_to_chat = AsyncMock()
        report = Mock()

        with patch(
            "core.handle.textHandler.listenMessageHandler.startToChat",
            start_to_chat,
        ), patch(
            "core.handle.textHandler.listenMessageHandler.enqueue_asr_report",
            report,
        ):
            await ListenTextMessageHandler().handle(
                conn,
                {"type": "listen", "state": "detect", "text": "今天天气怎么样"},
            )

        report.assert_called_once_with(conn, "今天天气怎么样", [])
        start_to_chat.assert_awaited_once_with(conn, "今天天气怎么样")


if __name__ == "__main__":
    unittest.main()
