"""
TTS Service - 文字转语音服务
使用 Edge TTS (免费、高质量)
"""
import io
import asyncio
from typing import AsyncGenerator, Optional
from loguru import logger


class EdgeTTSService:
    """
    Edge TTS 服务
    使用微软 Edge 浏览器的 TTS 引擎，免费且高质量
    """

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice
        self._init_check()

    def _init_check(self):
        """检查 Edge TTS 是否可用"""
        try:
            import edge_tts
            logger.info(f"Edge TTS 初始化成功，默认语音：{self.voice}")
        except ImportError:
            logger.error("Edge TTS 未安装，请运行：pip install edge-tts")
            raise

    async def synthesize(self, text: str) -> bytes:
        """
        合成完整音频

        Args:
            text: 要转换的文字

        Returns:
            PCM 音频数据 (16kHz, 16bit, 单声道)
        """
        try:
            import edge_tts
            import subprocess
            import tempfile
            import os

            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                # 使用 save 方法保存为 mp3
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(tmp_path)

                # 尝试使用 ffmpeg 转换为 PCM
                try:
                    result = subprocess.run(
                        [
                            'ffmpeg', '-y',
                            '-i', tmp_path,
                            '-f', 's16le', '-ar', '16000', '-ac', '1', 'pipe:1'
                        ],
                        capture_output=True,
                        timeout=60
                    )

                    if result.returncode == 0 and result.stdout:
                        audio_data = result.stdout
                        logger.info(f"TTS 合成完成 (ffmpeg)，大小：{len(audio_data)} bytes")
                        return audio_data
                except FileNotFoundError:
                    # ffmpeg 不可用，使用 edge_tts 直接生成音频
                    logger.info("ffmpeg 不可用，使用 edge_tts 流式输出")
                    pass

                # 备用方案：使用流式 API 获取 PCM
                audio_chunks = []
                communicate = edge_tts.Communicate(text, self.voice)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])

                if audio_chunks:
                    audio_data = b''.join(audio_chunks)
                    logger.info(f"TTS 合成完成 (流式)，大小：{len(audio_data)} bytes ({len(audio_data)/(16000*2):.2f}s)")
                    return audio_data
                else:
                    logger.error("TTS 合成失败：未收到音频数据")
                    return b""

            finally:
                # 清理临时文件
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            logger.error(f"TTS 合成失败：{e}")
            return b""

    async def synthesize_streaming(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        流式合成音频

        Args:
            text: 要转换的文字

        Yields:
            PCM 音频块
        """
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self.voice)

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        except Exception as e:
            logger.error(f"流式 TTS 合成失败：{e}")

    async def get_voices(self) -> list:
        """获取可用的中文语音列表"""
        try:
            import edge_tts

            voices = await edge_tts.list_voices()
            zh_voices = [v for v in voices if v["Locale"].startswith("zh-")]
            return zh_voices

        except Exception as e:
            logger.error(f"获取语音列表失败：{e}")
            return []


class OpenAITTSService:
    """
    备用 TTS 服务 - OpenAI TTS API
    更高质量但需要付费
    """

    def __init__(self, api_key: str = "", voice: str = "alloy"):
        self.api_key = api_key
        self.voice = voice
        self.client = None
        if api_key:
            self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"OpenAI TTS 客户端初始化成功，语音：{self.voice}")
        except Exception as e:
            logger.warning(f"OpenAI TTS 客户端初始化失败：{e}")

    async def synthesize(self, text: str) -> bytes:
        """合成完整音频"""
        if self.client is None:
            return b""

        try:
            response = self.client.audio.speech.create(
                model="tts-1",  # 或 tts-1-hd
                voice=self.voice,
                input=text,
                response_format="pcm"
            )

            audio_data = response.content
            logger.info(f"OpenAI TTS 合成完成，大小：{len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"OpenAI TTS 合成失败：{e}")
            return b""


class TTSServiceFactory:
    """TTS 服务工厂"""

    @staticmethod
    def create(service_type: str = "edge", **kwargs) -> Optional[EdgeTTSService | OpenAITTSService]:
        """
        创建 TTS 服务实例

        Args:
            service_type: "edge" 或 "openai"

        Returns:
            TTS 服务实例
        """
        if service_type == "edge":
            return EdgeTTSService(voice=kwargs.get("voice", "zh-CN-XiaoxiaoNeural"))
        elif service_type == "openai":
            return OpenAITTSService(
                api_key=kwargs.get("api_key", ""),
                voice=kwargs.get("voice", "alloy")
            )
        else:
            logger.error(f"未知的 TTS 服务类型：{service_type}")
            return None
