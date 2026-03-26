"""
Nexa AI Backend - 主程序入口
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from services.websocket_server import WebSocketServer
from config import LOG_LEVEL


def setup_logging():
    """配置日志"""
    # 创建日志目录
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=LOG_LEVEL,
        colorize=True
    )

    # 添加文件输出
    logger.add(
        log_dir / "nexa_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        level="DEBUG",
        encoding="utf-8"
    )

    logger.info("日志系统初始化完成")


def main():
    """主函数"""
    setup_logging()
    logger.info("=" * 50)
    logger.info("Nexa AI Backend 启动中...")
    logger.info("=" * 50)

    server = WebSocketServer()

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("\n收到退出信号，正在关闭...")
    except Exception as e:
        logger.error(f"服务器异常：{e}")
        raise


if __name__ == "__main__":
    main()
