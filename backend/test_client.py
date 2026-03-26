"""
测试客户端 - 用于测试后端服务
可以模拟 ESP32 发送音频流
"""
import asyncio
import json
import wave
import base64
from pathlib import Path
from loguru import logger

import websockets
from config import WEBSOCKET_HOST, WEBSOCKET_PORT, AUDIO_SAMPLE_RATE


async def test_connection():
    """测试 WebSocket 连接"""
    uri = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"

    logger.info(f"尝试连接：{uri}")

    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✓ 连接成功")

            # 接收欢迎消息
            welcome = await websocket.recv()
            logger.info(f"收到欢迎消息：{welcome}")

            return True

    except Exception as e:
        logger.error(f"连接失败：{e}")
        return False


async def test_with_audio_file(audio_file: str):
    """
    使用音频文件测试完整流程

    Args:
        audio_file: WAV 文件路径
    """
    uri = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"

    # 读取 WAV 文件
    with wave.open(str(audio_file), 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()

        logger.info(f"音频文件信息:")
        logger.info(f"  采样率：{sample_rate} Hz")
        logger.info(f"  声道数：{n_channels}")
        logger.info(f"  位深：{sample_width * 8} bit")

        if sample_rate != AUDIO_SAMPLE_RATE:
            logger.warning(f"采样率不匹配！期望 {AUDIO_SAMPLE_RATE} Hz")

        audio_data = wf.readframes(wf.getnframes())

    async with websockets.connect(uri) as websocket:
        # 接收欢迎消息
        await websocket.recv()

        logger.info("开始发送音频数据...")

        # 分帧发送（模拟实时流）
        chunk_size = int(AUDIO_SAMPLE_RATE * sample_width * n_channels * 0.2)  # 200ms 一帧
        chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]

        logger.info(f"共 {len(chunks)} 帧")

        for i, chunk in enumerate(chunks):
            await websocket.send(chunk)
            if i % 5 == 0:
                logger.debug(f"发送第 {i} 帧")
            await asyncio.sleep(0.2)  # 实时发送

        logger.info("发送完成，等待响应...")

        # 接收响应
        while True:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(response)
                msg_type = data.get("type")

                logger.info(f"收到响应：type={msg_type}")

                if msg_type == "transcript":
                    logger.info(f"识别结果：{data.get('text')}")
                elif msg_type == "audio_playback":
                    logger.info(f"收到 TTS 音频：{len(data.get('data', ''))} bytes")
                elif msg_type == "status":
                    logger.info(f"状态：{data.get('state')}")

            except asyncio.TimeoutError:
                logger.info("等待超时，测试结束")
                break


async def test_manual_text():
    """手动输入文字测试 TTS"""
    uri = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"

    async with websockets.connect(uri) as websocket:
        # 接收欢迎消息
        await websocket.recv()

        while True:
            text = input("\n输入文字 (q 退出): ")
            if text.lower() == 'q':
                break

            # 发送测试消息
            await websocket.send(json.dumps({
                "type": "test_tts",
                "text": text
            }))

            # 接收响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(response)
                logger.info(f"响应：{data}")
            except asyncio.TimeoutError:
                logger.warning("等待超时")


async def main():
    """主函数"""
    import sys

    logger.add(sys.stderr, level="INFO")

    # 先测试连接
    if not await test_connection():
        logger.error("无法连接到服务器，请先启动 backend/main.py")
        return

    logger.info("\n连接测试通过!")

    # 检查是否有音频文件参数
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if Path(audio_file).exists():
            await test_with_audio_file(audio_file)
        else:
            logger.error(f"音频文件不存在：{audio_file}")
    else:
        logger.info("\n使用方法:")
        logger.info(f"  python {sys.argv[0]} [audio_file.wav]")
        logger.info("\n运行手动测试模式...")
        await test_manual_text()


if __name__ == "__main__":
    asyncio.run(main())
