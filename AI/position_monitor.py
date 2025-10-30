# -*- coding: utf-8 -*-

"""
实时止盈监控模块
该模块独立运行一个线程，实时监控持仓的止盈条件，确保及时平仓
"""

import threading
import time
import MetaTrader5 as mt5
from typing import Dict, Any, Optional
from MT5.order_info import get_active_positions, send_order_request
from utils.logger import get_trading_logger, get_error_logger, log_exception
from config.config_manager import get_config_manager


class TakeProfitMonitor:
    """止盈监控器类"""

    def __init__(self):
        self.logger = get_trading_logger()
        self.error_logger = get_error_logger()
        self.config_manager = get_config_manager()

        # 监控状态
        self.is_running = False
        self.monitor_thread = None

        # 配置参数
        self.monitor_interval = self.config_manager.get("monitoring.interval_seconds", 1)
        self.enabled = self.config_manager.get("monitoring.enabled", True)
        self.cache_ttl = self.config_manager.get("monitoring.price_cache_ttl", 0.5)
        self.startup_notification = self.config_manager.get("monitoring.startup_notification", True)

        # 价格缓存（避免重复请求）
        self.price_cache = {}
        self.last_cache_update = {}

        self.logger.info(f"止盈监控器初始化完成 - 监控间隔: {self.monitor_interval}秒, 缓存TTL: {self.cache_ttl}秒, 启用状态: {self.enabled}")

    def get_active_positions_silent(self) -> Optional[list]:
        """
        静默获取活动持仓（避免日志刷屏）

        Returns:
            Optional[list]: 活动持仓列表，失败返回None
        """
        try:
            magic_number = self.config_manager.get("trading.magic_number", 100001)

            # 检查持仓数量
            positions_count = mt5.positions_total()
            if positions_count is None or positions_count == 0:
                return []

            # 获取所有活动持仓
            positions = mt5.positions_get()
            if positions is None:
                return None

            # 转换为标准格式并过滤
            positions_list = []
            for position in positions:
                if position.magic != magic_number:
                    continue

                # 持仓类型映射
                position_type_map = {
                    mt5.POSITION_TYPE_BUY: "Buy",
                    mt5.POSITION_TYPE_SELL: "Sell",
                }

                position_dict = {
                    "ticket": position.ticket,
                    "symbol": position.symbol,
                    "position_type": position_type_map.get(position.type, f"UNKNOWN({position.type})"),
                    "volume": position.volume,
                    "price_open": position.price_open,
                    "sl": position.sl,
                    "tp": position.tp,
                    "comment": position.comment,
                    "magic": position.magic,
                    "time": position.time,
                    "profit": position.profit,
                }

                positions_list.append(position_dict)

            return positions_list

        except Exception as e:
            self.error_logger.error(f"静默获取持仓时发生异常: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取指定品种的当前价格

        Args:
            symbol: 交易品种名称

        Returns:
            Optional[float]: 当前价格，获取失败返回None
        """
        current_time = time.time()

        # 检查缓存是否有效
        if (symbol in self.price_cache and
            symbol in self.last_cache_update and
            current_time - self.last_cache_update[symbol] < self.cache_ttl):
            return self.price_cache[symbol]

        try:
            # 获取品种报价
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.error_logger.error(f"无法获取品种 {symbol} 的报价信息")
                return None

            # 更新缓存
            self.price_cache[symbol] = tick.bid  # 使用bid价作为基准
            self.last_cache_update[symbol] = current_time

            return tick.bid

        except Exception as e:
            self.error_logger.error(f"获取品种 {symbol} 价格时发生异常: {e}")
            return None

    def check_position_take_profit(self, position: Dict[str, Any]) -> bool:
        """
        检查单个持仓是否达到止盈条件

        Args:
            position: 持仓信息字典

        Returns:
            bool: 是否达到止盈条件
        """
        symbol = position.get('symbol')
        position_type = position.get('position_type')
        tp_price = position.get('tp', 0)

        # 如果没有设置止盈，跳过检查
        if tp_price <= 0:
            return False

        # 获取当前价格
        current_price = self.get_current_price(symbol)
        if current_price is None:
            self.error_logger.error(f"无法获取持仓 {position.get('ticket')} 的当前价格")
            return False

        # 根据持仓类型判断是否触发止盈
        if position_type == "Buy":
            # 买单：当前价格 >= 止盈价格
            if current_price >= tp_price:
                self.logger.info(f"🎯 买单止盈触发: {symbol} 订单{position.get('ticket')} - 当前价格: {current_price:.5f}, 止盈价格: {tp_price:.5f}")
                return True
        elif position_type == "Sell":
            # 卖单：当前价格 <= 止盈价格
            if current_price <= tp_price:
                self.logger.info(f"🎯 卖单止盈触发: {symbol} 订单{position.get('ticket')} - 当前价格: {current_price:.5f}, 止盈价格: {tp_price:.5f}")
                return True

        return False

    def close_position_by_take_profit(self, position: Dict[str, Any]) -> bool:
        """
        因止盈触发而平仓

        Args:
            position: 持仓信息字典

        Returns:
            bool: 平仓是否成功
        """
        try:
            symbol = position.get('symbol')
            ticket = position.get('ticket')
            volume = position.get('volume')
            position_type = position.get('position_type')

            self.logger.info(f"🚀 开始止盈平仓: {symbol} 订单{ticket} 数量{volume}")

            # 获取当前报价
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.error_logger.error(f"无法获取 {symbol} 的当前报价，平仓失败")
                return False

            # 确定平仓方向和价格
            if position_type == "Buy":
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid  # 买单平仓使用bid价
            else:  # Sell
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask  # 卖单平仓使用ask价

            # 构建平仓请求
            close_request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': order_type,
                'price': price,
                'position': ticket,
                'deviation': 10,
                'type_filling': mt5.ORDER_FILLING_IOC,
                'type_time': mt5.ORDER_TIME_GTC,
                'original_comment': f"监控止盈自动平仓 {symbol} 订单{ticket}"
            }

            # 发送平仓请求
            result = send_order_request(close_request)

            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ 止盈平仓成功: {symbol} 订单{ticket} - 成交价格: {price}")
                return True
            else:
                error_msg = result.get('comment', '未知错误') if result else '平仓请求失败'
                self.error_logger.error(f"❌ 止盈平仓失败: {symbol} 订单{ticket}, 原因: {error_msg}")
                return False

        except Exception as e:
            self.error_logger.error(f"止盈平仓异常: {position.get('symbol')} 订单{position.get('ticket')}, 错误: {e}")
            return False

    def monitor_loop(self):
        """监控主循环"""
        self.logger.info("🔄 止盈监控线程启动")

        while self.is_running:
            try:
                # 检查监控是否启用
                if not self.enabled:
                    time.sleep(self.monitor_interval)
                    continue

                # 获取所有活动持仓（使用静默方法避免日志刷屏）
                positions = self.get_active_positions_silent()
                if positions is None:
                    self.error_logger.error("获取持仓信息失败，跳过本轮监控")
                    time.sleep(self.monitor_interval)
                    continue

                if not positions:
                    # 没有持仓时，清空价格缓存
                    self.price_cache.clear()
                    self.last_cache_update.clear()
                    time.sleep(self.monitor_interval)
                    continue

                # 监控每个持仓的止盈条件
                closed_positions = 0
                for position in positions:
                    if self.check_position_take_profit(position):
                        if self.close_position_by_take_profit(position):
                            closed_positions += 1

                # 如果有平仓操作，记录日志并稍作等待避免重复操作
                if closed_positions > 0:
                    self.logger.info(f"本轮监控完成: 检查了 {len(positions)} 个持仓，执行了 {closed_positions} 个止盈平仓")
                    time.sleep(2)  # 平仓后稍作等待
                else:
                    # 静默运行，避免日志刷屏
                    time.sleep(self.monitor_interval)

            except Exception as e:
                self.error_logger.error(f"监控循环发生异常: {e}")
                log_exception(self.error_logger, "止盈监控循环异常")
                # 异常时等待较长时间再继续
                time.sleep(5)

        self.logger.info("🔄 止盈监控线程停止")

    def start(self):
        """启动监控"""
        if self.is_running:
            self.logger.warning("止盈监控已在运行中")
            return False

        if not self.enabled:
            self.logger.info("止盈监控功能已禁用，跳过启动")
            return False

        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("🚀 止盈监控已启动")
        return True

    def stop(self):
        """停止监控"""
        if not self.is_running:
            self.logger.warning("止盈监控未在运行")
            return False

        self.is_running = False

        # 等待线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        self.logger.info("🛑 止盈监控已停止")
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        获取监控状态信息

        Returns:
            Dict[str, Any]: 监控状态
        """
        return {
            'is_running': self.is_running,
            'enabled': self.enabled,
            'monitor_interval': self.monitor_interval,
            'cached_symbols': len(self.price_cache),
            'thread_alive': self.monitor_thread.is_alive() if self.monitor_thread else False
        }


# 全局监控器实例
_monitor_instance = None


def get_take_profit_monitor() -> TakeProfitMonitor:
    """
    获取全局止盈监控器实例

    Returns:
        TakeProfitMonitor: 监控器实例
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = TakeProfitMonitor()
    return _monitor_instance


def start_take_profit_monitoring():
    """启动止盈监控"""
    monitor = get_take_profit_monitor()
    return monitor.start()


def stop_take_profit_monitoring():
    """停止止盈监控"""
    monitor = get_take_profit_monitor()
    return monitor.stop()


def get_monitoring_status() -> Dict[str, Any]:
    """获取监控状态"""
    monitor = get_take_profit_monitor()
    return monitor.get_status()