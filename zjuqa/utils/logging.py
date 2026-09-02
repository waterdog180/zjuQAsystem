"""
logging.py —— 统一日志配置。

详细信息（带时间戳）保存到 logs/ 目录下的日志文件，
控制台只输出关键步骤和进度条（由 progress.py 控制）。

使用说明：
    from zjuqa.utils.logging import get_logger
    logger = get_logger(__name__)
    logger.info("处理开始")
    logger.warning("数据异常")
    logger.error("处理失败", exc_info=True)
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.paths import LOG_DIR

# 全局日志文件路径（程序启动时创建一次，所有 logger 共享）
_LOG_FILE: Optional[Path] = None


def _get_log_file() -> Path:
    """获取当前运行的日志文件路径（懒加载，程序启动时创建一次）。"""
    global _LOG_FILE
    if _LOG_FILE is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG_FILE = LOG_DIR / f"zjuqa_{timestamp}.log"
    return _LOG_FILE


def get_logger(name: str = "zjuqa", level: int = logging.INFO) -> logging.Logger:
    """
    获取配置好的 logger 实例。

    日志同时输出到：
      1. 文件：logs/zjuqa_YYYYMMDD_HHMMSS.log（带时间戳，详细信息）
      2. 控制台：stdout（关键步骤，与进度条配合）

    Args:
        name:  logger 名称，通常传 __name__
        level: 日志级别，默认 INFO

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 文件处理器（详细日志，带时间戳）
        file_handler = logging.FileHandler(_get_log_file(), encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        # 控制台处理器（关键步骤）
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    return logger


def get_log_file_path() -> str:
    """返回当前日志文件的路径，便于用户查看。"""
    return str(_get_log_file())
