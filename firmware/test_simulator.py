"""
ESP32 固件模拟器 - 用于测试固件逻辑和后端通信
模拟 ESP32 的行为：WiFi 连接、WebSocket 通信、音频流传输
"""
import asyncio
import json
import base64
import random
import time
from typing import Optional

import websockets
from loguru import logger
import sys

logger.add(sys.stderr, level="INFO")

# ==================== 配置 ====================
WEBSOCKET_HOST = "127.0.0.1"
WEBSOCKET_PORT = 8765

AUDIO_SAMPLE_RATE = 16000
AUDIO_BITS_PER_SAMPLE = 16
BUFFER_SIZE = 1024


class ESP32Simulator:
    """
    ESP32-S3 模拟器
    模拟固件的主要功能：
    1. WiFi 连接状态
    2. WebSocket 客户端
    3. I2S 麦克风数据采集（模拟）
    4. I2S 音频播放（模拟）
    """

    def __init__(self, ssid: str = "CMCC-GNfE", password: str = "f2t2yw6e"):
        self.ssid = ssid
        self.password = password
        self.ws: Optional[websockets.ClientConnection] = None
        self.wifi_connected = False
        self.ws_connected = False
        self.is_recording = True
        self.is_playing = False

    async def connect_wifi(self) -> bool:
        """模拟 WiFi 连接"""
        logger.info(f"正在连接 WiFi: {self.ssid}")
        # 模拟连接延迟
        await asyncio.sleep(1)
        self.wifi_connected = True
        logger.info("✓ WiFi 连接成功")
        logger.info(f"IP 地址：192.168.1.{random.randint(100, 200)}")
        return True

    async def connect_websocket(self) -> bool:
        """连接 WebSocket 服务器"""
        uri = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"
        logger.info(f"正在连接 WebSocket: {uri}")

        try:
            self.ws = await websockets.connect(uri, ping_interval=30, ping_timeout=10)
            welcome = await asyncio.wait_for(self.ws.recv(), timeout=5)
            logger.info(f"✓ WebSocket 连接成功")
            logger.info(f"收到欢迎消息：{welcome}")
            self.ws_connected = True
            return True
        except Exception as e:
            logger.error(f"✗ WebSocket 连接失败：{e}")
            self.ws_connected = False
            return False

    async def generate_audio_frame(self, include_speech: bool = False) -> bytes:
        """
        模拟 I2S 麦克风采集的音频帧
        生成 16bit PCM 数据

        参数:
            include_speech: 是否包含模拟语音（正弦波，能量更高）
        """
        import numpy as np

        # 生成基础噪声（能量约 0.01）
        noise_float = np.random.uniform(-0.03, 0.03, BUFFER_SIZE).astype(np.float32)

        if include_speech:
            # 生成模拟语音信号（正弦波叠加）
            t = np.arange(BUFFER_SIZE) / AUDIO_SAMPLE_RATE
            # 基频 150Hz + 泛音，幅度 0.5（RMS 约 0.35，超过 VAD 阈值 0.3）
            speech_float = 0.5 * np.sin(2 * np.pi * 150 * t)
            speech_float += 0.2 * np.sin(2 * np.pi * 300 * t)
            speech_float += 0.1 * np.sin(2 * np.pi * 450 * t)

            # 混合语音和噪声
            audio_float = noise_float + speech_float
        else:
            audio_float = noise_float

        # 限制幅度在 -1 到 1 之间
        audio_float = np.clip(audio_float, -1.0, 1.0)

        # 转换为 16bit PCM
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    async def send_audio_stream(self, duration: float = 5):
        """
        模拟发送音频流到服务器
        模拟 ESP32 的 audioCaptureTask
        """
        logger.info("开始发送音频流...")

        start_time = time.time()
        frame_count = 0
        bytes_sent = 0
        speech_start = 1.0  # 1 秒后开始模拟语音
        speech_duration = 2.0  # 语音持续 2 秒

        while self.is_recording and not self.is_playing:
            if not self.ws_connected:
                logger.warning("WebSocket 断开，停止发送")
                break

            if time.time() - start_time > duration:
                logger.info("达到测试时长，停止发送")
                break

            # 生成音频帧（1-3 秒之间模拟语音）
            elapsed = time.time() - start_time
            include_speech = speech_start <= elapsed <= speech_start + speech_duration
            audio_frame = await self.generate_audio_frame(include_speech=include_speech)

            try:
                # 发送二进制音频数据
                await self.ws.send(audio_frame)
                frame_count += 1
                bytes_sent += len(audio_frame)

                if frame_count % 10 == 0:
                    status = "语音" if include_speech else "静音"
                    logger.debug(f"已发送 {frame_count} 帧 ({status})，{bytes_sent} 字节")

                # 模拟 20ms 一帧（50 FPS）
                await asyncio.sleep(0.02)

            except Exception as e:
                logger.error(f"发送音频失败：{e}")
                break

        logger.info(f"音频流发送完成：{frame_count} 帧，{bytes_sent} 字节")

    async def receive_messages(self, timeout: float = 10):
        """
        接收服务器消息
        模拟 ESP32 的 webSocketEvent 处理
        """
        logger.info("开始接收服务器消息...")

        try:
            while True:
                if not self.ws:
                    break

                message = await asyncio.wait_for(self.ws.recv(), timeout=timeout)

                if isinstance(message, bytes):
                    logger.info(f"收到二进制数据：{len(message)} 字节")
                else:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    logger.info(f"收到消息：type={msg_type}")

                    if msg_type == "audio_playback":
                        audio_data = data.get("data", "")
                        logger.info(f"✓ 收到 TTS 音频：{len(audio_data)} 字符")
                        self.is_playing = True
                        # 模拟播放
                        await asyncio.sleep(1)
                        self.is_playing = False
                        logger.info("音频播放完成")

                    elif msg_type == "transcript":
                        text = data.get("text", "")
                        logger.info(f"识别结果：{text}")

                    elif msg_type == "status":
                        state = data.get("state")
                        logger.info(f"服务器状态：{state}")

                    elif msg_type == "pong":
                        logger.debug("收到 PONG")

        except asyncio.TimeoutError:
            logger.info("消息接收超时")
        except Exception as e:
            logger.error(f"接收消息失败：{e}")

    async def test_full_flow(self, audio_duration: float = 5):
        """
        完整测试流程
        """
        logger.info("=" * 50)
        logger.info("ESP32 固件模拟测试")
        logger.info("=" * 50)

        # 1. WiFi 连接
        if not await self.connect_wifi():
            logger.error("WiFi 连接失败，终止测试")
            return

        # 2. WebSocket 连接
        if not await self.connect_websocket():
            logger.error("WebSocket 连接失败，终止测试")
            return

        # 3. 启动消息接收任务
        recv_task = asyncio.create_task(self.receive_messages(timeout=audio_duration + 5))

        # 4. 发送音频流
        await asyncio.sleep(0.5)  # 等待消息接收任务启动
        await self.send_audio_stream(duration=audio_duration)

        # 5. 等待可能的响应
        logger.info("等待服务器响应...")
        await asyncio.sleep(3)

        # 6. 清理
        recv_task.cancel()
        if self.ws:
            await self.ws.close()

        logger.info("=" * 50)
        logger.info("测试完成")
        logger.info("=" * 50)

    async def test_send_text_for_tts(self, text: str):
        """
        测试发送文本请求 TTS
        """
        logger.info("=" * 50)
        logger.info("ESP32 TTS 测试")
        logger.info("=" * 50)

        if not await self.connect_wifi():
            return
        if not await self.connect_websocket():
            return

        try:
            # 发送 TTS 请求
            logger.info(f"发送 TTS 请求：{text}")
            await self.ws.send(json.dumps({
                "type": "test_tts",
                "text": text
            }))

            # 等待响应
            while True:
                message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                if isinstance(message, bytes):
                    logger.info(f"收到音频：{len(message)} 字节")
                else:
                    data = json.loads(message)
                    logger.info(f"响应：{data}")
                    if data.get("type") == "audio_playback":
                        logger.info("✓ TTS 测试成功")
                        break
                    elif data.get("type") == "error":
                        logger.error(f"TTS 失败：{data.get('message')}")
                        break

        except asyncio.TimeoutError:
            logger.error("等待响应超时")
        except Exception as e:
            logger.error(f"测试失败：{e}")
        finally:
            if self.ws:
                await self.ws.close()


async def main():
    import sys

    if len(sys.argv) > 1:
        # TTS 测试模式
        text = " ".join(sys.argv[1:])
        sim = ESP32Simulator()
        await sim.test_send_text_for_tts(text)
    else:
        # 音频流测试模式
        sim = ESP32Simulator()
        await sim.test_full_flow(audio_duration=5)


if __name__ == "__main__":
    asyncio.run(main())
