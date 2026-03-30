"""
VAD (Voice Activity Detection) - 语音活动检测
支持两种模式：
1. SimpleVAD - 基于能量的简单检测
2. WebRTC VAD - 基于深度学习的专业检测（推荐）
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


class WebRtcVAD:
    """
    WebRTC VAD 检测器
    使用深度学习模型，能准确区分人声和噪音

    优点:
    - 能区分人声和非人声噪音（咳嗽、敲门、键盘声等）
    - 4 个灵敏度等级（0-3，推荐 2）
    - 计算量小，适合实时处理

    注意：
    - 只支持 8000/16000/32000/48000 Hz 采样率
    - 只支持单声道
    - 需要 10/20/30ms 的音频帧
    """

    def __init__(
        self,
        mode: int = 2,  # 0-3，越大越严格
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        speech_min_duration: float = SPEECH_MIN_DURATION,
        silence_max_duration: float = SILENCE_MAX_DURATION
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.speech_min_frames = int(speech_min_duration * 1000 / frame_duration_ms)
        self.silence_max_frames = int(silence_max_duration * 1000 / frame_duration_ms)

        import webrtcvad
        self.vad = webrtcvad.Vad(mode)
        logger.info(f"WebRTC VAD 初始化，模式={mode} (0=最宽松，3=最严格)")

        self.audio_buffer = deque()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0
        self.frame_count = 0

    def reset(self):
        """重置状态"""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0
        self.frame_count = 0

    def is_voice_frame(self, audio_bytes: bytes) -> bool:
        """
        检测单帧音频是否包含语音

        Args:
            audio_bytes: PCM 音频数据 (16bit, 单声道)

        Returns:
            True=人声，False=噪音/静音
        """
        try:
            return self.vad.is_speech(audio_bytes, self.sample_rate)
        except Exception as e:
            logger.warning(f"WebRTC VAD 检测失败：{e}")
            return False

    def add_audio(self, audio_data: np.ndarray) -> Tuple[bool, Optional[np.ndarray]]:
        """
        添加音频帧，返回 (是否正在说话，是否检测到完整语句)

        Args:
            audio_data: float32 音频数据 (-1~1)

        Returns:
            is_speaking: 是否检测到语音
            sentence: 如果检测到语句结束，返回完整的音频数据
        """
        # 转换为 16bit PCM
        audio_int16 = (audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()

        # WebRTC VAD 检测
        is_voice = self.is_voice_frame(audio_bytes)
        self.frame_count += 1

        if is_voice:
            if not self.is_speaking:
                # 刚开始说话
                self.is_speaking = True
                self.silence_counter = 0
                logger.info(f"🎤 WebRTC VAD: 检测到语音开始 (帧{self.frame_count})")

            self.speech_counter += 1
            self.audio_buffer.append(audio_data)
            return True, None

        else:
            if self.is_speaking:
                # 说话中遇到静音/噪音
                self.silence_counter += 1

                if self.silence_counter >= self.silence_max_frames:
                    # 静音时间过长，判定语句结束
                    if self.speech_counter >= self.speech_min_frames:
                        sentence = np.concatenate(list(self.audio_buffer))
                        duration = len(sentence) / self.sample_rate
                        logger.info(f"✅ WebRTC VAD: 检测到语句结束，时长={duration:.2f}s")
                        self.reset()
                        return False, sentence
                    else:
                        # 语音太短，忽略
                        logger.debug(f"WebRTC VAD: 语音太短 ({self.speech_counter}帧)，忽略")
                        self.reset()
                        return False, None

                self.audio_buffer.append(audio_data)
                return True, None
            else:
                # 静音/噪音状态
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
