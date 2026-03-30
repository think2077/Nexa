"""
VAD (Voice Activity Detection) - 语音活动检测
支持三种模式：
1. SimpleVAD - 基于能量的简单检测
2. WebRTC VAD - 基于深度学习的专业检测
3. EnhancedVAD - WebRTC + 频谱特征分析（最严格，推荐用于噪音环境）

EnhancedVAD 在 WebRTC VAD 基础上增加：
- 谱平坦度 (Spectral Flatness): 高→噪音，低→人声
- 谱熵 (Spectral Entropy): 高→随机噪音，低→有结构（人声）
- 过零率 (ZCR): 很高→噪音可能性大
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


class EnhancedVAD:
    """
    增强版 VAD 检测器：WebRTC VAD + 频谱特征分析

    在 WebRTC VAD 检测为语音的基础上，进一步分析频谱特征：
    - 谱平坦度 (Spectral Flatness): 衡量频谱的均匀程度
      - 高 (>0.5): 白噪音等均匀频谱
      - 低 (<0.3): 人声等有结构的频谱
    - 谱熵 (Spectral Entropy): 衡量频谱的混乱程度
      - 高 (>4.0): 随机噪音
      - 低 (<3.5): 有结构的语音
    - 过零率 (ZCR): 衡量信号变化频率
      - 很高 (>0.5): 高频噪音
      - 中等 (0.1-0.3): 人声

    组合逻辑：
    1. WebRTC VAD 先检测是否为人声
    2. 如果是，再检查频谱特征
    3. 如果特征符合"非语音"，则过滤掉
    """

    def __init__(
        self,
        webrtc_mode: int = 2,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        spectral_flatness_thresh: float = 0.70,  # 谱平坦度阈值
        spectral_entropy_thresh: float = 4.95,   # 谱熵阈值
        zcr_thresh: float = 0.20,                # 过零率阈值（最有效区分特征）
        speech_min_duration: float = SPEECH_MIN_DURATION,
        silence_max_duration: float = SILENCE_MAX_DURATION,
        noise_vote_thresh: int = 2               # 需要几个特征判定为噪音（推荐 2）
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.speech_min_frames = int(speech_min_duration * 1000 / frame_duration_ms)
        self.silence_max_frames = int(silence_max_duration * 1000 / frame_duration_ms)

        # 频谱特征阈值
        self.spectral_flatness_thresh = spectral_flatness_thresh
        self.spectral_entropy_thresh = spectral_entropy_thresh
        self.zcr_thresh = zcr_thresh
        self.noise_vote_thresh = noise_vote_thresh

        import webrtcvad
        self.vad = webrtcvad.Vad(webrtc_mode)
        logger.info(f"Enhanced VAD 初始化：WebRTC mode={webrtc_mode} + 频谱特征分析")
        logger.info(f"  谱平坦度阈值：{spectral_flatness_thresh} (超过则判定为噪音)")
        logger.info(f"  谱熵阈值：{spectral_entropy_thresh} (超过则判定为噪音)")
        logger.info(f"  过零率阈值：{zcr_thresh} (超过则判定为噪音)")
        logger.info(f"  投票阈值：{noise_vote_thresh}/3 特征超过阈值 → 判定为噪音")

        self.audio_buffer = deque()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0
        self.frame_count = 0

        # 统计信息
        self.total_frames = 0
        self.filtered_noise_frames = 0

    def reset(self):
        """重置状态"""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_counter = 0
        self.frame_count = 0

    def calculate_spectral_flatness(self, audio_data: np.ndarray) -> float:
        """
        计算谱平坦度 (Spectral Flatness / Wiener Entropy)

        公式：几何平均 / 算术平均
        - 接近 1: 白噪音（均匀频谱）
        - 接近 0: 纯音/语音（有结构的频谱）
        """
        # FFT 变换
        spectrum = np.fft.rfft(audio_data)
        magnitude = np.abs(spectrum) + 1e-10  # 避免 log(0)

        # 几何平均 = exp(mean(log(x)))
        log_magnitude = np.log(magnitude)
        geometric_mean = np.exp(np.mean(log_magnitude))

        # 算术平均
        arithmetic_mean = np.mean(magnitude)

        # 谱平坦度
        flatness = geometric_mean / arithmetic_mean
        return float(flatness)

    def calculate_spectral_entropy(self, audio_data: np.ndarray) -> float:
        """
        计算谱熵 (Spectral Entropy)

        熵越高表示频谱越混乱（随机噪音）
        熵越低表示频谱越有结构（人声）
        """
        # FFT 变换
        spectrum = np.fft.rfft(audio_data)
        magnitude = np.abs(spectrum) + 1e-10

        # 归一化为概率分布
        probability = magnitude / np.sum(magnitude)

        # 计算熵：-sum(p * log(p))
        entropy = -np.sum(probability * np.log(probability + 1e-10))
        return float(entropy)

    def calculate_zcr(self, audio_data: np.ndarray) -> float:
        """
        计算过零率 (Zero Crossing Rate)

        过零率很高表示信号变化频繁，可能是高频噪音
        """
        # 计算符号变化次数
        sign_changes = np.sum(np.diff(np.sign(audio_data)) != 0)
        # 归一化
        zcr = sign_changes / (2 * len(audio_data))
        return float(zcr)

    def analyze_spectrum(self, audio_data: np.ndarray) -> dict:
        """分析音频的频谱特征"""
        flatness = self.calculate_spectral_flatness(audio_data)
        entropy = self.calculate_spectral_entropy(audio_data)
        zcr = self.calculate_zcr(audio_data)

        return {
            "flatness": flatness,
            "entropy": entropy,
            "zcr": zcr
        }

    def is_noise_by_spectrum(self, audio_data: np.ndarray) -> bool:
        """
        通过频谱特征判断是否为噪音

        Returns:
            True=噪音（应过滤）, False=可能是人声
        """
        features = self.analyze_spectrum(audio_data)

        # 三个特征中任意两个超过阈值，则判定为噪音
        noise_votes = 0

        if features["flatness"] > self.spectral_flatness_thresh:
            noise_votes += 1
            logger.debug(f"  [谱平坦度={features['flatness']:.3f} > {self.spectral_flatness_thresh}] → 噪音特征")

        if features["entropy"] > self.spectral_entropy_thresh:
            noise_votes += 1
            logger.debug(f"  [谱熵={features['entropy']:.3f} > {self.spectral_entropy_thresh}] → 噪音特征")

        if features["zcr"] > self.zcr_thresh:
            noise_votes += 1
            logger.debug(f"  [过零率={features['zcr']:.3f} > {self.zcr_thresh}] → 噪音特征")

        # 使用动态阈值判定（默认 1 票就过滤，更严格）
        is_noise = noise_votes >= self.noise_vote_thresh

        if is_noise:
            logger.debug(f"  频谱特征：{noise_votes}/3 投票 → 判定为噪音，过滤")
        else:
            logger.debug(f"  频谱特征：{noise_votes}/3 投票 → 可能是人声，保留")

        return is_noise

    def is_voice_frame(self, audio_bytes: bytes) -> bool:
        """
        检测单帧音频是否包含语音

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

        self.total_frames += 1
        self.frame_count += 1

        # Step 1: WebRTC VAD 检测
        is_voice_by_webrtc = self.is_voice_frame(audio_bytes)

        if not is_voice_by_webrtc:
            # WebRTC 判定为静音/噪音，直接跳过
            if self.is_speaking:
                self.silence_counter += 1
                if self.silence_counter >= self.silence_max_frames:
                    if self.speech_counter >= self.speech_min_frames:
                        sentence = np.concatenate(list(self.audio_buffer))
                        duration = len(sentence) / self.sample_rate
                        logger.info(f"✅ Enhanced VAD: 检测到语句结束，时长={duration:.2f}s")
                        self.reset()
                        return False, sentence
                    else:
                        logger.debug(f"Enhanced VAD: 语音太短 ({self.speech_counter}帧)，忽略")
                        self.reset()
                        return False, None
                self.audio_buffer.append(audio_data)
                return True, None
            else:
                return False, None

        # Step 2: WebRTC 判定为语音，进一步检查频谱特征
        is_noise_by_spectrum = self.is_noise_by_spectrum(audio_data)

        if is_noise_by_spectrum:
            # 频谱特征显示是噪音，过滤掉
            self.filtered_noise_frames += 1
            logger.info(f"🚫 Enhanced VAD: 检测到噪音帧 (WebRTC=语音，但频谱分析=噪音)")

            if self.is_speaking:
                # 如果之前认为在说话，现在遇到"噪音"，也计入静音
                self.silence_counter += 1
            return False, None

        # Step 3: 通过所有检测，确认是人声
        if not self.is_speaking:
            self.is_speaking = True
            self.silence_counter = 0
            logger.info(f"🎤 Enhanced VAD: 检测到语音开始 (帧{self.frame_count})")

        self.speech_counter += 1
        self.audio_buffer.append(audio_data)
        return True, None

    def get_buffer_duration(self) -> float:
        """获取当前缓冲的音频时长（秒）"""
        total_samples = sum(len(chunk) for chunk in self.audio_buffer)
        return total_samples / self.sample_rate

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_frames": self.total_frames,
            "filtered_noise_frames": self.filtered_noise_frames,
            "filter_rate": self.filtered_noise_frames / max(1, self.total_frames)
        }
