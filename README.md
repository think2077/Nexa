# Nexa - AI 语音对话 Demo

基于 ESP32-S3 的本地 AI 语音对话产品 Demo，支持实时语音交互。

## 📋 项目简介

Nexa 是一个完整的 AI 语音对话系统，包含：
- **ESP32-S3 硬件端**: 音频采集 + 播放 + WiFi 传输
- **Python 后端**: STT + LLM + TTS 完整 AI 链路
- **本地部署 FunASR**: 阿里云达摩院开源语音识别，支持流式识别
- **本地 Piper TTS**: 快速离线语音合成，无需网络连接

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        整体架构图                                │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │   ESP32-S3       │
  │   (带 PSRAM)     │
  │                  │
  │  ┌────────────┐  │          固件功能：
  │  │ INMP441    │  │  ┌──────────────────────────┐
  │  │ 麦克风     │──┼──► • I2S 音频采集 (16kHz)   │
  │  └────────────┘  │  │ • VAD 语音活动检测        │
  │  ┌────────────┐  │  │ • WebSocket 客户端        │
  │  │ MAX98357   │  │  │ • WiFi 连接管理           │
  │  │ I2S 功放   │◄─┼──┤ • 配网 Web 服务器          │
  │  └────────────┘  │  └──────────────────────────┘
  └────────┬─────────┘
           │ WebSocket (WiFi)
           │ 发送：PCM 音频流
           │ 接收：AI 回复音频
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │              Python 后台服务 (backend/)                  │
  │                                                         │
  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
  │  │ WebSocket   │──►│ STT 服务    │──►│ LLM 服务    │   │
  │  │ 服务器      │   │ FunASR 本地 │   │ Claude API  │   │
  │  └─────────────┘   └─────────────┘   └─────────────┘   │
  │                            ▲                  │         │
  │                            │                  ▼         │
  │  ┌─────────────┐   ┌─────────────────────────────┐     │
  │  │ 音频播放    │◄──│ TTS 服务                     │     │
  │  │ (ESP32)     │   │ Piper (本地离线，首选)       │     │
  │  └─────────────┘   │ Edge TTS (备用)              │     │
  │  └─────────────┘   └─────────────────────────────┘     │
  └─────────────────────────────────────────────────────────┘
```

---

## 🔧 硬件清单

| 组件 | 型号 | 说明 | 预估价格 |
|------|------|------|---------|
| 开发板 | ESP32-S3 | 需支持 PSRAM (>=2MB) | ¥35-50 |
| 麦克风 | INMP441 | I2S 数字麦克风 | ¥5-8 |
| 功放 | MAX98357 | I2S 音频功放 | ¥8-12 |
| 喇叭 | 4Ω 3W | 配合 MAX98357 使用 | ¥5-10 |
| 杜邦线 | 母对母 | 连接各模块 | ¥2-5 |

**总计**: 约 ¥55-85

---

## 🚀 快速开始

### 1. 配置后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY
```

### 1.5 安装 Piper TTS（可选，推荐）

Piper 是本地离线 TTS，响应更快且无需网络请求。

```bash
# 运行自动安装脚本
bash scripts/install_piper.sh

# 下载中文语音模型
bash scripts/download_piper_models.sh
```

然后在 `.env` 中配置：
```bash
# Piper TTS 配置
PIPER_MODEL_PATH=/Users/yourname/piper/models/zh-cnxiaoxiao-high.onnx
```

详细说明请参考 [docs/PIPER_TTS_SETUP.md](docs/PIPER_TTS_SETUP.md)

### 2. 启动后端服务

```bash
# Linux/Mac
./start.sh

# Windows
start.bat

# 或直接运行
python main.py
```

首次运行会自动下载 FunASR 模型 (约 1-2GB)。

### 3. 配置固件

编辑 `firmware/src/main.cpp`:

```cpp
#define WIFI_SSID "你的 WiFi 名称"
#define WIFI_PASSWORD "你的 WiFi 密码"
#define WEBSOCKET_HOST "你的电脑 IP"  // 如 192.168.1.100
```

### 4. 烧录固件

**方法一：PlatformIO (推荐)**
```bash
cd firmware
pio run -t upload
pio device monitor  # 查看串口日志
```

**方法二：Arduino IDE**
1. 安装 ESP32 开发板支持
2. 安装库：WebSockets, ArduinoJson
3. 打开 `src/main.cpp` 上传

