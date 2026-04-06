# Nexa ESP32-S3 固件

ESP32-S3 语音交互设备固件，支持 WebSocket 音频流传输。

## 硬件连接

### 麦克风 (INMP441)

| INMP441 | ESP32-S3 |
|---------|----------|
| VDD | 3.3V |
| GND | GND |
| BCLK | GPIO5 |
| WS/LR | GPIO4 |
| SD | GPIO6 |
| L/R | GND (左声道) 或 VDD (右声道) |

**注意**: L/R 引脚决定输出声道：
- L/R 接地 = 左声道
- L/R 接 VDD = 右声道

固件默认配置为左声道 (`I2S_CHANNEL_FMT_ONLY_LEFT`)。

### 功放 (MAX98357)

| MAX98357 | ESP32-S3 |
|----------|----------|
| VIN | 5V (或 3.3V) |
| GND | GND |
| BCLK | GPIO7 |
| LRCLK | GPIO8 |
| DIN | GPIO9 |
| L+ | 扬声器+ |
| L- | 扬声器- |
| SD | VIN (常开) 或悬空 |

**注意**:
- SD (Shutdown) 引脚需要拉高才能启用放大器
- 如果模块上没有 SD 引脚，说明已内部上拉
- 扬声器推荐：4Ω 3W 或 8Ω 3W

### LED 状态指示

| 状态 | LED 行为 |
|------|----------|
| WiFi 未连接 | 慢闪 (1Hz) |
| WebSocket 未连接 | 快闪 (5Hz) |
| 已连接 | 常亮 |

## 编译和上传

### 环境要求

- PlatformIO Core
- ESP32 平台支持包

### 编译

```bash
cd firmware
pio run
```

### 上传

```bash
pio run -t upload
```

### 串口监视

```bash
pio device monitor
```

## 配置

### WiFi 配置

编辑 `src/main.cpp`:

```cpp
#define WIFI_SSID "your_ssid"
#define WIFI_PASSWORD "your_password"
#define WEBSOCKET_HOST "192.168.1.x"  // 后端服务器 IP
#define WEBSOCKET_PORT 8765
```

### 音频配置

```cpp
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT
#define AUDIO_CHANNEL I2S_CHANNEL_MODE_ONLY_RIGHT
```

## 故障排除

### 麦克风无声

1. 检查 I2S 接线是否正确
2. 确认 L/R 引脚配置与固件一致
3. 查看串口日志中的 I2S 采样值

### 功放无声

1. 检查 SD 引脚是否拉高
2. 确认扬声器连接正常
3. 查看串口日志中的播放进度

### WebSocket 连接失败

1. 确认 WiFi 连接正常
2. 检查后端服务器 IP 是否正确
3. 确认防火墙允许 8765 端口
