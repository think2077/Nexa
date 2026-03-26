"""
VAD (Voice Activity Detection) - 语音活动检测
使用简单的能量检测 + FunASR 内置 VAD
"""
import numpy as np
from collections import deque
from typing import Optional, Tuple
from loguru import logger

from config import VAD_THRESHOLD, SPEECH_MIN_DURATION, SILENCE_MAX_DURATION, AUDIO_SAMPLE_RATE


class SimpleVAD:
    """
    简单 VAD 检测器，基于音频能量
    用于预处理，减少发送到 STT 的无效音频
    """

    def __init__(
        self,
        threshold: float = VAD_THRESHOLD,
        speech_min_duration: float = SPEECH_MIN_DURATION,
        silence_max_duration: float = SILENCE_MAX_DURATION,
        sample_rate: int = AUDIO_SAMPLE_RATE
    ):
        self.threshold = threshold
        self.speech_min_samples = int(speech_min_duration * sample_rate)
        self.silence_max_samples = int(silence_max_duration * sample_rate)
        self.sample_rate = sample_rate

        self.audio_buffer = deque()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0

    def reset(self):
        """重置状态"""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0

    def calculate_energy(self, audio_data: np.ndarray) -> float:
        """计算音频能量 (RMS)"""
        return float(np.sqrt(np.mean(audio_data ** 2)))

    def add_audio(self, audio_data: np.ndarray) -> Tuple[bool, Optional[np.ndarray]]:
        """
        添加音频帧，返回 (是否正在说话，是否检测到完整语句)

        Returns:
            is_speaking: 是否检测到语音
            sentence: 如果检测到语句结束，返回完整的音频数据
        """
        energy = self.calculate_energy(audio_data)
        is_voice = energy > self.threshold

        if is_voice:
            if not self.is_speaking:
                # 刚开始说话
                self.is_speaking = True
                self.silence_counter = 0
                logger.debug(f"VAD: 检测到语音开始，energy={energy:.4f}")

            self.speech_counter += len(audio_data)
            self.audio_buffer.append(audio_data)
            return True, None

        else:
            if self.is_speaking:
                # 说话中遇到静音
                self.silence_counter += len(audio_data)

                if self.silence_counter >= self.silence_max_samples:
                    # 静音时间过长，判定语句结束
                    if self.speech_counter >= self.speech_min_samples:
                        sentence = np.concatenate(list(self.audio_buffer))
                        self.reset()
                        logger.debug(f"VAD: 检测到语句结束，duration={len(sentence)/self.sample_rate:.2f}s")
                        return False, sentence
                    else:
                        # 语音太短，忽略
                        logger.debug("VAD: 语音太短，忽略")
                        self.reset()
                        return False, None

                self.audio_buffer.append(audio_data)
                return True, None
            else:
                # 静音状态
                return False, None

    def get_buffer_duration(self) -> float:
        """获取当前缓冲的音频时长（秒）"""
        total_samples = sum(len(chunk) for chunk in self.audio_buffer)
        return total_samples / self.sample_rate


class FunASRVAD:
    """
    使用 FunASR 内置 VAD 进行更精确的检测
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir
        self.vad_model = None
        self._init_vad_model()

    def _init_vad_model(self):
        """初始化 VAD 模型"""
        try:
            from funasr import AutoModel
            self.vad_model = AutoModel(
                model="fsmn-vad",
                model_dir=self.model_dir,
                device="cpu"
            )
            logger.info("FunASR VAD 模型加载成功")
        except Exception as e:
            logger.warning(f"FunASR VAD 模型加载失败：{e}，将使用简单 VAD")
            self.vad_model = None

    def detect(self, audio_data: np.ndarray) -> list:
        """
        检测语音活动

        Returns:
            语音片段列表 [(start_ms, end_ms), ...]
        """
        if self.vad_model is None:
            return []

        try:
            # FunASR VAD 输入需要是单通道 float32, 16kHz
            result = self.vad_model.generate(
                input=audio_data.reshape(1, -1),
                input_sample_rate=16000
            )
            return result
        except Exception as e:
            logger.error(f"VAD 检测失败：{e}")
            return []
