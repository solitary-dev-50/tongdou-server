import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from core.utils.dialogue import Message


TAG = __name__

DEFAULT_FAREWELL_TEXT = "好，那我先退下啦。有需要再叫我。"
NO_VOICE_FAREWELL_TEXT = "你好像去忙啦，那我先安静待着。有需要再叫我。"


def is_semantic_exit(text: str) -> bool:
    """只识别含义明确、误判风险低的退出说法。"""
    if not text:
        return False

    return text.endswith(
        (
            "退下",
            "退下吧",
            "先退下",
            "先退下吧",
            "不聊了",
            "先不聊了",
            "结束对话",
            "先这样吧",
            "你去休息吧",
        )
    )


def mark_conversation_exit(conn: "ConnectionHandler", reason: str) -> bool:
    """把会话单向切换到正常退出状态。"""
    if getattr(conn, "conversation_exit_pending", False):
        return False

    conn.conversation_exit_pending = True
    conn.conversation_exit_reason = reason
    conn.conversation_goodbye_sent = False
    conn.close_after_chat = True
    conn.client_abort = False
    conn.logger.bind(tag=TAG).info(
        "conversation_exit_requested: "
        f"reason={reason}, session={conn.session_id}"
    )
    return True


async def begin_conversation_exit(
    conn: "ConnectionHandler",
    reason: str,
    user_text: str | None = None,
) -> bool:
    """停止当前回合，并把服务器生成的告别语送入原有语音合成队列。"""
    if not mark_conversation_exit(conn, reason):
        return False

    conn.reset_audio_states()
    conn.clear_queues()
    conn.client_abort = False

    farewell_text = (
        NO_VOICE_FAREWELL_TEXT if reason in ("no_voice", "server_timeout")
        else DEFAULT_FAREWELL_TEXT
    )
    sentence_id = uuid.uuid4().hex
    conn.sentence_id = sentence_id

    from core.handle.sendAudioHandle import send_stt_message, send_tts_message

    if user_text:
        await send_stt_message(conn, user_text)
        conn.dialogue.put(Message(role="user", content=user_text))
    else:
        await send_tts_message(conn, "start")
        conn.client_is_speaking = True

    if conn.tts is None:
        conn.logger.bind(tag=TAG).error(
            "conversation_exit_farewell_failed: tts_not_ready"
        )
        await finish_conversation_exit(conn)
        return True

    conn.tts.store_tts_text(sentence_id, farewell_text)
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=sentence_id,
            sentence_type=SentenceType.FIRST,
            content_type=ContentType.ACTION,
        )
    )
    conn.tts.tts_one_sentence(
        conn,
        ContentType.TEXT,
        content_detail=farewell_text,
        sentence_id=sentence_id,
    )
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=sentence_id,
            sentence_type=SentenceType.LAST,
            content_type=ContentType.ACTION,
        )
    )
    conn.dialogue.put(Message(role="assistant", content=farewell_text))
    conn.logger.bind(tag=TAG).info(
        "conversation_exit_farewell_queued: "
        f"reason={reason}, text={farewell_text}"
    )
    return True


async def finish_conversation_exit(conn: "ConnectionHandler") -> bool:
    """在告别音频发送完成后发出唯一的 goodbye，并关闭本次会话。"""
    if not getattr(conn, "conversation_exit_pending", False):
        return False
    if getattr(conn, "conversation_goodbye_sent", False):
        return True

    reason = getattr(conn, "conversation_exit_reason", "server") or "server"
    message = {
        "type": "goodbye",
        "session_id": conn.session_id,
        "reason": reason,
    }
    try:
        await conn.websocket.send(json.dumps(message))
        conn.conversation_goodbye_sent = True
        conn.logger.bind(tag=TAG).info(
            "conversation_goodbye_sent: "
            f"reason={reason}, session={conn.session_id}"
        )
    finally:
        await conn.close()
    return True
