"""
logging.py —— 统一日志配置。

提供轻量的日志配置，替代零散的 print 语句。
当前项目仍以 print 为主，本模块提供可选的日志升级路径。

使用说明：
    from zjuqa.utils.logging import get_logger
    logger = get_logger(__name__)
    logger.info("处理开始")
    logger.warning("数据异常")
"""

import logging
import sys


def get_logger(name: str = "zjuqa", level: int = logging.INFO) -> logging.Logger:
    """
    获取配置好的 logger 实例。

    统一格式：时间 - 名称 - 级别 - 消息
    输出到 stdout，便于在 CLI 中查看。

    Args:
        name:  logger 名称，通常传 __name__
        level: 日志级别，默认 INFO

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger
