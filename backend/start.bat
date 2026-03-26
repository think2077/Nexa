@echo off
REM Nexa Backend 快速启动脚本 (Windows)

echo ================================
echo   Nexa Backend 快速启动
echo ================================

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python
    exit /b 1
)

REM 创建虚拟环境 (如果不存在)
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo 检查依赖...
pip install -q -r requirements.txt

REM 检查 .env 文件
if not exist ".env" (
    echo 警告：未找到 .env 文件
    echo 请复制 .env.example 为 .env 并配置 ANTHROPIC_API_KEY
    copy .env.example .env
)

REM 创建日志目录
if not exist "logs" mkdir logs

REM 启动服务
echo.
echo 启动 WebSocket 服务器...
echo 服务地址：ws://0.0.0.0:8765
echo 按 Ctrl+C 停止服务
echo.

python main.py
