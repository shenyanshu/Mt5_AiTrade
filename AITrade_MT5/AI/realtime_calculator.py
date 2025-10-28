# -*- coding: utf-8 -*-

"""
简化的实时价格计算器
基于AI的相对价格策略，计算具体的交易参数
"""

import MetaTrader5 as mt5
from utils.logger import get_trading_logger


def calculate_simple_prices(symbol: str, action: str, volume: float,
                           entry_offset_points: float = 0,
                           stop_loss_points: float = 0,
                           take_profit_points: float = 0) -> dict:
    """
    计算简化的交易价格

    Args:
        symbol: 交易品种
        action: 交易动作 (BUY/SELL)
        volume: 交易量
        entry_offset_points: 入场价格偏移点数
        stop_loss_points: 止损点数
        take_profit_points: 止盈点数

    Returns:
        dict: 计算结果
    """
    logger = get_trading_logger()

    try:
        # 获取当前价格
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {
                'success': False,
                'error': f"无法获取 {symbol} 的价格信息"
            }

        # 获取品种信息
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return {
                'success': False,
                'error': f"无法获取 {symbol} 的品种信息"
            }

        point_value = symbol_info.point
        digits = symbol_info.digits

        # 计算入场价格
        if action == "BUY":
            current_price = tick.ask
        else:  # SELL
            current_price = tick.bid

        # 应用入场偏移
        if entry_offset_points != 0:
            entry_price = current_price + (entry_offset_points * point_value)
        else:
            entry_price = current_price

        # 获取关键的交易参数
        spread_points = symbol_info.spread  # MT5直接提供点差（点数）
        min_stops_level = symbol_info.trade_stops_level  # MT5最小止损距离要求
        safety_buffer = 5  # 额外安全缓冲（点数）

        # 计算最小有效距离（考虑点差和MT5要求）
        min_effective_distance = max(min_stops_level, spread_points + safety_buffer)

        logger.debug(f"{symbol} 交易参数: 点差={spread_points}点, 最小止损距离={min_stops_level}点, 有效最小距离={min_effective_distance}点")

        # 计算止损止盈价格
        if action == "BUY":
            if stop_loss_points > 0:
                # 确保止损距离至少满足最小有效距离
                effective_stop_points = max(stop_loss_points, min_effective_distance)
                stop_loss = entry_price - (effective_stop_points * point_value)

                # 额外检查：确保止损不会设置在当前bid价格之上（对于买单）
                if stop_loss >= tick.bid:
                    stop_loss = tick.bid - (min_effective_distance * point_value)

                logger.debug(f"{symbol} BUY止损调整: 请求{stop_loss_points}点 -> 实际{effective_stop_points}点")
            else:
                stop_loss = 0

            if take_profit_points > 0:
                # 确保止盈距离至少覆盖点差成本 + 合理利润
                min_profit_points = spread_points + safety_buffer
                effective_profit_points = max(take_profit_points, min_profit_points)
                take_profit = entry_price + (effective_profit_points * point_value)

                logger.debug(f"{symbol} BUY止盈调整: 请求{take_profit_points}点 -> 实际{effective_profit_points}点")
            else:
                take_profit = 0

        else:  # SELL
            if stop_loss_points > 0:
                # 确保止损距离至少满足最小有效距离
                effective_stop_points = max(stop_loss_points, min_effective_distance)
                stop_loss = entry_price + (effective_stop_points * point_value)

                # 额外检查：确保止损不会设置在当前ask价格之下（对于卖单）
                if stop_loss <= tick.ask:
                    stop_loss = tick.ask + (min_effective_distance * point_value)

                logger.debug(f"{symbol} SELL止损调整: 请求{stop_loss_points}点 -> 实际{effective_stop_points}点")
            else:
                stop_loss = 0

            if take_profit_points > 0:
                # 确保止盈距离至少覆盖点差成本 + 合理利润
                min_profit_points = spread_points + safety_buffer
                effective_profit_points = max(take_profit_points, min_profit_points)
                take_profit = entry_price - (effective_profit_points * point_value)

                logger.debug(f"{symbol} SELL止盈调整: 请求{take_profit_points}点 -> 实际{effective_profit_points}点")
            else:
                take_profit = 0

        # 格式化价格到正确的精度
        def format_price(price):
            if price <= 0:
                return 0
            return round(price, digits)

        entry_price = format_price(entry_price)
        stop_loss = format_price(stop_loss)
        take_profit = format_price(take_profit)
        current_price = format_price(current_price)

        result = {
            'success': True,
            'symbol': symbol,
            'action': action,
            'volume': volume,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'current_price': current_price,
            'spread_points': spread_points,
            'min_stops_level': min_stops_level,
            'min_effective_distance': min_effective_distance
        }

        # 验证止损止盈距离
        if stop_loss > 0:
            stop_distance = abs(entry_price - stop_loss) / point_value
            logger.debug(f"{symbol} 最终止损距离: {stop_distance:.1f} 点 (点差: {spread_points}点, 有效最小距离: {min_effective_distance}点)")

        if take_profit > 0:
            profit_distance = abs(take_profit - entry_price) / point_value
            profit_margin = profit_distance - spread_points  # 净利润空间
            logger.debug(f"{symbol} 最终止盈距离: {profit_distance:.1f} 点 (净利润空间: {profit_margin:.1f}点)")

        logger.debug(f"{symbol} 价格计算完成: 入场={entry_price:.5f}, 止损={stop_loss:.5f}, 止盈={take_profit:.5f}, 点差={spread_points}点")
        return result

    except Exception as e:
        logger.error(f"价格计算失败: {symbol} {action}, 错误: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_current_price(symbol: str, price_type: str = "mid") -> float:
    """
    获取当前价格

    Args:
        symbol: 交易品种
        price_type: 价格类型 (bid/ask/mid)

    Returns:
        float: 当前价格，失败返回0
    """
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return 0

        if price_type == "bid":
            return tick.bid
        elif price_type == "ask":
            return tick.ask
        else:  # mid
            return (tick.bid + tick.ask) / 2

    except Exception:
        return 0


def calculate_profit_loss_price(symbol: str, action: str, entry_price: float,
                                points: float, is_profit: bool = True) -> float:
    """
    计算盈利或亏损价格

    Args:
        symbol: 交易品种
        action: 交易动作 (BUY/SELL)
        entry_price: 入场价格
        points: 点数
        is_profit: 是否为盈利计算

    Returns:
        float: 计算后的价格
    """
    try:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return entry_price

        point_value = symbol_info.point
        price_offset = points * point_value

        if action == "BUY":
            if is_profit:
                return entry_price + price_offset  # 止盈：价格上涨
            else:
                return entry_price - price_offset  # 止损：价格下跌
        else:  # SELL
            if is_profit:
                return entry_price - price_offset  # 止盈：价格下跌
            else:
                return entry_price + price_offset  # 止损：价格上涨

    except Exception:
        return entry_price