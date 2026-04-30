"""
TTS Service - 使用 Piper TTS (本地离线)
https://github.com/OHF-voice/piper

Piper 是一个快速、本地的神经语音合成系统，支持多种语言。
"""
import os
import asyncio
from typing import Optional
from loguru import logger
from config import AUDIO_SAMPLE_RATE


class PiperTTSService:
    """
    Piper TTS 服务
    本地离线运行，快速且隐私安全
    """

    def __init__(self, model_path: str = "", config_path: str = ""):
        self.model_path = model_path
        self.config_path = config_path
        self.voice = None
        self._init_check()

    def _init_check(self):
        """检查 piper 是否可用"""
        try:
            from piper import PiperVoice

            # 如果指定了模型路径，加载模型
            if self.model_path and os.path.exists(self.model_path):
                self.voice = PiperVoice.load(self.model_path)
                logger.info(f"Piper 模型加载成功：{self.model_path}")
            else:
                # 没有模型文件时，使用默认模型（如果有）
                logger.info("Piper Python 库可用，但未指定模型文件")
                logger.info("请运行 bash scripts/download_piper_models.sh 下载中文语音模型")
        except ImportError:
            logger.error("Piper 未安装，请运行：pip3 install piper-tts")
            raise

    async def synthesize(self, text: str, volume: float = 0.7) -> bytes:
        """
        合成完整音频

        Args:
            text: 要转换的文字
            volume: 音量 (0.0-1.0)

        Returns:
            PCM 音频数据 (16kHz, 16bit, 单声道)
        """
        if self.voice is None:
            # 没有模型时，返回空
            logger.error("Piper 模型未加载，无法合成")
            return b""

        try:
            import numpy as np

            # 使用 PiperVoice 合成
            audio_chunks = []
            for audio_chunk in self.voice.synthesize(text):
                audio_chunks.append(audio_chunk)

            if not audio_chunks:
                logger.error("Piper 合成失败：未收到音频数据")
                return b""

            # 拼接音频
            audio_data = b''.join(audio_chunks)

            # 调整音量（如果需要）
            if volume != 1.0 and audio_data:
                audio_float = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                audio_float = audio_float * volume
                audio_float = np.clip(audio_float, -32768, 32767)
                audio_data = audio_float.astype(np.int16).tobytes()

            logger.info(f"Piper TTS 合成完成，大小：{len(audio_data)} bytes ({len(audio_data)/(AUDIO_SAMPLE_RATE*2):.2f}s)")
            return audio_data

        except Exception as e:
            logger.error(f"Piper TTS 合成失败：{e}")
            return b""


    async def synthesize_streaming(self, text: str):
        """流式合成（暂未实现）"""
        raise NotImplementedError("流式合成暂未实现")
