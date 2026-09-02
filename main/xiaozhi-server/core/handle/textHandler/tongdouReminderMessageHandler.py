import asyncio
import json
import uuid
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.sendAudioHandle import send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from core.reminder.announcement import generate_reminder_announcement


TAG = __name__
MAX_REMINDER_TEXT_BYTES = 95
PROACTIVE_EVENTS = {"desk_activity_break", "drink_water"}


class TongDouReminderTextMessageHandler(TextMessageHandler):
    """处理铜豆到期提醒，不把提醒伪装成一轮用户对话。"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.TONGDOU_REMINDER

    async def handle(
        self, conn: "ConnectionHandler", msg_json: Dict[str, Any]
    ) -> None:
        reminder_id = msg_json.get("id")
        text = msg_json.get("text") or ""
        locale = str(msg_json.get("locale") or "en-GB")
        proactive_event = str(msg_json.get("proactive_event") or "").strip()
        is_proactive = proactive_event in PROACTIVE_EVENTS
        if (
            not isinstance(reminder_id, int)
            or isinstance(reminder_id, bool)
            or reminder_id <= 0
            or not isinstance(text, str)
            or (not is_proactive and not text.strip())
            or (not is_proactive and len(text.strip().encode("utf-8")) > MAX_REMINDER_TEXT_BYTES)
            or (proactive_event and not is_proactive)
        ):
            await self._send_status(conn, reminder_id, "failed", "invalid_reminder")
            return

        text = text.strip()
        if (
            conn.llm is None
            or conn.tts is None
            or conn.executor is None
            or getattr(conn, "conversation_exit_pending", False)
            or getattr(conn, "client_is_speaking", False)
        ):
            await self._send_status(conn, reminder_id, "failed", "backend_busy")
            return

        sentence_id = uuid.uuid4().hex
        conn.sentence_id = sentence_id
        conn.client_abort = False
        await self._send_status(conn, reminder_id, "accepted")
        await send_tts_message(conn, "start")
        conn.client_is_speaking = True
        conn.executor.submit(
            self._generate_and_queue,
            conn,
            reminder_id,
            sentence_id,
            text,
            locale,
            proactive_event,
        )

    def _generate_and_queue(
        self,
        conn: "ConnectionHandler",
        reminder_id: int,
        sentence_id: str,
        text: str,
        locale: str,
        proactive_event: str,
    ) -> None:
        try:
            announcement = generate_reminder_announcement(
                conn.llm, conn.session_id, text, locale, proactive_event
            )
            if conn.sentence_id != sentence_id or conn.client_abort:
                raise RuntimeError("reminder_superseded")
            conn.tts.store_tts_text(sentence_id, announcement)
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=announcement,
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )
            conn.logger.bind(tag=TAG).info(
                f"提醒播报已进入语音队列: id={reminder_id}, text={announcement}"
            )
        except Exception as error:
            conn.logger.bind(tag=TAG).error(
                f"提醒播报生成失败: id={reminder_id}, error={error}"
            )
            asyncio.run_coroutine_threadsafe(
                self._fail_started_reminder(
                    conn, reminder_id, sentence_id, "announcement_generation_failed"
                ),
                conn.loop,
            )

    async def _fail_started_reminder(
        self,
        conn: "ConnectionHandler",
        reminder_id: int,
        sentence_id: str,
        reason: str,
    ) -> None:
        if conn.sentence_id == sentence_id:
            await send_tts_message(conn, "stop")
        await self._send_status(conn, reminder_id, "failed", reason)

    @staticmethod
    async def _send_status(
        conn: "ConnectionHandler",
        reminder_id,
        state: str,
        reason: str = "",
    ) -> None:
        message = {
            "type": TextMessageType.TONGDOU_REMINDER.value,
            "state": state,
            "session_id": conn.session_id,
            "id": reminder_id,
        }
        if reason:
            message["reason"] = reason
        await conn.websocket.send(json.dumps(message, ensure_ascii=False))
