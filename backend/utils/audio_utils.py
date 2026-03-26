"""
音频处理工具函数
"""
import numpy as np
from typing import Tuple


def pcm_to_float(pcm_data: bytes, sample_width: int = 2) -> np.ndarray:
    """
    将 PCM 字节数据转换为浮点数组
    """
    if sample_width == 2:
        return np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 1:
        return np.frombuffer(pcm_data, dtype=np.int8).astype(np.float32) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")


def float_to_pcm(float_data: np.ndarray, sample_width: int = 2) -> bytes:
    """
    将浮点数组转换为 PCM 字节数据
    """
    if sample_width == 2:
        pcm_data = np.clip(float_data * 32767, -32768, 32767).astype(np.int16)
    elif sample_width == 1:
        pcm_data = np.clip(float_data * 127, -128, 127).astype(np.int8)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")
    return pcm_data.tobytes()


def calculate_audio_energy(audio_data: np.ndarray) -> float:
    """
    计算音频帧的能量（RMS）
    """
    return np.sqrt(np.mean(audio_data ** 2))


def resample_audio(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    重采样音频
    """
    try:
        import librosa
        return librosa.resample(data, orig_sr=orig_sr, target_sr=target_sr)
    except ImportError:
        # 简单降采样（仅适用于整数倍）
        if orig_sr % target_sr == 0:
            factor = orig_sr // target_sr
            return data[::factor]
        raise RuntimeError("Please install librosa for resampling")


def normalize_audio(audio_data: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """
    标准化音频音量
    """
    max_amp = np.max(np.abs(audio_data))
    if max_amp > 0:
        target_amp = 10 ** (target_db / 20)
        audio_data = audio_data * (target_amp / max_amp)
    return np.clip(audio_data, -1.0, 1.0)
