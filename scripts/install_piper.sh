#!/bin/bash
# Piper TTS 安装脚本
# 用于 macOS 和 Linux

set -e

PIPER_VERSION="1.2.0"
INSTALL_DIR="${PIPER_INSTALL_DIR:-$HOME/piper}"
MODEL_DIR="${PIPER_MODEL_DIR:-$HOME/piper/models}"

echo "========================================"
echo "Piper TTS 安装脚本"
echo "========================================"

# 检测系统
detect_os() {
    case "$(uname -s)" in
        Darwin)
            echo "macos"
            ;;
        Linux)
            if grep -q "Ubuntu" /etc/*-release; then
                echo "ubuntu"
            elif grep -q "Debian" /etc/*-release; then
                echo "debian"
            elif grep -q "CentOS" /etc/*-release; then
                echo "centos"
            else
                echo "linux"
            fi
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

OS=$(detect_os)
ARCH="$(uname -m)"

echo "检测到系统：$OS ($ARCH)"

# 创建安装目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$MODEL_DIR"

# 下载 Piper
download_piper() {
    local os_name=$1
    local arch=$2

    if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
        arch="aarch64"
    elif [ "$arch" = "x86_64" ]; then
        arch="x64"
    fi

    local filename="piper_${os_name}_${arch}.tar.gz"
    local download_url="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/${filename}"

    echo "正在下载 Piper: ${download_url}"

    curl -L -o "$INSTALL_DIR/piper.tar.gz" "$download_url"

    echo "正在解压..."
    tar -xzf "$INSTALL_DIR/piper.tar.gz" -C "$INSTALL_DIR"
    rm "$INSTALL_DIR/piper.tar.gz"

    # 设置执行权限
    chmod +x "$INSTALL_DIR/piper" 2>/dev/null || true

    echo "Piper 安装完成：$INSTALL_DIR/piper"
}

# 下载中文语音模型
download_chinese_model() {
    local model_name="${1:-zh-cnxiaoxiao}"
    local quality="${2:-high}"

    local filename="${model_name}_${quality}.onnx"
    local config_filename="${model_name}_${quality}.onnx.json"
    local base_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/${model_name}/${quality}"

    echo "正在下载中文语音模型：${model_name} (${quality})"

    # 下载模型
    curl -L -o "$MODEL_DIR/${filename}" "${base_url}/${filename}"
    curl -L -o "$MODEL_DIR/${config_filename}" "${base_url}/${config_filename}"

    echo "模型下载完成：$MODEL_DIR/${filename}"
}

# 安装 Python 依赖
install_python_deps() {
    echo "正在安装 Python 依赖..."
    pip3 install numpy
    echo "Python 依赖安装完成"
}

# 主安装流程
main() {
    echo ""
    echo "1. 安装 Piper 命令行工具..."
    download_piper "$OS" "$ARCH"

    echo ""
    echo "2. 安装 Python 依赖..."
    install_python_deps

    echo ""
    echo "3. 下载中文语音模型..."

    # 提供模型选择
    echo "请选择语音模型质量:"
    echo "  1) high  - 高质量 (约 100MB，推荐)"
    echo "  2) medium - 中等质量 (约 50MB)"
    echo "  3) low   - 低质量 (约 20MB，最快)"
    read -p "请选择 [1/2/3] (默认：1): " quality_choice

    case $quality_choice in
        1) quality="high" ;;
        2) quality="medium" ;;
        3) quality="low" ;;
        *) quality="high" ;;
    esac

    download_chinese_model "zh-cnxiaoxiao" "$quality"

    echo ""
    echo "========================================"
    echo "安装完成!"
    echo "========================================"
    echo ""
    echo "Piper 路径：$INSTALL_DIR/piper"
    echo "模型路径：$MODEL_DIR/zh-cnxiaoxiao_${quality}.onnx"
    echo ""
    echo "请在 .env 文件中添加:"
    echo "  PIPER_PATH=$INSTALL_DIR/piper"
    echo "  PIPER_MODEL_PATH=$MODEL_DIR/zh-cnxiaoxiao_${quality}.onnx"
    echo ""

    # 测试安装
    echo "测试安装..."
    echo "你好，这是 Piper 语音合成测试。" | "$INSTALL_DIR/piper" -m "$MODEL_DIR/zh-cnxiaoxiao_${quality}.onnx" -f pipe --output-raw | \
        ffplay -nodisp -autoexit -ar 16000 -ac 1 -f s16le -

    echo ""
    echo "如果听到声音，说明安装成功!"
}

# 运行安装
main
