/**
 * Nexa ESP32-S3 Firmware
 *
 * 功能：
 * 1. I2S 麦克风采集 (INMP441)
 * 2. I2S 音频播放 (MAX98357)
 * 3. WebSocket 音频流传输
 * 4. WiFi 配置和管理
 * 5. 配网 Web 服务器
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include <SPIFFS.h>

// ==================== 配置 ====================

// WiFi 配置
#define WIFI_SSID "CMCC-GNfE"
#define WIFI_PASSWORD "f2t2yw6e"
// #define WIFI_SSID "think"
// #define WIFI_PASSWORD "12345678"
// 服务器配置
#define WEBSOCKET_HOST "192.168.1.18"  // Python 服务器 IP
#define WEBSOCKET_PORT 8765
#define WEBSOCKET_URL "/ws"

// 音频配置
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT
#define AUDIO_CHANNEL I2S_CHANNEL_MODE_ONLY_RIGHT  // 单声道

// I2S 麦克风引脚 (INMP441) - 根据实际接线调整
#define I2S_SCK 5
#define I2S_WS 4
#define I2S_SD 6  // SD 引脚 (数据输入)

// I2S 功放引脚 (MAX98357) - 根据实际接线调整
#define I2S_BCLK 7
#define I2S_LRCLK 8
#define I2S_DATA 9
#define I2S_SD_MUTE 10  // 静音控制引脚（可选）

// LED 状态指示
#define LED_PIN 48  // ESP32-S3 板载 LED

// ==================== 全局变量 ====================

// Web 服务器 (配网用)
WebServer server(80);

// 状态标志
bool wifiConnected = false;
bool wsConnected = false;
volatile bool isRecording = true;
volatile bool isPlaying = false;

// 重连控制
int wifiRetryCount = 0;
const int WIFI_MAX_RETRY = 10;
unsigned long lastWifiRetry = 0;
const unsigned long WIFI_RETRY_DELAY = 5000;

// WebSocket 客户端（全局对象，确保稳定初始化）
WebSocketsClient webSocket;

// I2S 句柄
i2s_pin_config_t mic_pins;

// 音频缓冲区
static const size_t BUFFER_SIZE = 1024;
uint8_t audioBuffer[BUFFER_SIZE * sizeof(int16_t)];  // 使用 uint8_t 数组

// 播放队列（全局，WebSocket 回调和播放任务都需要访问）
// 64K 样本 = 128KB = 约 4 秒音频 (16kHz, 16bit)
static const size_t PLAY_QUEUE_SIZE = 65536;
int16_t playQueue[PLAY_QUEUE_SIZE];
volatile size_t playQueueHead = 0;
volatile size_t playQueueTail = 0;

// I2S 功放引脚
i2s_pin_config_t amp_pins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = I2S_BCLK,
    .ws_io_num = I2S_LRCLK,
    .data_out_num = I2S_DATA,
    .data_in_num = I2S_PIN_NO_CHANGE
};

// ==================== 函数声明 ====================

void initWiFi();
void initI2S();
void initWebSocket();
void initWebServer();
void audioCaptureTask(void* parameter);
void audioPlayTask(void* parameter);
void updateLED();

// WebSocket 回调
void webSocketEvent(WStype_t type, uint8_t* payload, size_t length);

// ====================  Setup  ====================

void setup() {
    // 初始化串口
    Serial.begin(115200);

    // 等待 USB 串口连接（ESP32-S3 需要）
    delay(2000);

    Serial.println("\n\n=== Nexa ESP32-S3 Firmware ===");
    Serial.println("系统启动...");

    // 初始化 LED
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    Serial.println("LED 初始化完成");

    // 闪烁 LED 表示启动
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);

    // 初始化 I2S
    Serial.println("正在初始化 I2S...");
    initI2S();
    Serial.println("I2S 初始化完成");

    // 连接 WiFi
    Serial.println("正在连接 WiFi...");
    initWiFi();

    if (wifiConnected) {
        // 测试网络连通性
        Serial.print("测试 Ping 后端服务器...");
        // WiFi 已连接，直接初始化 WebSocket
        Serial.println("正在连接 WebSocket...");
        initWebSocket();
        // 立即调用 loop 让 WebSockets 处理连接
        delay(100);
        webSocket.loop();
    }

    // 启动音频捕获任务
    xTaskCreate(
        audioCaptureTask,
        "AudioCapture",
        4096,
        NULL,
        2,
        NULL
    );

    // 启动音频播放任务
    xTaskCreate(
        audioPlayTask,
        "AudioPlay",
        4096,
        NULL,
        2,
        NULL
    );

    Serial.println("=== 初始化完成 ===\n");
}

// ====================  Loop  ====================

void loop() {
    // 处理 WebSocket（始终调用，否则无法建立连接）
    webSocket.loop();

    // 处理 Web 服务器
    server.handleClient();

    // 重连逻辑 - 由 WebSocketsClient 库自动处理

    if (!wifiConnected) {
        // 检查重试间隔
        if (millis() - lastWifiRetry >= WIFI_RETRY_DELAY) {
            if (wifiRetryCount < WIFI_MAX_RETRY) {
                Serial.printf("WiFi 断开，尝试重连... (%d/%d)\n", wifiRetryCount + 1, WIFI_MAX_RETRY);
                initWiFi();
                wifiRetryCount++;
                lastWifiRetry = millis();
            } else {
                // 超过最大重试次数，等待更长时间
                Serial.println("WiFi 连接失败次数过多，等待 30 秒后重试...");
                delay(30000);
                wifiRetryCount = 0;
                lastWifiRetry = millis();
            }
        }
        delay(10);
    }

    delay(10);
}

// ==================== WiFi  ====================

void initWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("连接 WiFi");

    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 30) {
        delay(500);
        Serial.print(".");
        timeout++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi 连接成功!");
        Serial.print("IP 地址：");
        Serial.println(WiFi.localIP());
        wifiConnected = true;
        wifiRetryCount = 0;  // 重置重试计数
        updateLED();
    } else {
        Serial.println("\nWiFi 连接失败!");
        Serial.printf("错误代码：%d\n", WiFi.status());
        wifiConnected = false;

        // TODO: 切换到 AP 模式进行配网
        // initWebServer();
    }
}

// ==================== I2S  ====================

void initI2S() {
    // 配置麦克风引脚 (RX)
    i2s_pin_config_t mic_pins = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
        .bck_io_num = I2S_SCK,
        .ws_io_num = I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_SD
    };

    // I2S 配置 (麦克风 - RX)
    // INMP441 是单声道麦克风，L/R 引脚决定输出声道
    // L/R 接地 = 左声道，L/R 接 VDD = 右声道
    // 如果 L/R 接地，请使用 I2S_CHANNEL_FMT_ONLY_LEFT
    // 如果 L/R 接 VDD，请使用 I2S_CHANNEL_FMT_ONLY_RIGHT
    i2s_config_t rx_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = AUDIO_BITS_PER_SAMPLE,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // 单声道左声道 (如果 L/R 接地)
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,  // I2S 标准格式
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,  // 每次 DMA 传输 256 样本
        .use_apll = false,   // 不使用 APLL 时钟
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    // 安装麦克风驱动
    i2s_driver_install(I2S_NUM_0, &rx_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &mic_pins);

    // 设置为单声道模式 (硬件修复)
    // 注意：INMP441 的 L/R 引脚决定左右声道
    // L/R 接地 = 左声道，L/R 接 VDD = 右声道
    // 固件配置需要与硬件接线匹配

    Serial.println("I2S 初始化完成");
}

// ==================== WebSocket  ====================

void initWebSocket() {
    Serial.println("initWebSocket 开始");
    webSocket.begin(WEBSOCKET_HOST, WEBSOCKET_PORT, WEBSOCKET_URL);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    Serial.println("initWebSocket 完成");
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
    Serial.printf("webSocketEvent 类型：%d\n", type);
    switch (type) {
        case WStype_DISCONNECTED:
            Serial.println("WebSocket 断开");
            Serial.printf("断开类型：%d\n", type);
            wsConnected = false;
            updateLED();
            Serial.println("wsConnected = false");
            break;

        case WStype_CONNECTED:
            Serial.println("WebSocket 连接成功");
            Serial.printf("WebSocket 类型：%d, 负载长度：%d\n", type, length);
            if (length > 0) {
                Serial.printf("负载内容：%s\n", payload);
            }
            wsConnected = true;
            updateLED();
            Serial.println("wsConnected = true");
            break;

        case WStype_TEXT:
            // 处理 JSON 消息
            {
                String jsonStr = String((char*)payload);
                Serial.print("收到消息：");
                Serial.println(jsonStr);

                JsonDocument doc;
                DeserializationError err = deserializeJson(doc, jsonStr);

                if (!err) {
                    const char* msgType = doc["type"];
                    Serial.printf("消息类型：%s\n", msgType);

                    if (strcmp(msgType, "audio_start") == 0) {
                        // 音频播放开始
                        Serial.println("=== 音频播放开始 ===");
                        isPlaying = true;
                        // 清空队列，避免累积旧数据
                        playQueueHead = 0;
                        playQueueTail = 0;
                        Serial.printf("队列已重置：head=%zu, tail=%zu\n", playQueueHead, playQueueTail);
                    }
                    else if (strcmp(msgType, "audio_end") == 0) {
                        // 音频播放结束
                        Serial.println("=== 音频播放结束 ===");
                        // 等待队列播放完成（最多等待 5 秒）
                        int waitCount = 0;
                        while (playQueueHead != playQueueTail && waitCount < 500) {
                            delay(10);
                            waitCount++;
                        }
                        if (waitCount >= 500) {
                            Serial.printf("警告：队列未清空，强制重置 (head=%zu, tail=%zu)\n",
                                playQueueHead, playQueueTail);
                        }
                        isPlaying = false;
                        // 清空队列
                        playQueueHead = 0;
                        playQueueTail = 0;
                        // 切换到录音模式
                        isRecording = true;
                        Serial.println("=== 切换回录音模式 ===");
                    }
                    else if (strcmp(msgType, "status") == 0) {
                        // 状态更新
                        const char* state = doc["state"];
                        Serial.printf("状态更新：%s\n", state);
                        if (strcmp(state, "speaking") == 0) {
                            isRecording = false;  // AI 播放时停止录音
                            Serial.println("isRecording = false (AI 播放中)");
                        } else if (strcmp(state, "listening") == 0) {
                            isRecording = true;   // 恢复录音
                            Serial.println("isRecording = true (恢复录音)");
                        }
                    }
                } else {
                    Serial.printf("JSON 解析失败：%s\n", err.c_str());
                }
            }
            break;

        case WStype_BIN:
            // 处理二进制音频数据 - 批量添加到播放队列
            {
                Serial.printf(">>> 收到音频数据：%d bytes\n", length);

                // 直接将二进制数据视为 int16 数组
                int16_t* samples = (int16_t*)payload;
                size_t samplesCount = length / sizeof(int16_t);
                size_t copied = 0;

                Serial.printf(">>> 样本数：%zu, head=%zu, tail=%zu\n", samplesCount, playQueueHead, playQueueTail);

                // 批量复制到环形队列
                while (copied < samplesCount) {
                    // 计算队列已用空间
                    size_t used = (playQueueHead - playQueueTail + PLAY_QUEUE_SIZE) % PLAY_QUEUE_SIZE;
                    size_t freeSpace = PLAY_QUEUE_SIZE - used - 1;  // 留 1 个空位避免 head==tail

                    if (freeSpace == 0) {
                        // 队列已满，等待播放
                        delay(5);
                        continue;
                    }

                    // 计算本次复制数量
                    size_t toCopy = min(samplesCount - copied, freeSpace);
                    size_t toEnd = PLAY_QUEUE_SIZE - playQueueHead;

                    if (toCopy <= toEnd) {
                        // 不需要绕界
                        memcpy(&playQueue[playQueueHead], &samples[copied], toCopy * sizeof(int16_t));
                        playQueueHead = (playQueueHead + toCopy) % PLAY_QUEUE_SIZE;
                        copied += toCopy;
                    } else {
                        // 需要绕界：先复制到末尾
                        memcpy(&playQueue[playQueueHead], &samples[copied], toEnd * sizeof(int16_t));
                        playQueueHead = 0;
                        copied += toEnd;
                    }
                }

                Serial.printf(">>> 复制完成：head=%zu, tail=%zu, 队列=%zu 样本\n",
                    playQueueHead, playQueueTail,
                    (playQueueHead - playQueueTail + PLAY_QUEUE_SIZE) % PLAY_QUEUE_SIZE);
            }
            break;

        case WStype_PING:
            // 服务器心跳，自动回复 PONG
            Serial.printf("收到服务器 PING\n");
            break;

        case WStype_PONG:
            Serial.printf("收到服务器 PONG\n");
            break;

        default:
            Serial.printf("未知事件类型：%d\n", type);
            break;
    }
}

// ==================== 音频捕获  ====================

void audioCaptureTask(void* parameter) {
    Serial.println("音频捕获任务启动");
    int readCount = 0;
    int zeroReadCount = 0;

    while (true) {
        if (isRecording && !isPlaying) {
            // 从 I2S 读取音频数据
            size_t bytesRead = 0;
            i2s_read(I2S_NUM_0, audioBuffer, sizeof(audioBuffer), &bytesRead, portMAX_DELAY);
            readCount++;

            if (bytesRead > 0) {
                if (readCount <= 10 || readCount % 50 == 0) {
                    Serial.printf("I2S 读取：%d bytes (第 %d 次)\n", bytesRead, readCount);
                    // 打印前几个采样值
                    int16_t* samples = (int16_t*)audioBuffer;
                    Serial.printf("采样值：");
                    for (int i = 0; i < 8 && i < bytesRead/2; i++) {
                        Serial.printf("%d ", samples[i]);
                    }
                    Serial.println();
                }
                zeroReadCount = 0;

                if (wsConnected) {
                    // 发送音频数据到服务器
                    webSocket.sendBIN(audioBuffer, bytesRead);
                    if (readCount <= 5 || readCount % 100 == 0) {
                        Serial.printf("发送音频：%d bytes, wsConnected=%d\n", bytesRead, wsConnected);
                    }
                } else {
                    if (readCount <= 5 || readCount % 100 == 0) {
                        Serial.printf("wsConnected=0, 无法发送音频\n");
                    }
                }
            } else {
                zeroReadCount++;
                if (zeroReadCount >= 5) {
                    Serial.println("警告：I2S 持续返回 0 字节，检查麦克风连接！");
                    zeroReadCount = 0;
                }
            }
        } else {
            delay(10);
        }
    }
}

// ==================== 音频播放  ====================

void audioPlayTask(void* parameter) {
    Serial.println("=== 音频播放任务启动 ===");
    delay(100);  // 等待串口输出完成

    Serial.printf("I2S_NUM_1 初始化，BCLK=%d, LRCLK=%d, DATA=%d\n", I2S_BCLK, I2S_LRCLK, I2S_DATA);
    delay(100);

    // I2S 配置 (功放 - TX)
    i2s_config_t tx_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    // 安装功放驱动
    esp_err_t ret = i2s_driver_install(I2S_NUM_1, &tx_config, 0, NULL);
    Serial.printf("I2S 驱动安装：%d\n", ret);
    delay(100);

    ret = i2s_set_pin(I2S_NUM_1, &amp_pins);
    Serial.printf("I2S 引脚设置：%d\n", ret);
    delay(100);

    Serial.println("=== 播放任务就绪 ===");

    int loopCount = 0;
    int playCount = 0;
    bool everPlayed = false;

    while (true) {
        loopCount++;

        if (isPlaying) {
            if (!everPlayed) {
                Serial.println(">>> isPlaying=true, 等待数据...");
                everPlayed = true;
            }

            if (playQueueHead != playQueueTail) {
                // 计算可用数据量
                size_t available = (playQueueHead - playQueueTail + PLAY_QUEUE_SIZE) % PLAY_QUEUE_SIZE;
                size_t samplesToPlay = min((size_t)256, available);

                if (samplesToPlay > 0) {
                    // 播放音频
                    size_t bytesWritten = 0;
                    esp_err_t ret = i2s_write(I2S_NUM_1, &playQueue[playQueueTail], samplesToPlay * sizeof(int16_t), &bytesWritten, portMAX_DELAY);
                    playQueueTail = (playQueueTail + samplesToPlay) % PLAY_QUEUE_SIZE;
                    playCount++;

                    if (playCount <= 10 || playCount % 100 == 0) {
                        Serial.printf("播放进度：%d 次，bytes=%d, ret=%d\n", playCount, bytesWritten, ret);
                    }
                }
            } else if (loopCount % 100 == 0) {
                Serial.printf("等待数据：playQueueHead=%zu, playQueueTail=%zu\n", playQueueHead, playQueueTail);
            }
        } else if (loopCount % 100 == 0) {
            Serial.printf("等待播放：isPlaying=%d\n", isPlaying);
        }

        delay(10);
    }
}

// ==================== 工具函数  ====================

void updateLED() {
    if (!wifiConnected) {
        // WiFi 未连接：慢闪
        digitalWrite(LED_PIN, millis() % 1000 < 500 ? HIGH : LOW);
    } else if (!wsConnected) {
        // WebSocket 未连接：快闪
        digitalWrite(LED_PIN, millis() % 200 < 100 ? HIGH : LOW);
    } else {
        // 已连接：常亮
        digitalWrite(LED_PIN, HIGH);
    }
}

// ==================== Web 服务器 (配网)  ====================

void initWebServer() {
    // TODO: 实现配网页面
    /*
    server.on("/", []() {
        server.send(200, "text/html", "<h1>Nexa 配网页面</h1>");
    });

    server.begin();
    Serial.println("Web 服务器启动 (AP 模式)");
    */
}
