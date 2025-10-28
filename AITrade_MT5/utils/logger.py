"""
日志模块
提供统一的日志记录接口
"""

import logging


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name (str): 日志记录器名称，默认使用调用模块名

    Returns:
        logging.Logger: 日志记录器实例
    """
    if name is None:
        name = __name__

    return logging.getLogger(name)


def get_app_logger() -> logging.Logger:
    """
    获取应用程序日志记录器

    Returns:
        logging.Logger: 应用程序日志记录器
    """
    return logging.getLogger("app")


def get_trading_logger() -> logging.Logger:
    """
    获取交易日志记录器

    Returns:
        logging.Logger: 交易日志记录器
    """
    return logging.getLogger("trading")


def get_error_logger() -> logging.Logger:
    """
    获取错误日志记录器

    Returns:
        logging.Logger: 错误日志记录器
    """
    return logging.getLogger("error")


def log_exception(logger: logging.Logger, message: str):
    """
    记录异常信息

    Args:
        logger (logging.Logger): 日志记录器
        message (str): 附加消息
    """
    logger.exception(message)


def setup_mt5_logging():
    """
    设置MT5相关的日志记录
    """
    mt5_logger = get_trading_logger()
    mt5_logger.info("MT5日志模块已初始化")
    return mt5_logger


def initialize_logging():
    """
    初始化日志系统
    此函数需要在程序启动时调用，以确保日志系统正确配置
    """
    from config.logging_config import setup_logging
    setup_logging()


# 创建默认的日志记录器实例
app_logger = get_app_logger()
trading_logger = get_trading_logger()
error_logger = get_error_logger()
