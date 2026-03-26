# Nexa Backend

AI 对话产品的后端服务，基于 FunASR + Claude + Edge TTS。

## 功能特性

- 🎤 **STT 语音识别**: 本地部署 FunASR，支持流式识别
- 🤖 **LLM 对话**: Claude API，支持流式输出和对话历史
- 🔊 **TTS 语音合成**: Edge TTS 免费高质量
- 🔌 **WebSocket**: 实时双向音频流传输
- 🎯 **VAD 检测**: 语音活动检测，自动识别说话开始和结束

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

需要配置：
- `ANTHROPIC_API_KEY`: Claude API 密钥

### 3. 首次运行 - 下载模型

FunASR 模型首次运行会自动下载到本地：

```bash
python main.py
```

### 4. 启动服务

```bash
python main.py
```

服务默认在 `ws://localhost:8765` 启动。

## 项目结构

```
backend/
├── main.py                 # 主程序入口
├── config.py               # 配置管理
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量示例
├── services/
│   ├── __init__.py
│   ├── stt_service.py     # STT 服务 (FunASR)
│   ├── llm_service.py     # LLM 服务 (Claude)
│   ├── tts_service.py     # TTS 服务 (Edge TTS)
│   └── websocket_server.py # WebSocket 服务器
├── utils/
│   ├── __init__.py
│   ├── audio_utils.py     # 音频处理工具
│   └── vad.py             # VAD 检测
└── logs/                   # 日志目录
```

## WebSocket 协议

### 客户端 → 服务器

**音频数据（二进制）**:
- PCM16 格式，16kHz，单声道
- 直接发送二进制帧

**控制消息（JSON）**:
```json
{
  "type": "control",
  "action": "start_listening"  // 或 "stop_listening", "clear_history"
}
```

### 服务器 → 客户端

**欢迎消息**:
```json
{
  "type": "welcome",
  "message": "Connected to Nexa AI Server",
  "sample_rate": 16000
}
```

**状态更新**:
```json
{
  "type": "status",
  "state": "listening"  // 或 "processing", "speaking", "idle"
}
```

**语音识别结果**:
```json
{
  "type": "transcript",
  "text": "你好"
}
```

**音频播放**:
```json
{
  "type": "audio_playback",
  "format": "pcm16",
  "sample_rate": 16000,
  "data": "<base64 编码的 PCM 数据>"
}
```

## 配置说明

编辑 `config.py` 或 `.env` 文件：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `WEBSOCKET_PORT` | WebSocket 端口 | 8765 |
| `AUDIO_SAMPLE_RATE` | 音频采样率 | 16000 |
| `VAD_THRESHOLD` | VAD 能量阈值 | 0.05 |
| `SILENCE_MAX_DURATION` | 最大静音时长（秒） | 1.5 |
| `ANTHROPIC_API_KEY` | Claude API 密钥 | - |

## API 服务替代方案

### STT 备选
- FunASR（本地，默认）
- OpenAI Whisper API

### LLM 备选
- Claude API（默认）
- OpenAI GPT API

### TTS 备选
- Edge TTS（免费，默认）
- OpenAI TTS API

## 调试

查看日志：
```bash
tail -f logs/nexa_*.log
```

测试 WebSocket 连接：
```python
import asyncio
import websockets

async def test():
    async with websockets.connect("ws://localhost:8765") as ws:
        msg = await ws.recv()
        print(f"收到：{msg}")

asyncio.run(test())
```

## 性能优化建议

1. **FunASR 模型**: 首次加载较慢，建议常驻运行
2. **GPU 加速**: 如有 NVIDIA GPU，可设置 `device="cuda"` 加速 STT
3. **网络**: ESP32 建议连接 5GHz WiFi 降低延迟
4. **缓冲**: 调整 `SILENCE_MAX_DURATION` 平衡响应速度和完整性
