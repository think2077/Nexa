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
#define WIFI_SSID "YourSSID"
#define WIFI_PASSWORD "YourPassword"

// 服务器配置
#define WEBSOCKET_HOST "192.168.1.100"  // Python 服务器 IP
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

// WebSocket 客户端
WebSocketsClient webSocket;

// Web 服务器 (配网用)
WebServer server(80);

// 状态标志
bool wifiConnected = false;
bool wsConnected = false;
bool isRecording = true;
bool isPlaying = false;

// I2S 句柄
i2s_pin_config_t mic_pins;

// 音频缓冲区
static const size_t BUFFER_SIZE = 1024;
uint8_t audioBuffer[BUFFER_SIZE * sizeof(int16_t)];  // 使用 uint8_t 数组

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
    Serial.begin(115200);
    Serial.println("\n\n=== Nexa ESP32-S3 Firmware ===");

    // 初始化 LED
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    // 初始化 I2S
    Serial.println("正在初始化 I2S...");
    initI2S();

    // 连接 WiFi
    Serial.println("正在连接 WiFi...");
    initWiFi();

    if (wifiConnected) {
        // 初始化 WebSocket
        Serial.println("正在连接 WebSocket...");
        initWebSocket();
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
    // 处理 WebSocket
    if (wsConnected) {
        webSocket.loop();
    }

    // 处理 Web 服务器
    server.handleClient();

    // 重连逻辑
    if (!wsConnected && wifiConnected) {
        Serial.println("WebSocket 断开，尝试重连...");
        delay(1000);
        initWebSocket();
    }

    if (!wifiConnected) {
        Serial.println("WiFi 断开，尝试重连...");
        delay(1000);
        initWiFi();
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
        updateLED();
    } else {
        Serial.println("\nWiFi 连接失败!");
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
    i2s_config_t rx_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = AUDIO_BITS_PER_SAMPLE,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,  // 单声道
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    // 安装麦克风驱动
    i2s_driver_install(I2S_NUM_0, &rx_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &mic_pins);

    Serial.println("I2S 初始化完成");
}

// ==================== WebSocket  ====================

void initWebSocket() {
    webSocket.begin(WEBSOCKET_HOST, WEBSOCKET_PORT, WEBSOCKET_URL);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);

    Serial.print("连接 WebSocket 服务器: ");
    Serial.print(WEBSOCKET_HOST);
    Serial.print(":");
    Serial.println(WEBSOCKET_PORT);
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_DISCONNECTED:
            Serial.println("WebSocket 断开");
            wsConnected = false;
            updateLED();
            break;

        case WStype_CONNECTED:
            Serial.println("WebSocket 连接成功");
            wsConnected = true;
            updateLED();
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

                    if (strcmp(msgType, "audio_playback") == 0) {
                        // 收到音频播放数据
                        const char* format = doc["format"];
                        const char* data = doc["data"];

                        // Base64 解码并发送到播放队列
                        // TODO: 实现 Base64 解码和播放队列
                        Serial.println("收到音频播放数据");
                    }
                }
            }
            break;

        case WStype_BIN:
            // 处理二进制音频数据
            Serial.printf("收到二进制数据：%d bytes\n", length);
            // TODO: 发送到播放队列
            break;

        default:
            break;
    }
}

// ==================== 音频捕获  ====================

void audioCaptureTask(void* parameter) {
    Serial.println("音频捕获任务启动");

    while (true) {
        if (isRecording && !isPlaying) {
            // 从 I2S 读取音频数据
            size_t bytesRead = 0;
            i2s_read(I2S_NUM_0, audioBuffer, sizeof(audioBuffer), &bytesRead, portMAX_DELAY);

            if (bytesRead > 0 && wsConnected) {
                // 发送音频数据到服务器
                webSocket.sendBIN(audioBuffer, bytesRead);
            }
        } else {
            delay(10);
        }
    }
}

// ==================== 音频播放  ====================

// 播放队列（简单实现）
static const size_t PLAY_QUEUE_SIZE = 8192;
int16_t playQueue[PLAY_QUEUE_SIZE];
size_t playQueueHead = 0;
size_t playQueueTail = 0;

void audioPlayTask(void* parameter) {
    Serial.println("音频播放任务启动");

    while (true) {
        if (isPlaying && playQueueHead != playQueueTail) {
            // 从播放队列读取数据
            size_t samplesToPlay = min((size_t)256, (playQueueHead - playQueueTail + PLAY_QUEUE_SIZE) % PLAY_QUEUE_SIZE);

            if (samplesToPlay > 0) {
                // TODO: 切换到功放模式并播放
                // i2s_set_pin(I2S_NUM_0, &amp_pins);
                // i2s_write(I2S_NUM_0, ...);

                playQueueTail = (playQueueTail + samplesToPlay) % PLAY_QUEUE_SIZE;
            }
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