### 5. 硬件接线

#### INMP441 麦克风接线

| INMP441 引脚 | ESP32-S3 GPIO | 说明 |
|-------------|--------------|------|
| VDD | 3.3V | 电源正极 |
| GND | GND | 电源负极 |
| SCK | GPIO 5 | 时钟信号 |
| WS/SEL | GPIO 4 | 字选择信号 |
| SD | GPIO 6 | 数据输出 |
| L/R | GND | 声道选择（接 GND=左声道，接 3.3V=右声道）|

**⚠️ 重要提示：**
- L/R 引脚**必须**连接 GND 或 3.3V，不能悬空，否则无数据输出
- SD 是数据**输出**引脚，连接到 ESP32 的数据**输入**引脚
- 如果采样值全为 0，检查 L/R 引脚是否已连接

#### MAX98357 功放接线

| MAX98357 引脚 | ESP32-S3 GPIO | 说明 |
|--------------|--------------|------|
| VDD | 5V 或 3.3V | 电源正极 |
| GND | GND | 电源负极 |
| BCLK | GPIO 7 | 位时钟 |
| LRCLK | GPIO 8 | 字时钟 |
| DIN | GPIO 9 | 数据输入 |
| SD_MUTE | 可选 | 静音控制（可悬空） |

参考 [docs/hardware_wiring.md](docs/hardware_wiring.md)

## 📁 项目结构

```
Nexa/
├── README.md                 # 本文件
├── .gitignore               # Git 忽略配置
│
├── backend/                 # Python 后端
│   ├── main.py              # 主入口
│   ├── config.py            # 配置管理
│   ├── requirements.txt     # Python 依赖
│   ├── .env.example        # 环境变量模板
│   ├── start.sh / .bat     # 快速启动脚本
│   ├── test_client.py      # 测试客户端
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stt_service.py      # STT (FunASR 本地)
│   │   ├── llm_service.py      # LLM (Claude API)
│   │   ├── tts_service.py      # TTS (Edge TTS)
│   │   └── websocket_server.py # WebSocket 服务器
│   └── utils/
│       ├── __init__.py
│       ├── audio_utils.py      # 音频处理
│       └── vad.py              # VAD 检测
│
├── firmware/                # ESP32 固件
│   ├── platformio.ini       # PlatformIO 配置
│   └── src/
│       ├── main.cpp         # 主程序
│       ├── audio/           # 音频模块 (TODO)
│       ├── wifi/            # WiFi 模块 (TODO)
│       └── websocket/       # WebSocket 模块 (TODO)
│
└── docs/                    # 文档
    ├── setup_guide.md       # 详细安装指南
    └── hardware_wiring.md   # 硬件接线图
```

---

## 🔄 工作流程

```
用户说话
   │
   ▼
┌─────────────────┐
│ ESP32 音频采集   │ I2S 读取 INMP441, 16kHz 16bit
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ VAD 检测        │ 本地能量检测，识别说话开始/结束
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocket 发送   │ PCM 二进制流，200ms/帧
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FunASR STT      │ 本地语音识别 → 文字
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Qwen LLM       │ API 请求 → 文字回复
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Edge TTS        │ 文字转语音 → PCM 音频
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocket 返回   │ Base64 编码音频
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ESP32 播放      │ I2S 输出到 MAX98357
└─────────────────┘
         │
         ▼
用户听到 AI 回复
```

---

## ⚙️ 配置说明

### 后端配置 (.env)

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope 密钥 (必填) | - |
| `DASHSCOPE_BASE_URL` | API 基础地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `LLM_MODEL` | 模型名称 | qwen-plus |
| `WEBSOCKET_HOST` | WebSocket 监听地址 | 0.0.0.0 |
| `WEBSOCKET_PORT` | WebSocket 端口 | 8765 |
| `AUDIO_SAMPLE_RATE` | 音频采样率 | 16000 |
| `VAD_THRESHOLD` | VAD 能量阈值 | 0.05 |
| `SILENCE_MAX_DURATION` | 最大静音时长 (秒) | 1.5 |

### 固件配置 (src/main.cpp)

