import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.providers.asr.xunfei_stream import ASRProvider


class _WebSocket:
    def __init__(self):
        self.closed = False
        self.state = SimpleNamespace(name="OPEN")

    async def close(self):
        self.closed = True
        self.state.name = "CLOSED"


class XunfeiAsrPreconnectTest(unittest.IsolatedAsyncioTestCase):
    def _provider(self):
        return ASRProvider(
            {
                "app_id": "test-app",
                "api_key": "test-key",
                "api_secret": "test-secret",
            },
            True,
        )

    def _connection(self):
        return SimpleNamespace(
            voice_debug_started_at=int(time.time() * 1000),
            client_listen_mode="auto",
        )

    async def test_preconnect_is_reused_when_voice_arrives(self):
        provider = self._provider()
        conn = self._connection()
        websocket = _WebSocket()

        async def connect(_url):
            return websocket

        provider._connect_asr = connect
        provider._start_preconnect(conn)
        first_task = provider.preconnect_task
        conn.voice_debug_started_at += 1
        provider._start_preconnect(conn)
        self.assertIs(provider.preconnect_task, first_task)

        reused = await provider._take_preconnected_ws()

        self.assertIs(reused, websocket)
        self.assertIsNotNone(first_task)
        self.assertFalse(websocket.closed)
        self.assertIsNone(provider.preconnect_task)
        self.assertIsNone(provider.preconnect_expiry_task)

    async def test_unused_preconnect_expires(self):
        provider = self._provider()
        conn = self._connection()
        websocket = _WebSocket()

        async def connect(_url):
            return websocket

        provider._connect_asr = connect
        with patch(
            "core.providers.asr.xunfei_stream.ASR_PRECONNECT_MAX_AGE_SECONDS",
            0.01,
        ):
            provider._start_preconnect(conn)
            await asyncio.sleep(0.03)

        self.assertTrue(websocket.closed)
        self.assertIsNone(provider.preconnect_task)
        self.assertIsNone(provider.preconnect_expiry_task)


if __name__ == "__main__":
    unittest.main()
