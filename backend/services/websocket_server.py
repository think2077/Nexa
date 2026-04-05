"""
WebSocket Server - 核心服务器
处理 ESP32 连接、音频流接收、AI 响应推送
"""
import asyncio
import json
import base64
import numpy as np
from typing import Dict, Set, Optional
from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
from loguru import logger
from collections import deque

from config import (
    WEBSOCKET_HOST, WEBSOCKET_PORT,
    AUDIO_SAMPLE_RATE, AUDIO_CHUNK_DURATION,
    VAD_THRESHOLD, SILENCE_MAX_DURATION
)
from services import FunASRService, LLMService, EdgeTTSService
from utils import SimpleVAD, WebRtcVAD, EnhancedVAD, pcm_to_float, float_to_pcm


class ClientSession:
    """客户端会话管理"""

    def __init__(self, websocket: WebSocketServerProtocol):
        self.websocket = websocket
        self.session_id = id(self)
        self.is_speaking = False  # 客户端是否在播放 AI 回复
        self.audio_buffer: deque = deque()  # 接收的音频缓冲
        # 使用 Enhanced VAD: WebRTC + 频谱特征分析，更好地区分人声和噪音
        self.vad = EnhancedVAD(
            webrtc_mode=3,           # WebRTC VAD 模式 3（最严格）
            spectral_flatness_thresh=0.50,  # 谱平坦度阈值（降低以提高灵敏度）
            spectral_entropy_thresh=4.50,   # 谱熵阈值
            zcr_thresh=0.10,                # 过零率阈值（降低以提高灵敏度）
            noise_vote_thresh=1       # 1 个特征超过阈值就判定为噪音（更严格）
        )
        self.state = "idle"  # idle, listening, processing, speaking

    def reset(self):
        """重置会话状态"""
        self.audio_buffer.clear()
        self.vad.reset()
        self.state = "idle"


