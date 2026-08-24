import json
import hmac
import base64
import hashlib
import asyncio
import websockets
import gc
import time
import opuslib_next
from time import mktime
from datetime import datetime
from urllib.parse import urlencode
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from config.logger import setup_logging
from wsgiref.handlers import format_date_time
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()

# 帧状态常量
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识
XUNFEI_ASR_HOST = "iat-api.xfyun.cn"
XUNFEI_ASR_PATH = "/v2/iat"
XUNFEI_ASR_URL = f"wss://{XUNFEI_ASR_HOST}{XUNFEI_ASR_PATH}"


class ASRProvider(ASRProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__()
        self.interface_type = InterfaceType.STREAM
        self.config = config
        self.text = ""
        self.asr_ws = None
        self.forward_task = None
        self.is_processing = False
        self.server_ready = False
        self.final_frame_sent = False
        self.decoder = None

        # 讯飞配置
        self.app_id = config.get("app_id")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")

        if not all([self.app_id, self.api_key, self.api_secret]):
            raise ValueError("必须提供app_id、api_key和api_secret")

        # 识别参数
        domain = config.get("domain", "iat")
        if domain == "slm":
            domain = "iat"

        self.iat_params = {
            "domain": domain,
            "language": config.get("language", "zh_cn"),
            "accent": config.get("accent", "mandarin"),
            "dwa": config.get("dwa", "wpgs"),
            "vad_eos": int(config.get("vad_eos", 5000) or 5000),
        }
        self.current_iat_params = dict(self.iat_params)

        self.output_dir = config.get("output_dir", "tmp/")
        self.delete_audio_file = delete_audio_file

    def create_url(self) -> str:
        """生成认证URL"""
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + XUNFEI_ASR_HOST + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + XUNFEI_ASR_PATH + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding="utf-8")

        authorization_origin = (
            'api_key="%s", algorithm="%s", headers="%s", signature="%s"'
            % (self.api_key, "hmac-sha256", "host date request-line", signature_sha)
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
            encoding="utf-8"
        )

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": XUNFEI_ASR_HOST,
        }

        # 拼接鉴权参数，生成url
        url = XUNFEI_ASR_URL + "?" + urlencode(v)
        return url

    async def _connect_asr(self, ws_url: str):
        options = {
            "max_size": 1000000000,
            "ping_interval": None,
            "ping_timeout": None,
            "close_timeout": 10,
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            return await websockets.connect(
                ws_url, additional_headers=headers, **options
            )
        except TypeError:
            return await websockets.connect(ws_url, extra_headers=headers, **options)

    async def open_audio_channels(self, conn: "ConnectionHandler"):
        await super().open_audio_channels(conn)

    async def receive_audio(self, conn: "ConnectionHandler", audio, audio_have_voice):
        # 先调用父类方法处理基础逻辑
        await super().receive_audio(conn, audio, audio_have_voice)

        # 如果本次有声音，且之前没有建立连接
        if audio_have_voice and self.asr_ws is None and not self.is_processing:
            try:
                await self._start_recognition(conn)
            except Exception as e:
                logger.bind(tag=TAG).error(f"建立ASR连接失败: {str(e)}")
                await self._cleanup()
                return
            return

        # 发送当前音频数据
        if self.asr_ws and self.is_processing and self.server_ready:
            try:
                if not self.final_frame_sent:
                    pcm_audio = self._decode_audio_frame(conn, audio)
                    if pcm_audio:
                        await self._send_audio_frame(pcm_audio, STATUS_CONTINUE_FRAME)
                if conn.client_voice_stop and not self.final_frame_sent:
                    await self._send_stop_request()
            except Exception as e:
                logger.bind(tag=TAG).warning(f"发送音频数据时发生错误: {e}")
                await self._cleanup()

    async def _start_recognition(self, conn: "ConnectionHandler"):
        """开始识别会话"""
        try:
            self.is_processing = True
            started_at = getattr(conn, "voice_debug_started_at", 0)
            elapsed_ms = int(time.time() * 1000 - started_at) if started_at else 0
            # 建立WebSocket连接
            ws_url = self.create_url()
            logger.bind(tag=TAG).info(f"正在连接ASR服务: {ws_url[:50]}...")
            logger.bind(tag=TAG).info(
                "语音时间线 asr_connect_start: "
                f"elapsed_ms={elapsed_ms}, mode={conn.client_listen_mode}, "
                f"cached_audio={len(conn.asr_audio)}"
            )

            self.current_iat_params = dict(self.iat_params)
            # 如果为手动模式,设置超时时长为一分钟
            if conn.client_listen_mode == "manual":
                self.current_iat_params["vad_eos"] = 60000

            self.asr_ws = await self._connect_asr(ws_url)

            logger.bind(tag=TAG).info("ASR WebSocket连接已建立")
            elapsed_ms = int(time.time() * 1000 - started_at) if started_at else 0
            logger.bind(tag=TAG).info(
                "语音时间线 asr_connected: "
                f"elapsed_ms={elapsed_ms}, mode={conn.client_listen_mode}, "
                f"cached_audio={len(conn.asr_audio)}"
            )
            self.server_ready = False
            self.final_frame_sent = False
            self.decoder = None
            self.forward_task = asyncio.create_task(self._forward_results(conn))

            cached_audio = conn.asr_audio[-10:] if conn.asr_audio else []
            first_frame_sent = False
            cached_pcm_frames = 0
            cached_pcm_bytes = 0
            for cached_packet in cached_audio:
                try:
                    pcm_frame = self._decode_audio_frame(conn, cached_packet)
                    if not pcm_frame:
                        continue
                    status = STATUS_FIRST_FRAME if not first_frame_sent else STATUS_CONTINUE_FRAME
                    await self._send_audio_frame(pcm_frame, status)
                    first_frame_sent = True
                    cached_pcm_frames += 1
                    cached_pcm_bytes += len(pcm_frame)
                except Exception as e:
                    logger.bind(tag=TAG).info(f"发送缓存音频数据时发生错误: {e}")
                    break

            if first_frame_sent:
                self.server_ready = True
                logger.bind(tag=TAG).info("已发送首帧，开始识别")
                elapsed_ms = int(time.time() * 1000 - started_at) if started_at else 0
                logger.bind(tag=TAG).info(
                    "语音时间线 asr_first_frame_sent: "
                    f"elapsed_ms={elapsed_ms}, mode={conn.client_listen_mode}, "
                    f"cached_audio={len(cached_audio)}, "
                    f"cached_pcm_frames={cached_pcm_frames}, "
                    f"cached_pcm_bytes={cached_pcm_bytes}"
                )

        except Exception as e:
            logger.bind(tag=TAG).error(f"建立ASR连接失败: {str(e)}")
            if hasattr(e, "__cause__") and e.__cause__:
                logger.bind(tag=TAG).error(f"错误原因: {str(e.__cause__)}")
            if self.asr_ws:
                await self.asr_ws.close()
                self.asr_ws = None
            self.is_processing = False
            raise

    async def _send_audio_frame(self, audio_data: bytes, status: int):
        """发送音频帧"""
        if not self.asr_ws:
            return

        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        frame_data = {
            "data": {
                "status": status,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": audio_b64,
            },
        }
        if status == STATUS_FIRST_FRAME:
            frame_data["common"] = {"app_id": self.app_id}
            frame_data["business"] = self.current_iat_params

        await self.asr_ws.send(json.dumps(frame_data, ensure_ascii=False))
        if status == STATUS_LAST_FRAME:
            self.final_frame_sent = True

    def _decode_audio_frame(self, conn: "ConnectionHandler", audio_data: bytes) -> bytes:
        if not audio_data:
            return b""
        if getattr(conn, "audio_format", "opus") == "pcm":
            return audio_data
        if self.decoder is None:
            self.decoder = opuslib_next.Decoder(16000, 1)
        return self.decoder.decode(audio_data, 960)

    async def _forward_results(self, conn: "ConnectionHandler"):
        """转发识别结果"""
        try:
            while not conn.stop_event.is_set():
                try:
                    response = await asyncio.wait_for(self.asr_ws.recv(), timeout=60)
                    result = json.loads(response)
                    logger.bind(tag=TAG).debug(f"收到ASR结果: {result}")

                    data = result.get("data", {})
                    code = result.get("code", 0)
                    status = data.get("status", 0)
                    text_ws = data.get("result", {}).get("ws", [])
                    text_piece = ""
                    for i in text_ws:
                        for j in i.get("cw", []):
                            text_piece += j.get("w", "")
                    logger.bind(tag=TAG).info(
                        "讯飞ASR返回: "
                        f"code={code}, status={status}, "
                        f"text_piece={text_piece or '<empty>'}, "
                        f"total_text={self.text or '<empty>'}"
                    )

                    if code != 0:
                        logger.bind(tag=TAG).error(
                            f"识别错误，错误码: {code}, 消息: {result.get('message', '')}"
                        )
                        if code in [10114, 10160]:  # 连接问题
                            break
                        continue

                    # 处理识别结果
                    for i in text_ws:
                        for j in i.get("cw", []):
                            w = j.get("w", "")
                            self.text += w

                    if status == 2:
                        logger.bind(tag=TAG).info(
                            f"收到最终识别结果，触发处理: text={self.text or '<empty>'}"
                        )
                        await self.handle_voice_stop(conn, conn.asr_audio)
                        break

                except asyncio.TimeoutError:
                    logger.bind(tag=TAG).error(
                        f"接收结果超时: final_frame_sent={self.final_frame_sent}, "
                        f"text={self.text or '<empty>'}"
                    )
                    break
                except websockets.ConnectionClosed:
                    logger.bind(tag=TAG).info("ASR服务连接已关闭")
                    self.is_processing = False
                    break
                except Exception as e:
                    logger.bind(tag=TAG).error(f"处理ASR结果时发生错误: {str(e)}")
                    if hasattr(e, "__cause__") and e.__cause__:
                        logger.bind(tag=TAG).error(f"错误原因: {str(e.__cause__)}")
                    self.is_processing = False
                    break

        except Exception as e:
            logger.bind(tag=TAG).error(f"ASR结果转发任务发生错误: {str(e)}")
            if hasattr(e, "__cause__") and e.__cause__:
                logger.bind(tag=TAG).error(f"错误原因: {str(e.__cause__)}")
        finally:
            # 清理连接资源
            await self._cleanup()
            conn.reset_audio_states()

    async def handle_voice_stop(
        self, conn: "ConnectionHandler", asr_audio_task: List[bytes]
    ):
        """处理语音停止，发送最后一帧并处理识别结果"""
        try:
            # 先发送最后一帧表示音频结束
            if self.asr_ws and self.is_processing:
                try:
                    if not self.final_frame_sent:
                        await self._send_audio_frame(b"", STATUS_LAST_FRAME)
                        logger.bind(tag=TAG).debug(f"已发送停止请求")

                    await asyncio.sleep(0.25)
                except Exception as e:
                    logger.bind(tag=TAG).error(f"发送停止请求失败: {e}")

            await super().handle_voice_stop(conn, asr_audio_task)
        except Exception as e:
            logger.bind(tag=TAG).error(f"处理语音停止失败: {e}")
            import traceback

            logger.bind(tag=TAG).debug(f"异常详情: {traceback.format_exc()}")

    def stop_ws_connection(self):
        if self.asr_ws:
            asyncio.create_task(self.asr_ws.close())
            self.asr_ws = None
        self.is_processing = False

    async def _send_stop_request(self):
        """发送停止识别请求（不关闭连接）"""
        if self.asr_ws:
            try:
                if not self.final_frame_sent:
                    await self._send_audio_frame(b"", STATUS_LAST_FRAME)
                    logger.bind(tag=TAG).info(
                        f"已发送讯飞ASR最后一帧: text={self.text or '<empty>'}"
                    )
                else:
                    logger.bind(tag=TAG).info("讯飞ASR最后一帧此前已发送")
            except Exception as e:
                logger.bind(tag=TAG).error(f"发送停止请求失败: {e}")

    async def _cleanup(self):
        """清理资源（关闭连接）"""
        logger.bind(tag=TAG).debug(
            f"开始ASR会话清理 | 当前状态: processing={self.is_processing}, server_ready={self.server_ready}"
        )

        # 状态重置
        self.is_processing = False
        self.server_ready = False
        self.final_frame_sent = False
        self.decoder = None
        self.current_iat_params = dict(self.iat_params)
        logger.bind(tag=TAG).debug("ASR状态已重置")

        # 关闭连接
        if self.asr_ws:
            try:
                logger.bind(tag=TAG).debug("正在关闭WebSocket连接")
                await asyncio.wait_for(self.asr_ws.close(), timeout=2.0)
                logger.bind(tag=TAG).debug("WebSocket连接已关闭")
            except Exception as e:
                logger.bind(tag=TAG).error(f"关闭WebSocket连接失败: {e}")
            finally:
                self.asr_ws = None

        # 清理任务引用
        self.forward_task = None

        logger.bind(tag=TAG).debug("ASR会话清理完成")

    async def speech_to_text(self, opus_data, session_id, audio_format, artifacts=None):
        """获取识别结果"""
        result = self.text
        self.text = ""
        return result, None

    async def close(self):
        """资源清理方法"""
        if self.asr_ws:
            await self.asr_ws.close()
            self.asr_ws = None
        if self.forward_task:
            self.forward_task.cancel()
            try:
                await self.forward_task
            except asyncio.CancelledError:
                pass
            self.forward_task = None
        self.is_processing = False

        self.decoder = None
