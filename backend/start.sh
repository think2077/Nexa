#!/bin/bash
# Nexa 后端快速启动脚本

set -e

echo "================================"
echo "  Nexa Backend 快速启动"
echo "================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 Python3"
    exit 1
fi

echo "Python 版本：$(python3 --version)"

# 创建虚拟环境 (如果不存在)
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "检查依赖..."
pip install -q -r requirements.txt

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告：未找到 .env 文件"
    echo "请复制 .env.example 为 .env 并配置 ANTHROPIC_API_KEY"
    cp .env.example .env
fi

# 创建日志目录
mkdir -p logs

# 启动服务
echo ""
echo "启动 WebSocket 服务器..."
echo "服务地址：ws://0.0.0.0:8765"
echo "按 Ctrl+C 停止服务"
echo ""

python main.py