class WebSocketServer:
    """
    WebSocket 服务器
    管理所有客户端连接和 AI 处理流程
    """

    def __init__(self):
        self.clients: Set[ClientSession] = set()
        self.stt_service: Optional[FunASRService] = None
        self.llm_service: Optional[LLMService] = None
        self.tts_service: Optional[EdgeTTSService] = None
        self._services_initialized = False

    def init_services(self):
        """初始化 AI 服务"""
        logger.info("正在初始化 AI 服务...")

        try:
            self.stt_service = FunASRService()
            logger.info("✓ STT 服务 (FunASR) 初始化成功")
        except Exception as e:
            logger.warning(f"STT 服务初始化失败：{e}，将使用备用方案")
            from services import STTFallbackService
            self.stt_service = STTFallbackService()

        try:
            self.llm_service = LLMService()
            logger.info("✓ LLM 服务 (Claude) 初始化成功")
        except Exception as e:
            logger.warning(f"LLM 服务初始化失败：{e}")
            from services import LLMFallbackService
            self.llm_service = LLMFallbackService()

        try:
            self.tts_service = EdgeTTSService()
            logger.info("✓ TTS 服务 (Edge TTS) 初始化成功")
        except Exception as e:
            logger.error(f"TTS 服务初始化失败：{e}")
            from services import OpenAITTSService
            self.tts_service = OpenAITTSService()

        self._services_initialized = True
        logger.info("AI 服务初始化完成")

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        session = ClientSession(websocket)
        self.clients.add(session)
        logger.info(f"🔌 新客户端连接：{session.session_id} (来自 {websocket.remote_address})")
        print(f"=== 新客户端连接：{session.session_id} ===")  # 确保输出

        try:
            # 发送欢迎消息
            await self.send_to_client(session, {
                "type": "welcome",
                "message": "Connected to Nexa AI Server",
                "sample_rate": AUDIO_SAMPLE_RATE
            })

            async for message in websocket:
                await self.process_message(session, message)

        except ConnectionClosed:
            logger.info(f"客户端断开：{session.session_id}")
        except Exception as e:
            logger.error(f"处理客户端消息异常：{e}")
        finally:
            self.clients.discard(session)
            session.reset()

    async def process_message(self, session: ClientSession, message):
        """处理客户端消息"""
        try:
            # 解析消息
            if isinstance(message, bytes):
                # 二进制音频数据
                await self.process_audio(session, message)
            else:
                # JSON 控制消息
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "audio":
                    # Base64 编码的音频
                    audio_data = base64.b64decode(data.get("data", ""))
                    await self.process_audio(session, audio_data)

                elif msg_type == "control":
                    await self.process_control(session, data)

                elif msg_type == "ping":
                    await self.send_to_client(session, {"type": "pong"})

                elif msg_type == "test_tts":
                    # 测试 TTS 功能
                    text = data.get("text", "")
                    if text:
                        await self.test_tts(session, text)
                    else:
                        await self.send_to_client(session, {
                            "type": "error",
                            "message": "Missing text field"
                        })

        except json.JSONDecodeError:
            logger.warning("无效的 JSON 消息")
        except Exception as e:
            logger.error(f"处理消息失败：{e}")

    async def process_audio(self, session: ClientSession, audio_bytes: bytes):
        """处理音频数据"""
        # 调试：打印收到的音频数据
        print(f"=== 收到音频：{len(audio_bytes)} bytes, state={session.state} ===")

        if session.state == "speaking":
            # 正在播放 AI 回复，忽略输入（半双工）
            print("状态：speaking，忽略音频")
            return

        # WebRTC VAD 需要固定帧大小 (16kHz 时 320 样本=640 bytes 每 20ms)
        # 将大帧分割为小帧处理
        FRAME_SIZE = 640  # 16kHz * 20ms * 2 bytes = 320 样本

        is_any_voice = False
        last_sentence = None

        for i in range(0, len(audio_bytes), FRAME_SIZE):
            frame = audio_bytes[i:i+FRAME_SIZE]
            if len(frame) < FRAME_SIZE:
                # 不足一帧，留到下次处理
                break

            try:
                # 转换为 numpy 数组
                audio_float = pcm_to_float(frame)

                # VAD 检测
                is_voice, sentence = session.vad.add_audio(audio_float)

                if is_voice:
                    is_any_voice = True
                if sentence is not None:
                    last_sentence = sentence

            except Exception as e:
                # VAD 处理失败，跳过此帧
                print(f"VAD 帧处理失败：{e}")
                continue

        # 使用最后一帧的结果
        if last_sentence is not None:
            sentence = last_sentence
            is_voice = False  # 语句结束
        elif is_any_voice:
            is_voice = True

        # 调试输出
        energy = float(np.sqrt(np.mean(pcm_to_float(audio_bytes[:FRAME_SIZE]) ** 2))) if len(audio_bytes) >= FRAME_SIZE else 0
        print(f"音频能量：{energy:.4f}, VAD 结果：is_voice={is_voice}, sentence={sentence is not None if 'sentence' in locals() else 'N/A'}")

        if is_voice:
            if session.state != "listening":
                # 状态变化时才发送
                session.state = "listening"
                print(f"VAD: 开始录音")
                # 通知客户端正在录音
                await self.send_to_client(session, {
                    "type": "status",
                    "state": "listening"
                })
            session.audio_buffer.append(pcm_to_float(audio_bytes))

        elif sentence is not None:
            # 检测到完整语句，开始处理
            session.state = "processing"
            logger.info(f"检测到完整语句，缓冲时长：{len(session.audio_buffer)} 帧")

            # 异步处理 AI 响应
            asyncio.create_task(self.process_ai_response(session))

    async def process_ai_response(self, session: ClientSession):
        """处理 AI 响应流程：STT → LLM → TTS"""
        try:
            # 发送状态更新
            await self.send_to_client(session, {
                "type": "status",
                "state": "processing"
            })

            # 1. STT: 语音转文字
            logger.info("开始 STT 识别...")
            audio_data = np.concatenate(list(session.audio_buffer))
            stt_text = self.stt_service.recognize(audio_data)

            if not stt_text.strip():
                logger.warning("STT 识别结果为空")
                session.reset()
                return

            logger.info(f"用户说：{stt_text}")

            # 发送识别结果给客户端（可选显示）
            await self.send_to_client(session, {
                "type": "transcript",
                "text": stt_text
            })

            # 2. LLM: 获取回复
            logger.info("开始 LLM 请求...")
            full_response = ""

            async for chunk in self.llm_service.chat(stt_text, session.session_id):
                full_response += chunk

            if not full_response.strip():
                logger.warning("LLM 回复为空")
                session.reset()
                return

            logger.info(f"AI 回复：{full_response}")

            # 3. TTS: 文字转语音
            logger.info("开始 TTS 合成...")
            session.state = "speaking"

            await self.send_to_client(session, {
                "type": "status",
                "state": "speaking"
            })

            # 合成音频
            tts_audio = await self.tts_service.synthesize(full_response)

            if tts_audio:
                # 发送音频给客户端播放 - 分块发送以避免超过 WebSocket 消息限制
                logger.info(f"发送 TTS 音频：{len(tts_audio)} bytes")

                # 先发送音频开始消息
                await self.send_to_client(session, {
                    "type": "audio_start",
                    "format": "pcm16",
                    "sample_rate": AUDIO_SAMPLE_RATE,
                    "total_bytes": len(tts_audio)
                })

                # 分块发送音频数据（每块 8KB）
                CHUNK_SIZE = 8 * 1024
                for i in range(0, len(tts_audio), CHUNK_SIZE):
                    chunk = tts_audio[i:i+CHUNK_SIZE]
                    await session.websocket.send(chunk)
                    await asyncio.sleep(0.01)  # 小块延迟

                # 发送音频结束消息
                await self.send_to_client(session, {
                    "type": "audio_end"
                })

                # 等待播放完成（估算时间）
                duration = len(tts_audio) / (AUDIO_SAMPLE_RATE * 2)
                await asyncio.sleep(duration + 0.5)

            # 重置会话
            session.reset()
            logger.info("AI 响应流程完成")

        except Exception as e:
            logger.error(f"AI 处理失败：{e}")
            session.reset()

    async def process_control(self, session: ClientSession, data: dict):
        """处理控制消息"""
        action = data.get("action")

        if action == "start_listening":
            session.vad.reset()
            session.audio_buffer.clear()
            logger.info("开始新的语音会话")

        elif action == "stop_listening":
            session.vad.reset()
            session.audio_buffer.clear()
            logger.info("停止语音会话")

        elif action == "clear_history":
            self.llm_service.clear_history(session.session_id)
            logger.info("清空对话历史")

    async def test_tts(self, session: ClientSession, text: str):
        """测试 TTS 功能"""
        try:
            logger.info(f"TTS 测试请求：{text}")

            if not self.tts_service:
                await self.send_to_client(session, {
                    "type": "error",
                    "message": "TTS 服务未初始化"
                })
                return

            # 合成音频
            tts_audio = await self.tts_service.synthesize(text)

            if tts_audio:
                logger.info(f"发送 TTS 音频：{len(tts_audio)} bytes")
                await self.send_to_client(session, {
                    "type": "audio_playback",
                    "format": "pcm16",
                    "sample_rate": AUDIO_SAMPLE_RATE,
                    "data": base64.b64encode(tts_audio).decode()
                })
            else:
                await self.send_to_client(session, {
                    "type": "error",
                    "message": "TTS 合成失败"
                })

        except Exception as e:
            logger.error(f"TTS 测试失败：{e}")
            await self.send_to_client(session, {
                "type": "error",
                "message": str(e)
            })

    async def send_to_client(self, session: ClientSession, data: dict):
        """发送消息给客户端"""
        try:
            if data.get("type") == "audio_playback":
                # 二进制音频直接发送
                await session.websocket.send(json.dumps(data))
            else:
                # JSON 消息
                await session.websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"发送消息失败：{e}")

    async def start(self):
        """启动服务器"""
        if not self._services_initialized:
            self.init_services()

        logger.info(f"WebSocket 服务器启动：ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")

        # process_request 用于处理所有路径
        async def process_request(path, request_headers):
            print(f"=== 收到请求：{path} ===")
            return None  # 继续处理 WebSocket 请求

        async with serve(
            self.handle_client,
            WEBSOCKET_HOST,
            WEBSOCKET_PORT,
            ping_interval=30,
            ping_timeout=10,
            process_request=process_request,
            max_size=None  # 禁用消息大小限制
        ) as server:
            await server.serve_forever()


# 主程序入口
async def main():
    """主入口"""
    from loguru import logger

    # 配置日志
    logger.add(
        "logs/nexa_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )

    server = WebSocketServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
