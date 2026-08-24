import asyncio
import json
import queue
import time
import unittest
from types import SimpleNamespace

from core.handle.conversationExitHandle import (
    begin_conversation_exit,
    finish_conversation_exit,
    is_semantic_exit,
)
from core.handle.receiveAudioHandle import no_voice_close_connect
from core.handle.sendAudioHandle import send_tts_message
from core.connection import ConnectionHandler


class _Logger:
    def bind(self, **_kwargs):
        return self

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _WebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


class _Tts:
    def __init__(self):
        self.tts_text_queue = queue.Queue()
        self.tts_audio_queue = queue.Queue()
        self.stored = []

    def store_tts_text(self, sentence_id, text):
        self.stored.append((sentence_id, text))

    def tts_one_sentence(
        self,
        _conn,
        _content_type,
        content_detail=None,
        content_file=None,
        sentence_id=None,
    ):
        self.tts_text_queue.put(
            SimpleNamespace(
                sentence_type="middle",
                content_detail=content_detail,
                content_file=content_file,
                sentence_id=sentence_id,
            )
        )


class _Connection:
    def __init__(self):
        self.session_id = "test-session"
        self.websocket = _WebSocket()
        self.tts = _Tts()
        self.logger = _Logger()
        self.config = {"enable_stop_tts_notify": False}
        self.close_after_chat = False
        self.client_abort = False
        self.client_is_speaking = False
        self.conversation_exit_pending = False
        self.conversation_exit_reason = None
        self.conversation_goodbye_sent = False
        self.sentence_id = None
        self.dialogue = SimpleNamespace(put=lambda _message: None)
        self.closed = False
        self.last_activity_time = 0.0

    def reset_audio_states(self):
        pass

    def clear_queues(self):
        pass

    def clearSpeakStatus(self):
        self.client_is_speaking = False

    async def close(self):
        self.closed = True


class ConversationExitSequenceTest(unittest.IsolatedAsyncioTestCase):
    def test_conservative_semantic_exit(self):
        self.assertTrue(is_semantic_exit("好了没事了你先退下吧"))
        self.assertFalse(is_semantic_exit("你知道退下是什么意思吗"))

    async def test_farewell_stop_goodbye_order(self):
        conn = _Connection()

        started = await begin_conversation_exit(
            conn, "semantic", "好了没事了你先退下吧"
        )
        self.assertTrue(started)
        self.assertTrue(conn.conversation_exit_pending)
        self.assertEqual(conn.conversation_exit_reason, "semantic")
        self.assertEqual(conn.tts.tts_text_queue.qsize(), 3)

        await send_tts_message(conn, "stop")
        await finish_conversation_exit(conn)

        self.assertEqual(
            [message["type"] for message in conn.websocket.messages],
            ["stt", "tts", "tts", "goodbye"],
        )
        self.assertEqual(
            [
                message.get("state")
                for message in conn.websocket.messages
                if message["type"] == "tts"
            ],
            ["start", "stop"],
        )
        self.assertEqual(conn.websocket.messages[-1]["reason"], "semantic")
        self.assertTrue(conn.closed)

    async def test_no_voice_uses_the_same_exit_sequence(self):
        conn = _Connection()
        conn.config["close_connection_no_voice_time"] = 120
        conn.last_activity_time = time.time() * 1000 - 121_000

        should_stop_receiving = await no_voice_close_connect(conn, have_voice=False)
        self.assertTrue(should_stop_receiving)
        self.assertTrue(conn.conversation_exit_pending)
        self.assertEqual(conn.conversation_exit_reason, "no_voice")

        await send_tts_message(conn, "stop")
        await finish_conversation_exit(conn)

        self.assertEqual(
            [message["type"] for message in conn.websocket.messages],
            ["tts", "tts", "goodbye"],
        )
        self.assertEqual(
            [
                message.get("state")
                for message in conn.websocket.messages
                if message["type"] == "tts"
            ],
            ["start", "stop"],
        )
        self.assertEqual(conn.websocket.messages[-1]["reason"], "no_voice")
        self.assertTrue(conn.closed)

    async def test_idle_connection_timeout_closes_without_farewell(self):
        conn = ConnectionHandler.__new__(ConnectionHandler)
        conn.stop_event = asyncio.Event()
        conn.last_activity_time = time.time() * 1000 - 1_000
        conn.first_activity_time = conn.last_activity_time
        conn.need_bind = False
        conn.timeout_seconds = 0
        conn.conversation_active = False
        conn.logger = _Logger()
        conn.websocket = _WebSocket()
        conn.closed = False

        async def close(_ws=None):
            conn.closed = True
            conn.stop_event.set()

        conn.close = close
        await conn._check_timeout()

        self.assertTrue(conn.closed)
        self.assertEqual(conn.websocket.messages, [])


if __name__ == "__main__":
    unittest.main()
