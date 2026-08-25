import json
import unittest
from unittest.mock import AsyncMock, patch

from core.providers.tools.device_mcp.mcp_executor import DeviceMCPExecutor


class FakeLogger:
    def error(self, message):
        raise AssertionError(message)


class FakeMcpClient:
    def __init__(self):
        self.name_mapping = {
            "tongdou_reminder_create": "tongdou.reminder.create"
        }

    async def is_ready(self):
        return True

    def has_tool(self, name):
        return name == "tongdou_reminder_create"


class FakeConnection:
    def __init__(self):
        self.mcp_client = FakeMcpClient()
        self.logger = FakeLogger()


class TongDouReminderMcpTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_reminder_gets_server_rendered_bitmap(self):
        connection = FakeConnection()
        executor = DeviceMCPExecutor(connection)
        call = AsyncMock(return_value='{"ok": true}')

        with patch(
            "core.providers.tools.device_mcp.mcp_executor.render_reminder_bitmap_base64",
            return_value="rendered-bitmap",
        ), patch(
            "core.providers.tools.device_mcp.mcp_executor.call_mcp_tool", call
        ):
            await executor.execute(
                connection,
                "tongdou_reminder_create",
                {"delaySeconds": 30, "text": "喝水"},
            )

        sent_arguments = json.loads(call.await_args.args[3])
        self.assertEqual(sent_arguments["text"], "喝水")
        self.assertEqual(
            sent_arguments["displayBitmapBase64"], "rendered-bitmap"
        )


if __name__ == "__main__":
    unittest.main()
