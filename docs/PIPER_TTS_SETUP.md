# Piper TTS 本地部署指南

Piper 是一个快速、本地的神经语音合成系统，支持中文等多种语言。相比在线 TTS 服务，Piper 具有以下优势：

- **离线运行**：无需网络连接，保护隐私
- **低延迟**：本地推理，响应快速
- **免费**：无需 API 密钥或订阅
- **轻量**：模型文件小，资源占用低

## 快速安装

### 方法一：自动安装脚本（推荐）

```bash
# 进入项目目录
cd /path/to/Nexa

# 运行安装脚本
bash scripts/install_piper.sh
```

脚本会自动：
1. 下载并安装 Piper 命令行工具
2. 安装 Python 依赖
3. 下载中文语音模型（可选择质量）
4. 测试安装是否成功

### 方法二：手动安装

#### 1. 安装 Piper Python 库

```bash
pip3 install piper-tts
```

#### 2. 下载语音模型

**中文语音模型下载（多个镜像源，任选其一）：**

**源 1 - 魔搭社区（ModelScope，推荐国内用户）：**
```bash
mkdir -p ~/piper/models
cd ~/piper/models

# 使用 modelsync 工具下载
git clone https://www.modelscope.cn/rhasspy/piper-voices.git .
# 或手动下载所需模型文件
```

**源 2 - HuggingFace（需要科学上网）：**
```bash
# 下载 zh-cnxiaoxiao 高质量模型
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/zh-cnxiaoxiao/high/zh-cnxiaoxiao_high.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/zh-cnxiaoxiao/high/zh-cnxiaoxiao_high.onnx.json
```

**源 3 - GitHub Releases（备用）：**
```bash
# 访问 https://github.com/OHF-voice/piper/releases 查看是否有预打包的模型
```

**模型文件说明：**

| 模型名 | 质量 | 大小 | 描述 |
|--------|------|------|------|
| zh-cnxiaoxiao-high | 高 | ~100MB | 温柔女声，推荐 |
| zh-cnxiaoyi-high | 高 | ~100MB | 另一种女声 |
| zh-cnlibiao-high | 高 | ~100MB | 成熟男声 |

```bash
# 测试 Piper 命令行
echo "你好，这是 Piper 语音合成测试。" | piper -m ~/piper/models/zh-cnxiaoxiao-high.onnx -f pipe --output-raw | ffplay -nodisp -autoexit -ar 16000 -ac 1 -f s16le -
```

如果听到声音，说明安装成功！

## 配置 Nexa 后端

### 1. 编辑 .env 文件

在 `backend/.env` 文件中添加：

```bash
# Piper TTS 配置
PIPER_PATH=/usr/local/bin/piper
PIPER_MODEL_PATH=/Users/yourname/piper/models/zh-cnxiaoxiao-high.onnx
PIPER_CONFIG_PATH=/Users/yourname/piper/models/zh-cnxiaoxiao-high.onnx.json
```

请根据你的实际安装路径修改。

### 2. 重启后端服务

```bash
cd /path/to/Nexa/backend
python3 main.py
```

查看日志，确认 Piper TTS 初始化成功：
```
✓ TTS 服务 (Piper 本地 TTS) 初始化成功
```

## 故障排除

### 问题 1：找不到 piper 命令

```bash
# 检查 piper 是否安装
which piper

# 如果未找到，手动指定路径
export PIPER_PATH=/path/to/piper
```

### 问题 2：模型文件不存在

确保 `.env` 中的 `PIPER_MODEL_PATH` 指向正确的模型文件路径。

### 问题 3：合成速度慢

- 使用 `-medium` 或 `-low` 质量的模型（文件更小）
- 确保 CPU 没有其他高负载任务

### 问题 4：音质不佳

- 尝试 `high` 质量的模型
- 检查音频采样率配置（应为 16000Hz）

## 备份方案：Edge TTS

如果 Piper 无法使用，系统会自动降级到 Edge TTS（需要网络连接）：

```bash
# .env 中无需额外配置
# 确保安装了 edge-tts
pip3 install edge-tts
```

## 模型文件参考

完整语音模型列表：https://huggingface.co/rhasspy/piper-voices

### 中文语音模型

| 语言 | 模型 | 质量 | 描述 |
|------|------|------|------|
| 普通话 | zh-cnxiaoxiao | high/medium/low | 温柔女声（推荐） |
| 普通话 | zh-cnxiaoyi | high/medium/low | 清晰女声 |
| 普通话 | zh-cnlibiao | high/medium/low | 成熟男声 |
| 粤语 | zh-huixuan | high/medium/low | 粤语女声 |

## 性能参考

在 M1 Mac 上的合成速度：
- high 模型：约 100-200ms 延迟，实时率约 0.1x
- medium 模型：约 50-100ms 延迟，实时率约 0.05x
- low 模型：约 20-50ms 延迟，实时率约 0.02x

（实时率 = 合成时间 / 音频时长，越小越好）
