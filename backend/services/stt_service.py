"""
STT Service - 语音转文字服务
使用 FunASR 本地部署（阿里云达摩院）
支持流式识别
"""
import numpy as np
from typing import Optional, AsyncGenerator
from loguru import logger
from config import FUNASR_MODEL_DIR, AUDIO_SAMPLE_RATE


class FunASRService:
    """
    FunASR 语音识别服务
    支持离线部署和流式识别
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or FUNASR_MODEL_DIR
        self.model = None
        self._init_model()

    def _init_model(self):
        """初始化 FunASR 模型"""
        try:
            from funasr import AutoModel

            # 加载流式语音识别模型
            # paraformer-zh-streaming 支持流式识别
            logger.info("正在加载 FunASR 语音识别模型...")
            self.model = AutoModel(
                model="paraformer-zh-streaming",
                model_dir=self.model_dir,
                device="cpu",
                # 启用 VAD 和标点
                vad_model="fsmn-vad",
                punc_model="ct-punc"
            )
            logger.info("FunASR 模型加载成功")

        except ImportError as e:
            logger.error(f"FunASR 未安装，请运行：pip install funasr modelscope -U")
            logger.error(f"详细错误：{e}")
            raise

        except Exception as e:
            logger.error(f"FunASR 模型加载失败：{e}")
            # 尝试使用备用方案
            logger.warning("尝试加载离线版本...")
            try:
                from funasr import AutoModel
                self.model = AutoModel(
                    model="paraformer-zh",
                    model_dir=self.model_dir,
                    device="cpu"
                )
                logger.info("FunASR 离线模型加载成功（非流式）")
            except Exception as e2:
                logger.error(f"备用模型加载也失败：{e2}")
                raise

    async def recognize_stream(self, audio_chunks: list) -> AsyncGenerator[str, None]:
        """
        流式识别音频

        Args:
            audio_chunks: PCM 音频块列表

        Yields:
            识别结果文本（增量）
        """
        if self.model is None:
            raise RuntimeError("FunASR 模型未初始化")

        try:
            # 合并音频块
            audio_data = np.concatenate(audio_chunks)

            # FunASR 需要 int16 格式
            if audio_data.dtype == np.float32:
                audio_data = (audio_data * 32767).astype(np.int16)

            # 流式识别
            result = self.model.generate(
                input=audio_data.reshape(1, -1),
                input_sample_rate=AUDIO_SAMPLE_RATE,
                batch_size_s=60,  # 批处理时长
                chunk_size_s=0.5,  # 分块时长
            )

            # 提取识别结果
            if result and len(result) > 0:
                text = result[0].get("text", "")
                if text:
                    yield text

        except Exception as e:
            logger.error(f"流式识别失败：{e}")
            raise

    def recognize(self, audio_data: np.ndarray) -> str:
        """
        识别完整音频

        Args:
            audio_data: PCM 音频数据 (float32, -1~1)

        Returns:
            识别的文本
        """
        if self.model is None:
            raise RuntimeError("FunASR 模型未初始化")

        try:
            # 转换为 int16
            if audio_data.dtype == np.float32:
                audio_data = (audio_data * 32767).astype(np.int16)

            # 识别
            result = self.model.generate(
                input=audio_data.reshape(1, -1),
                input_sample_rate=AUDIO_SAMPLE_RATE,
            )

            # 提取结果
            if result and len(result) > 0:
                text = result[0].get("text", "")
                logger.info(f"STT 识别结果：{text}")
                return text

            return ""

        except Exception as e:
            logger.error(f"STT 识别失败：{e}")
            return ""

    def cleanup(self):
        """清理资源"""
        if self.model is not None:
            del self.model
            self.model = None


class STTFallbackService:
    """
    备用 STT 服务 - 使用 OpenAI Whisper API
    当 FunASR 不可用时使用
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.client = None
        if api_key:
            self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info("Whisper API 客户端初始化成功")
        except Exception as e:
            logger.warning(f"Whisper API 客户端初始化失败：{e}")

    def recognize(self, audio_data: np.ndarray) -> str:
        """使用 Whisper API 识别"""
        if self.client is None:
            return ""

        try:
            import io
            import wave

            # 转换为 WAV 格式
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(16000)
                wav_file.writeframes((audio_data * 32767).astype(np.int16).tobytes())

            wav_buffer.seek(0)

            # API 调用
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", wav_buffer, "audio/wav"),
                language="zh"
            )

            text = transcription.text
            logger.info(f"Whisper 识别结果：{text}")
            return text

        except Exception as e:
            logger.error(f"Whisper API 识别失败：{e}")
            return ""
