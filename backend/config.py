"""
Nexa Backend Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# FunASR 配置
FUNASR_MODEL_DIR = os.getenv("FUNASR_MODEL_DIR", None)

# LLM API 配置 (阿里云 DashScope)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")

# 服务器配置
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8765"))

# 音频配置
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
AUDIO_CHUNK_DURATION = float(os.getenv("AUDIO_CHUNK_DURATION", "0.2"))

# VAD 配置
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.3"))  # 阈值 0.3，说话时能量约 0.5+
SPEECH_MIN_DURATION = float(os.getenv("SPEECH_MIN_DURATION", "0.5"))
SILENCE_MAX_DURATION = float(os.getenv("SILENCE_MAX_DURATION", "2.0"))  # 静音 2 秒判定语句结束

# Piper TTS 配置
PIPER_PATH = os.getenv("PIPER_PATH", "/usr/local/bin/piper")
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "")
PIPER_CONFIG_PATH = os.getenv("PIPER_CONFIG_PATH", "")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
