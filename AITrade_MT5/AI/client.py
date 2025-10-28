# -*- coding: utf-8 -*-

"""
AI客户端模块
提供与OpenAI API的通信功能
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import openai
from config.config_manager import get_config_manager
from utils.logger import get_app_logger, get_error_logger, log_exception
from AI.prompts import count_prompt_tokens


class AIClientError(Exception):
    """AI客户端异常"""

    pass


class OpenAIClient:
    """OpenAI API客户端"""

    def __init__(self, config_key: str = "ai"):
        """
        初始化OpenAI客户端

        Args:
            config_key (str): 配置文件中的配置键名
        """
        self.app_logger = get_app_logger()
        self.error_logger = get_error_logger()
        self.config_manager = get_config_manager()

        # 加载配置
        self._load_config(config_key)

        # 初始化OpenAI客户端
        self._init_client()

    def _load_config(self, config_key: str) -> None:
        """
        加载AI配置

        Args:
            config_key (str): 配置键名
        """
        try:
            self.base_url = self.config_manager.get(f"{config_key}.base_url")
            self.api_key = self.config_manager.get(f"{config_key}.api_key")
            self.model_id = self.config_manager.get(f"{config_key}.model_id")
            self.timeout = self.config_manager.get(f"{config_key}.timeout", 30)  # 默认30秒
            self.user_agent = self.config_manager.get(f"{config_key}.user_agent")  # 自定义User-Agent

            # 验证必需配置
            if not self.base_url:
                raise AIClientError("配置中缺少base_url")
            if not self.api_key:
                raise AIClientError("配置中缺少api_key")
            if not self.model_id:
                raise AIClientError("配置中缺少model_id")

            self.app_logger.info(
                f"AI配置加载成功: {self.base_url}, 模型: {self.model_id}"
            )

        except Exception as e:
            log_exception(self.error_logger, "加载AI配置时发生异常")
            raise AIClientError(f"AI配置加载失败: {e}")

    def _init_client(self) -> None:
        """初始化OpenAI客户端"""
        try:
            # 构建客户端配置
            client_config = {
                "api_key": self.api_key,
                "base_url": self.base_url
            }

            # 如果配置了自定义User-Agent，添加到HTTP客户端中
            if self.user_agent:
                # 创建自定义HTTP客户端
                import httpx

                # 设置自定义headers
                default_headers = {
                    "User-Agent": self.user_agent
                }

                # 创建httpx客户端
                http_client = httpx.Client(
                    headers=default_headers,
                    timeout=self.timeout
                )

                # 使用自定义HTTP客户端初始化OpenAI客户端
                client_config["http_client"] = http_client

                self.app_logger.info(f"OpenAI客户端使用自定义User-Agent: {self.user_agent}")

            self.client = openai.OpenAI(**client_config)
            self.app_logger.info("OpenAI客户端初始化成功")

        except Exception as e:
            log_exception(self.error_logger, "初始化OpenAI客户端时发生异常")
            raise AIClientError(f"OpenAI客户端初始化失败: {e}")

    def analyze_market(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        调用AI进行市场分析

        Args:
            system_prompt (str): 系统提示词
            user_prompt (str): 用户提示词

        Returns:
            Dict[str, Any]: AI分析结果

        Raises:
            AIClientError: AI调用失败时抛出
        """
        try:
            self.app_logger.info(f"开始AI市场分析，模型: {self.model_id}")

            # 计算并打印token数量
            system_tokens = count_prompt_tokens(system_prompt)
            user_tokens = count_prompt_tokens(user_prompt)
            total_tokens = system_tokens + user_tokens

            print(f"\n🔢 === AI提示词Token统计 ===")
            print(f"📋 系统提示词: {system_tokens:,} tokens")
            print(f"📝 用户提示词: {user_tokens:,} tokens")
            print(f"📊 总计: {total_tokens:,} tokens")
            print(f"💡 模型: {self.model_id}")
            print("=" * 35 + "\n")

            self.app_logger.info(f"提示词Token统计 - 系统: {system_tokens}, 用户: {user_tokens}, 总计: {total_tokens}")

            # 构建请求
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 调用OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=1.0,
                max_tokens=2000,
                timeout=self.timeout,  # 从配置文件读取超时时间
            )

            # 提取响应内容
            content = response.choices[0].message.content

            if not content:
                raise AIClientError("AI返回空响应")

            self.app_logger.info(f"AI响应获取成功，长度: {len(content)} 字符")

            # 尝试解析JSON响应
            try:
                result = json.loads(content)
                self.app_logger.info("AI响应JSON解析成功")
                return result

            except json.JSONDecodeError as e:
                self.error_logger.warning(f"AI响应非JSON格式，尝试提取: {e}")
                # 尝试从文本中提取JSON
                json_content = self._extract_json_from_text(content)
                if json_content:
                    result = json.loads(json_content)
                    self.app_logger.info("AI响应JSON提取成功")
                    return result
                else:
                    raise AIClientError("无法从AI响应中提取有效的JSON")

        except openai.APIError as e:
            error_msg = f"OpenAI API错误: {e}"
            self.error_logger.error(error_msg)
            raise AIClientError(error_msg)

        except openai.RateLimitError as e:
            error_msg = f"OpenAI API频率限制: {e}"
            self.error_logger.error(error_msg)
            raise AIClientError(error_msg)

        except openai.Timeout as e:
            error_msg = f"OpenAI API超时: {e}"
            self.error_logger.error(error_msg)
            raise AIClientError(error_msg)

        except Exception as e:
            log_exception(self.error_logger, "调用AI进行市场分析时发生异常")
            raise AIClientError(f"AI市场分析失败: {e}")

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        从文本中提取JSON片段

        Args:
            text (str): 包含JSON的文本

        Returns:
            Optional[str]: 提取的JSON字符串，失败返回None
        """
        # 方法1: 寻找{ }包围的JSON内容
        start_brace = text.find("{")
        end_brace = text.rfind("}")

        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            json_candidate = text[start_brace : end_brace + 1]

            # 验证是否为有效JSON
            try:
                json.loads(json_candidate)
                return json_candidate
            except json.JSONDecodeError:
                pass  # 继续尝试其他方法

        # 方法2: 寻找```json代码块
        import re

        json_code_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        matches = re.findall(json_code_pattern, text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

        return None


# 全局AI客户端实例
_ai_client: Optional[OpenAIClient] = None


def get_ai_client() -> OpenAIClient:
    """
    获取全局AI客户端实例

    Returns:
        OpenAIClient: AI客户端实例
    """
    global _ai_client

    if _ai_client is None:
        _ai_client = OpenAIClient()

    return _ai_client


def reset_ai_client() -> None:
    """重置AI客户端实例（用于重新加载配置）"""
    global _ai_client
    _ai_client = None
