# 硬件接线指南

## 材料清单

| 组件 | 数量 | 备注 |
|------|------|------|
| ESP32-S3 开发板 | 1 | 建议带 PSRAM 版本 |
| INMP441 麦克风模块 | 1 | I2S 数字麦克风 |
| MAX98357 功放模块 | 1 | I2S 音频功放 |
| 喇叭 | 1 | 4Ω 3-5W |
| 杜邦线 | 若干 | 母对母或公对母 |

## 接线图

### INMP441 麦克风接线

```
ESP32-S3          INMP441
─────────         ───────
3.3V         ──── VDD
GND          ──── GND
GPIO4 (WS)   ──── WS
GPIO5 (SCK)  ──── SCK
GPIO6 (SD)   ──── SD
GND          ──── L/R (左声道接地)
```

### MAX98357 功放接线

```
ESP32-S3          MAX98357
─────────         ────────
5V           ──── VDD
GND          ──── GND
GPIO7 (BCLK) ──── BCLK
GPIO8 (LRCLK)──── LRCLK
GPIO9 (DIN)  ──── DIN
GPIO10       ──── SD_MODE (静音控制，可选)
               ──── GAIN (增益，悬空或接电阻)
OUT+  ──── 喇叭正极
OUT-  ──── 喇叭负极
```

## 引脚自定义

如果默认引脚不可用，可以在 `firmware/src/main.cpp` 中修改：

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

## 注意事项

1. **电源**：INMP441 使用 3.3V，MAX98357 使用 5V
2. **接地**：确保所有 GND 共地
3. **I2S 时钟**：WS 和 LRCLK 不要混淆
4. **音频质量**：尽量使用短线，减少干扰
