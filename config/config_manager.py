"""
配置管理器模块
提供YAML配置文件的读取和管理功能
"""

import os
import yaml
from typing import Any, Dict, Optional


class ConfigManager:
    """配置管理器类"""

    def __init__(self, config_file: str = "config.yaml"):
        """
        初始化配置管理器

        Args:
            config_file (str): 配置文件路径
        """
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}

        # 延迟导入日志函数以避免循环依赖
        from utils.logger import get_app_logger, get_error_logger

        self.app_logger = get_app_logger()
        self.error_logger = get_error_logger()
        self._load_config()

    def _load_config(self) -> None:
        """
        加载配置文件
        """
        try:
            # 检查配置文件是否存在
            if not os.path.exists(self.config_file):
                self.app_logger.error(
                    f"配置文件 {self.config_file} 不存在，程序无法启动"
                )
                raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")

            # 读取YAML配置文件
            with open(self.config_file, "r", encoding="utf-8") as file:
                self.config_data = yaml.safe_load(file) or {}

            self.app_logger.info(f"成功加载配置文件 {self.config_file}")
        except yaml.YAMLError as e:
            self.error_logger.error(f"配置文件 {self.config_file} 格式错误: {e}")
            raise
        except Exception as e:
            # 延迟导入以避免循环依赖
            from utils.logger import log_exception
            log_exception(
                self.error_logger, f"加载配置文件 {self.config_file} 时发生异常"
            )
            raise

    def _create_default_config(self) -> None:
        """
        创建默认配置文件
        """
        # 移除默认配置文件创建逻辑，如果配置文件不存在则程序无法启动
        pass

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项的值

        Args:
            key_path (str): 配置项路径，使用点号分隔，例如 "trading.magic_number"
            default (Any): 默认值

        Returns:
            Any: 配置项的值
        """
        keys = key_path.split(".")
        value = self.config_data

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def reload(self) -> None:
        """
        重新加载配置文件
        """
        self._load_config()


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例

    Returns:
        ConfigManager: 配置管理器实例
    """
    return config_manager
