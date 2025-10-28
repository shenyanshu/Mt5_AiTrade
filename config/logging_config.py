"""
日志配置模块
提供统一的日志配置管理
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from config.config_manager import get_config_manager


def get_log_config():
    """
    获取日志配置

    Returns:
        dict: 日志配置字典
    """
    # 从配置文件获取日志目录
    config_manager = get_config_manager()
    log_dir = config_manager.get("logging.log_directory", "logs")

    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 获取当前日期作为日志文件名的一部分
    current_date = datetime.now().strftime("%Y-%m-%d")

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": f"{log_dir}/app_{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "trading_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": f"{log_dir}/trading_{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": f"{log_dir}/error_{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "app": {
                "handlers": ["console", "app_file"],
                "level": "DEBUG",
                "propagate": False,
            },
            "trading": {
                "handlers": ["console", "trading_file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
            "error": {
                "handlers": ["console", "error_file"],
                "level": "ERROR",
                "propagate": False,
            },
        },
        "root": {"handlers": ["console", "app_file"], "level": "DEBUG"},
    }

    return config


def setup_logging():
    """
    设置日志系统
    """
    import logging.config

    config = get_log_config()
    logging.config.dictConfig(config)
