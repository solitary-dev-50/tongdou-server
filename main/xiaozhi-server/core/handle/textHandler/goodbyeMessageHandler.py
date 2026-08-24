from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.conversationExitHandle import begin_conversation_exit
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType


class GoodbyeTextMessageHandler(TextMessageHandler):
    """把设备发来的 goodbye 当作手动退出请求交给统一出口。"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.GOODBYE

    async def handle(
        self, conn: "ConnectionHandler", msg_json: Dict[str, Any]
    ) -> None:
        await begin_conversation_exit(conn, "manual")
