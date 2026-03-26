# Nexa 环境搭建指南

详细的环境安装和配置步骤。

---

## 一、后端环境安装

### 1.1 系统要求

- Python 3.8+
- 内存 >= 4GB (FunASR 模型需要)
- 磁盘空间 >= 2GB (模型文件)
- 可选：NVIDIA GPU (加速 STT)

### 1.2 创建虚拟环境

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 1.3 安装依赖

```bash
pip install -r requirements.txt
```

如果安装失败，可以分步安装：

```bash
# 1. 基础依赖
pip install websockets numpy pydub scipy loguru python-dotenv

# 2. FunASR (可能需要先安装 torch)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install funasr modelscope

# 3. LLM 和 TTS
pip install anthropic edge-tts
```

### 1.4 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 必填：Claude API Key
ANTHROPIC_API_KEY=sk-ant-api-xxxxxxxxxxxxxxx

# 可选：FunASR 模型路径 (默认自动下载)
# FUNASR_MODEL_DIR=./models

# 服务器配置
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765

# 音频配置
AUDIO_SAMPLE_RATE=16000
VAD_THRESHOLD=0.05
SILENCE_MAX_DURATION=1.5
```

### 1.5 获取 Claude API Key

1. 访问 https://console.anthropic.com/
2. 注册/登录账号
3. 创建 API Key
4. 复制到 `.env` 文件

### 1.6 测试后端

```bash
python main.py
```

首次运行会：
- 自动下载 FunASR 模型 (约 1-2GB)
- 下载需要一定时间，请耐心等待

看到以下日志表示成功：
```
WebSocket 服务器启动：ws://0.0.0.0:8765
```

### 1.7 GPU 加速 (可选)

如果有 NVIDIA GPU，可以安装 CUDA 版本加速：

```bash
# 安装 CUDA 版本的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 修改 config.py 或启动参数
export FUNASR_DEVICE=cuda
```

---

## 二、ESP32 固件环境安装

### 2.1 方法一：PlatformIO (推荐)

#### 安装 VS Code

1. 下载并安装 [VS Code](https://code.visualstudio.com/)

#### 安装 PlatformIO 插件

1. 打开 VS Code
2. 进入扩展市场 (Ctrl+Shift+X)
3. 搜索 "PlatformIO IDE"
4. 安装并重启

#### 配置固件

编辑 `firmware/platformio.ini`:
- 确认 `board` 型号与实际开发板一致
- 确认 `board_flash_size` 与实际 Flash 大小一致

编辑 `firmware/src/main.cpp`:
```cpp
#define WIFI_SSID "你的 WiFi 名称"
#define WIFI_PASSWORD "你的 WiFi 密码"
#define WEBSOCKET_HOST "你的电脑 IP"  // 如 192.168.1.100
```

#### 编译和烧录

```bash
cd firmware
pio run -t upload
```

或使用 VS Code 的 PlatformIO 界面：
1. 点击左侧小象图标
2. 点击 `Build` (编译)
3. 点击 `Upload` (烧录)

#### 查看串口日志

```bash
pio device monitor
```

或使用 VS Code 点击 `Monitor`。

### 2.2 方法二：Arduino IDE

#### 安装 Arduino IDE

1. 下载并安装 [Arduino IDE](https://www.arduino.cc/en/software)

#### 添加 ESP32 开发板支持

1. 打开 Arduino IDE
2. 文件 -> 首选项
3. 在"附加开发板管理器 URL"添加：
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. 工具 -> 开发板 -> 开发板管理器
5. 搜索 "esp32"
6. 安装 "esp32 by Espressif"

#### 安装依赖库

工具 -> 管理库库，安装：
- `WebSockets` by Links2004
- `ArduinoJson` by Benoit Blanchon

#### 配置并上传

1. 打开 `firmware/src/main.cpp`
2. 修改 WiFi 和服务器配置
3. 工具 -> 开发板 -> 选择 "ESP32S3 Dev Module"
4. 点击上传按钮

---

## 三、硬件连接

### 3.1 INMP441 麦克风接线

| INMP441 引脚 | ESP32-S3 引脚 | 说明 |
|-------------|--------------|------|
| VDD | 3.3V | 电源 |
| GND | GND | 地 |
| WS | GPIO4 | 字时钟 |
| SCK | GPIO5 | 位时钟 |
| SD | GPIO6 | 数据输出 |
| L/R | GND | 左声道 (接地) |

### 3.2 MAX98357 功放接线

| MAX98357 引脚 | ESP32-S3 引脚 | 说明 |
|--------------|--------------|------|
| VDD | 5V | 电源 |
| GND | GND | 地 |
| BCLK | GPIO7 | 位时钟 |
| LRCLK | GPIO8 | 字时钟 |
| DIN | GPIO9 | 数据输入 |
| SD_MODE | GPIO10 | 静音控制 (可选) |
| GAIN | 悬空或接电阻 | 增益设置 |

### 3.3 喇叭连接

将喇叭连接到 MAX98357 的 OUT+ 和 OUT- 引脚。

### 3.4 引脚自定义

如果引脚冲突，可以修改：

**firmware/src/main.cpp**:
```cpp
// 麦克风引脚
#define I2S_SCK 5
#define I2S_WS 4
#define I2S_SD 6

// 功放引脚
#define I2S_BCLK 7
#define I2S_LRCLK 8
#define I2S_DATA 9
```

---

## 四、联调测试

### 4.1 启动后端

```bash
cd backend
python main.py
```

### 4.2 烧录固件

```bash
cd firmware
pio run -t upload
pio device monitor
```

### 4.3 观察日志

**后端日志**：
```
新客户端连接：123456
检测到完整语句，缓冲时长：10 帧
开始 STT 识别...
STT 识别结果：你好
开始 LLM 请求...
AI 回复：你好！有什么我可以帮助你的吗？
开始 TTS 合成...
发送 TTS 音频：xxxxx bytes
```

**ESP32 日志**：
```
=== Nexa ESP32-S3 Firmware ===
正在连接 WiFi...
WiFi 连接成功!
正在连接 WebSocket...
WebSocket 连接成功
音频捕获任务启动
音频播放任务启动
=== 初始化完成 ===
```

### 4.4 测试交互

1. 对着麦克风说话
2. 等待 LED 状态变化
3. 等待喇叭播放 AI 回复

---

## 五、常见问题

### Q1: FunASR 模型下载失败

**解决**：手动下载模型

```bash
# 使用 modelscope 下载
python -c "from modelscope import snapshot_download; snapshot_download('damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch')"
```

### Q2: WebSocket 连接被拒绝

**检查**：
- 防火墙是否开放 8765 端口
- 电脑 IP 是否正确
- ESP32 和电脑是否在同一局域网

### Q3: 音频质量差或有杂音

**尝试**：
- 检查接线是否牢固
- 降低 `AUDIO_SAMPLE_RATE` 到 8000
- 调整 `VAD_THRESHOLD`
- 检查电源是否稳定

### Q4: 响应延迟太高

**优化**：
- 使用 GPU 加速 FunASR
- 减小 `SILENCE_MAX_DURATION`
- 使用更快的网络

---

## 六、下一步

完成环境搭建后，可以：

1. 优化 VAD 参数，提高识别准确度
2. 添加配网功能 (AP 模式 + Web 页面)
3. 添加离线语音唤醒
4. 优化音频播放队列