| 宏定义 | 说明 | 默认值 |
|--------|------|--------|
| `WIFI_SSID` | WiFi 名称 | - |
| `WIFI_PASSWORD` | WiFi 密码 | - |
| `WEBSOCKET_HOST` | 后端服务器 IP | 192.168.1.100 |
| `WEBSOCKET_PORT` | 后端服务器端口 | 8765 |
| `AUDIO_SAMPLE_RATE` | 音频采样率 | 16000 |

### I2S 引脚定义

```cpp
// 麦克风 (INMP441)
#define I2S_SCK 5      // 位时钟
#define I2S_WS 4       // 字时钟
#define I2S_SD 6       // 数据输出

// 功放 (MAX98357)
#define I2S_BCLK 7     // 位时钟
#define I2S_LRCLK 8    // 字时钟
#define I2S_DATA 9     // 数据输入
```

---

## 📊 性能与延迟

### 延迟分解

| 环节 | 预估延迟 | 说明 |
|------|---------|------|
| 音频采集 + 传输 | 100-300ms | WiFi 网络质量影响 |
| VAD 检测 | 50-100ms | 本地计算 |
| STT 识别 | 500-1500ms | FunASR 流式识别 |
| LLM 响应 | 1000-2000ms | API 响应时间 |
| TTS 合成 | 500-1000ms | Edge TTS |
| **总计** | **2.5-5 秒** | 从说完到播放 |

### 优化建议

1. **GPU 加速**: 使用 CUDA 加速 FunASR，STT 延迟可降至 200-500ms
2. **网络优化**: ESP32 连接 5GHz WiFi，降低传输延迟
3. **参数调整**: 减小 `SILENCE_MAX_DURATION` 可更快响应
4. **流式处理**: LLM 和 TTS 已支持流式，首句响应更快

---

## 🔌 WebSocket 协议

### 客户端 → 服务器

**音频数据 (二进制)**:
```
PCM16 格式，16kHz，单声道
直接发送二进制帧，每帧约 200ms
```

**控制消息 (JSON)**:
```json
{
  "type": "control",
  "action": "start_listening"
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
  "state": "listening"   // listening, processing, speaking, idle
}
```

**识别结果**:
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

---

## 🛠️ 故障排查

### 后端无法启动

| 问题 | 解决 |
|------|------|
| Python 版本错误 | 确保 Python >= 3.8 |
| 依赖安装失败 | `pip install -r requirements.txt --upgrade` |
| 端口被占用 | `lsof -i :8765` 或换端口 |
| 模型下载失败 | 检查网络，或手动下载 FunASR 模型 |

### ESP32 无法连接

| 问题 | 解决 |
|------|------|
| WiFi 连不上 | 检查 SSID/密码，确保 2.4GHz 网络 |
| WebSocket 被拒绝 | 检查 IP 是否正确，防火墙是否开放 |
| 串口无输出 | 检查波特率 (115200) 和 USB 驱动 |

### 音频问题

| 问题 | 解决 |
|------|------|
| 有杂音 | 检查 I2S 接线，确保共地 |
| 声音小 | 调整 TTS 语音或功放增益 |
| 识别不准 | 调整 VAD 阈值，改善麦克风位置 |

---

## 📝 待办事项

### 固件优化
- [ ] I2S 分时复用 (麦克风/功放切换)
- [ ] 完整的播放队列实现
- [ ] 配网 AP 模式 + Captive Portal
- [ ] 蓝牙配网替代方案
- [ ] 离线关键词唤醒 (如「你好 AI」)
- [ ] 回声消除 (AEC)
- [ ] 状态指示 OLED 显示

### 后端优化
- [ ] 多会话管理
- [ ] 音频缓存优化
- [ ] 支持其他 LLM (Ollama 本地)
- [ ] 支持其他 STT (Whisper API)
- [ ] Web 管理界面
- [ ] 对话记录持久化

### 功能增强
- [ ] 多语言支持
- [ ] 语音情感识别
- [ ] 背景音乐播放
- [ ] 定时任务/闹钟
- [ ] 智能家居控制对接

---

## 📄 License

MIT License

---

## 🙏 致谢

- [FunASR](https://github.com/alibaba-damo-academy/FunASR) - 阿里达摩院开源 STT
- [Edge TTS](https://github.com/rany2/edge-tts) - 微软免费 TTS
- [阿里云通义千问](https://help.aliyun.com/zh/dashscope/) - Qwen LLM
- [ESP32](https://www.espressif.com/) - 优秀的开源硬件平台
