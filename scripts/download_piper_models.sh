#!/bin/bash
# Piper TTS 中文语音模型下载脚本
# 使用镜像源加速下载

set -e

MODEL_DIR="${PIPER_MODEL_DIR:-$HOME/piper/models}"
MIRROR="${PIPER_MIRROR:-hf}"  # hf = HuggingFace, mirror = 阿里镜像

echo "========================================"
echo "Piper TTS 中文语音模型下载"
echo "========================================"
echo ""

# 创建模型目录
mkdir -p "$MODEL_DIR"

# 模型选择
echo "请选择要下载的语音模型:"
echo "  1) zh-cnxiaoxiao - 温柔女声 (推荐)"
echo "  2) zh-cnxiaoyi   - 清晰女声"
echo "  3) zh-cnlibiao   - 成熟男声"
echo ""
read -p "请选择 [1/2/3] (默认：1): " voice_choice

case $voice_choice in
    1) model_id="zh-cnxiaoxiao" ;;
    2) model_id="zh-cnxiaoyi" ;;
    3) model_id="zh-cnlibiao" ;;
    *) model_id="zh-cnxiaoxiao" ;;
esac

# 质量选择
echo ""
echo "请选择模型质量:"
echo "  1) high   - 高质量 (约 100MB，推荐)"
echo "  2) medium - 中等质量 (约 50MB)"
echo "  3) low    - 低质量 (约 20MB，最快)"
echo ""
read -p "请选择 [1/2/3] (默认：1): " quality_choice

case $quality_choice in
    1) quality="high" ;;
    2) quality="medium" ;;
    3) quality="low" ;;
    *) quality="high" ;;
esac

echo ""
echo "正在下载：$model_id ($quality)"
echo "保存位置：$MODEL_DIR"
echo ""

# 文件名
filename="${model_id}_${quality}.onnx"
config_filename="${model_id}_${quality}.onnx.json"

# HuggingFace 基础 URL
base_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/${model_id}/${quality}"

# 使用 aria2c 如果可用（支持断点续传）
if command -v aria2c &> /dev/null; then
    echo "使用 aria2c 下载（支持断点续传）..."
    aria2c -x4 -s4 -k1M -c -o "$MODEL_DIR/${filename}" "${base_url}/${filename}"
    aria2c -x4 -s4 -k1M -c -o "$MODEL_DIR/${config_filename}" "${base_url}/${config_filename}"
else
    # 使用 curl
    echo "使用 curl 下载..."
    curl -L -o "$MODEL_DIR/${filename}" "${base_url}/${filename}"
    curl -L -o "$MODEL_DIR/${config_filename}" "${base_url}/${config_filename}"
fi

echo ""
echo "========================================"
echo "下载完成!"
echo "========================================"
echo ""
echo "模型文件：$MODEL_DIR/${filename}"
echo "配置文件：$MODEL_DIR/${config_filename}"
echo ""

# 验证文件
if [ -f "$MODEL_DIR/${filename}" ]; then
    size=$(ls -lh "$MODEL_DIR/${filename}" | awk '{print $5}')
    echo "✓ 模型文件存在，大小：$size"
else
    echo "✗ 模型文件下载失败!"
    exit 1
fi

# 测试
echo ""
echo "是否现在测试语音合成？"
read -p "需要 piper 命令行工具已安装 [y/N]: " test_choice

if [ "$test_choice" = "y" ] || [ "$test_choice" = "Y" ]; then
    if command -v piper &> /dev/null; then
        echo ""
        echo "开始测试..."
        echo "你好，这是 Piper 语音合成测试。我是${model_id}，很高兴为你服务。" | \
            piper -m "$MODEL_DIR/${filename}" -f pipe --output-raw | \
            ffplay -nodisp -autoexit -ar 16000 -ac 1 -f s16le -
        echo ""
        echo "测试完成!"
    else
        echo "piper 命令行工具未安装，跳过测试。"
        echo "请先运行：bash scripts/install_piper.sh"
    fi
fi

echo ""
echo "请在 .env 文件中添加:"
echo "  PIPER_MODEL_PATH=$MODEL_DIR/${filename}"
echo "  PIPER_CONFIG_PATH=$MODEL_DIR/${config_filename}"
