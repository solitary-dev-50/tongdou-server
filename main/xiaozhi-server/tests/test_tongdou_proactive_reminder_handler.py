import json
import queue
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

send_audio_stub = types.ModuleType("core.handle.sendAudioHandle")


async def _send_tts_message_stub(connection, state):
    pass


send_audio_stub.send_tts_message = _send_tts_message_stub
sys.modules.setdefault("core.handle.sendAudioHandle", send_audio_stub)

from core.handle.textHandler.tongdouReminderMessageHandler import (
    TongDouReminderTextMessageHandler,
)


class FakeLogger:
    def bind(self, **kwargs):
        return self

    def info(self, message):
        pass

    def error(self, message):
        raise AssertionError(message)


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, payload):
        self.messages.append(json.loads(payload))


class FakeLlm:
    def response(self, session_id, dialogue):
        event = dialogue[-1]["content"]
        if "drink_water" in event:
            yield "喝口水吧，别把自己晾成桌面摆件。"
        else:
            yield "起来活动一下，桌子可没打算收你当永久住户。"


class FakeTts:
    def __init__(self):
        self.tts_text_queue = queue.Queue()
        self.stored = {}

    def store_tts_text(self, sentence_id, text):
        self.stored[sentence_id] = text


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


class FakeConnection:
    def __init__(self):
        self.llm = FakeLlm()
        self.tts = FakeTts()
        self.executor = ImmediateExecutor()
        self.websocket = FakeWebSocket()
        self.logger = FakeLogger()
        self.session_id = "test-session"
        self.sentence_id = None
        self.client_abort = False
        self.client_is_speaking = False
        self.conversation_exit_pending = False


class TongDouProactiveReminderHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def _handle(self, payload):
        connection = FakeConnection()
        handler = TongDouReminderTextMessageHandler()
        with patch(
            "core.handle.textHandler.tongdouReminderMessageHandler.send_tts_message",
            new=AsyncMock(),
        ) as send_tts:
            await handler.handle(connection, payload)
        return connection, send_tts

    async def test_activity_event_is_accepted_and_queued_for_tts(self):
        connection, send_tts = await self._handle(
            {
                "type": "tongdou_reminder",
                "id": 0xF0000001,
                "text": "",
                "locale": "zh-CN",
                "proactive_event": "desk_activity_break",
            }
        )
        self.assertEqual(connection.websocket.messages[0]["state"], "accepted")
        self.assertTrue(connection.tts.stored)
        self.assertGreaterEqual(connection.tts.tts_text_queue.qsize(), 3)
        send_tts.assert_awaited_once_with(connection, "start")

    async def test_hydration_event_is_accepted_and_queued_for_tts(self):
        connection, send_tts = await self._handle(
            {
                "type": "tongdou_reminder",
                "id": 0xF0000002,
                "text": "",
                "locale": "zh-CN",
                "proactive_event": "drink_water",
            }
        )
        self.assertEqual(connection.websocket.messages[0]["state"], "accepted")
        self.assertTrue(connection.tts.stored)
        send_tts.assert_awaited_once_with(connection, "start")

    async def test_unknown_proactive_event_is_rejected(self):
        connection, send_tts = await self._handle(
            {
                "type": "tongdou_reminder",
                "id": 0xF0000003,
                "text": "",
                "locale": "zh-CN",
                "proactive_event": "unknown_event",
            }
        )
        self.assertEqual(connection.websocket.messages[0]["state"], "failed")
        self.assertEqual(
            connection.websocket.messages[0]["reason"], "invalid_reminder"
        )
        self.assertFalse(connection.tts.stored)
        send_tts.assert_not_awaited()

    async def test_regular_reminder_still_requires_valid_id_and_text(self):
        connection, send_tts = await self._handle(
            {
                "type": "tongdou_reminder",
                "id": 0,
                "text": "下午三点给妈妈打电话",
                "locale": "zh-CN",
            }
        )
        self.assertEqual(connection.websocket.messages[0]["state"], "failed")
        self.assertEqual(
            connection.websocket.messages[0]["reason"], "invalid_reminder"
        )
        send_tts.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
