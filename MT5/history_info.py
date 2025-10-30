"""
历史订单信息相关函数
获取历史交易记录并关联AI决策结果，用于AI学习和改进
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import MetaTrader5 as mt5

from config.config_manager import get_config_manager
from utils.database import get_order_comment
from utils.logger import get_trading_logger, get_error_logger, log_exception


def get_history_orders(
    days_back: int = 7,
    magic_number: Optional[int] = None,
    include_closed: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """
    获取历史订单信息，包括AI决策和最终盈亏结果

    Args:
        days_back (int): 获取多少天前的历史记录，默认7天
        magic_number (Optional[int]): 魔法数字，如果指定则只返回匹配的订单
        include_closed (bool): 是否包含已平仓的订单

    Returns:
        Optional[List[Dict[str, Any]]]: 历史订单信息列表，每个订单包含：
            - ticket: 订单号
            - symbol: 交易品种
            - type: 订单类型
            - volume: 交易量
            - price_open: 开仓价格
            - price_close: 平仓价格
            - profit: 最终盈亏
            - commission: 手续费
            - swap: 库存费
            - time_setup: 订单创建时间
            - time_done: 订单完成时间
            - comment: 完整的AI决策注释（从数据库获取）
            - duration_minutes: 持仓时间（分钟）
            - profit_pips: 盈亏点数
            - outcome: 交易结果（盈利/亏损）
    """

    logger = get_trading_logger()
    error_logger = get_error_logger()

    # 如果未指定魔法数字，则从配置文件获取
    if magic_number is None:
        config_manager = get_config_manager()
        magic_number = config_manager.get("trading.magic_number", 100001)

    try:
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        logger.info(f"获取历史订单：{start_time} 到 {end_time}")

        # 获取历史交易（deals）
        if include_closed:
            # 使用MT5标准方式获取历史交易
            history_deals = mt5.history_deals_get(start_time, end_time)
        else:
            history_deals = []

        if history_deals is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取历史交��失败，错误代码 = {error_code}")
            return None

        logger.info(f"获取到 {len(history_deals)} 条历史交易记录")

        # 转换为标准字典格式
        history_orders = []

        for deal in history_deals:
            # 根据魔法数字过滤
            if magic_number != -1 and deal.magic != magic_number:
                continue

            # 只处理入场的交易（entry=0），忽略平仓交易（entry=1）
            if deal.entry != 0:
                continue

            # 查找对应的平仓交易
            close_deal = _find_close_deal(deal, history_deals)

            # 从数据库获取AI决策注释
            ai_comment = get_order_comment(deal.order)

            # 计算持仓时间和盈亏点数
            duration_minutes = 0
            profit_pips = 0

            if close_deal:
                duration_minutes = (close_deal.time - deal.time) // 60
                profit_pips = _calculate_profit_pips(deal, close_deal)

            # 确定交易结果
            outcome = "盈利" if deal.profit > 0 else "亏损" if deal.profit < 0 else "持平"

            order_dict = {
                "ticket": deal.order,
                "symbol": deal.symbol,
                "type": _get_deal_type_name(deal.type),
                "volume": deal.volume,
                "price_open": deal.price,
                "price_close": close_deal.price if close_deal else None,
                "profit": deal.profit,
                "commission": deal.commission,
                "swap": deal.swap,
                "time_setup": deal.time,
                "time_done": close_deal.time if close_deal else deal.time,
                "comment": ai_comment if ai_comment else deal.comment,
                "duration_minutes": duration_minutes,
                "profit_pips": profit_pips,
                "outcome": outcome,
                "entry_time_str": datetime.fromtimestamp(deal.time).strftime('%Y-%m-%d %H:%M:%S'),
                "exit_time_str": datetime.fromtimestamp(close_deal.time).strftime('%Y-%m-%d %H:%M:%S') if close_deal else None
            }

            history_orders.append(order_dict)

        # 按时间倒序排列（最新的在前）
        history_orders.sort(key=lambda x: x['time_setup'], reverse=True)

        logger.info(f"成功处理 {len(history_orders)} 个历史订单")
        return history_orders

    except Exception as e:
        log_exception(error_logger, "获取历史订单时发生异常")
        return None


def _find_close_deal(entry_deal, all_deals) -> Optional[Any]:
    """
    查找与入场交易对应的平仓交易

    Args:
        entry_deal: 入场交易
        all_deals: 所有交易列表

    Returns:
        Optional[Any]: 平仓交易，如果未找到则返回None
    """
    for deal in all_deals:
        # 查找同一订单的平仓交易（entry=1）
        if (deal.order == entry_deal.order and
            deal.entry == 1 and
            deal.time > entry_deal.time):
            return deal
    return None


def _calculate_profit_pips(entry_deal, close_deal) -> float:
    """
    计算盈亏点数

    Args:
        entry_deal: 入场交易
        close_deal: 平仓交易

    Returns:
        float: 盈亏点数
    """
    try:
        if entry_deal.type == mt5.DEAL_TYPE_BUY:
            # 买入：平仓价 - 开仓价
            pips = (close_deal.price - entry_deal.price)
        else:
            # 卖出：开仓价 - 平仓价
            pips = (entry_deal.price - close_deal.price)

        # 转换为点数（考虑小数位数）
        symbol_info = mt5.symbol_info(entry_deal.symbol)
        if symbol_info:
            point = symbol_info.point
            return round(pips / point, 1)
        else:
            return round(pips, 5)

    except Exception:
        return 0.0


def _get_deal_type_name(deal_type: int) -> str:
    """
    获取交易类型名称

    Args:
        deal_type: MT5交易类型代码

    Returns:
        str: 交易类型名称
    """
    type_map = {
        mt5.DEAL_TYPE_BUY: "买入",
        mt5.DEAL_TYPE_SELL: "卖出",
        mt5.DEAL_TYPE_BALANCE: "余额",
        mt5.DEAL_TYPE_CREDIT: "信用",
        mt5.DEAL_TYPE_CHARGE: "费用",
        mt5.DEAL_TYPE_CORRECTION: "更正",
        mt5.DEAL_TYPE_BONUS: "奖金",
        mt5.DEAL_TYPE_COMMISSION: "佣金",
        mt5.DEAL_TYPE_COMMISSION_DAILY: "每日佣金",
        mt5.DEAL_TYPE_COMMISSION_MONTHLY: "每月佣金",
        mt5.DEAL_TYPE_COMMISSION_AGENT_DAILY: "代理每日佣金",
        mt5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY: "代理每月佣金",
        mt5.DEAL_TYPE_INTEREST: "利息",
        mt5.DEAL_TYPE_BUY_CANCELED: "已取消买入",
        mt5.DEAL_TYPE_SELL_CANCELED: "已取消卖出",
        mt5.DEAL_DIVIDEND: "股息",
        mt5.DEAL_DIVIDEND_FRANKED: "股息税抵免",
        mt5.DEAL_TAX: "税款"
    }
    return type_map.get(deal_type, f"未知类型({deal_type})")


def get_daily_statistics(days_back: int = 7) -> Optional[Dict[str, Any]]:
    """
    获取交易统计数据

    Args:
        days_back (int): 统计天数

    Returns:
        Optional[Dict[str, Any]]: 统计数据字典，包含：
            - total_trades: 总交易次数
            - profitable_trades: 盈利交易次数
            - losing_trades: 亏损交易次数
            - win_rate: 胜率（百分比）
            - total_profit: 总盈利
            - total_loss: 总亏损
            - net_profit: 净盈利
            - average_profit: 平均盈利
            - average_loss: 平均亏损
            - profit_factor: 盈利因子
            - best_trade: 最佳交易
            - worst_trade: 最差交易
            - average_duration: 平均持仓时间（分钟）
    """

    history_orders = get_history_orders(days_back=days_back)

    if not history_orders:
        return None

    # 过滤掉余额调整等非交易记录
    trades = [order for order in history_orders if order['type'] in ['买入', '卖出']]

    if not trades:
        return None

    profitable_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] < 0]

    total_profit = sum(t['profit'] for t in profitable_trades) if profitable_trades else 0
    total_loss = abs(sum(t['profit'] for t in losing_trades)) if losing_trades else 0

    stats = {
        'total_trades': len(trades),
        'profitable_trades': len(profitable_trades),
        'losing_trades': len(losing_trades),
        'win_rate': round(len(profitable_trades) / len(trades) * 100, 2) if trades else 0,
        'total_profit': total_profit,
        'total_loss': total_loss,
        'net_profit': total_profit - total_loss,
        'average_profit': total_profit / len(profitable_trades) if profitable_trades else 0,
        'average_loss': total_loss / len(losing_trades) if losing_trades else 0,
        'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
        'best_trade': max(trades, key=lambda x: x['profit']) if trades else None,
        'worst_trade': min(trades, key=lambda x: x['profit']) if trades else None,
        'average_duration': sum(t['duration_minutes'] for t in trades) / len(trades) if trades else 0
    }

    return stats


def format_history_for_prompt(history_orders: List[Dict[str, Any]], max_orders: int = 10) -> str:
    """
    将历史订单格式化为适合AI提示词的文本

    Args:
        history_orders: 历史订单列表
        max_orders: 最大显示订单数量

    Returns:
        str: 格式化的历史订单文本
    """
    if not history_orders:
        return "- 无历史交易记录"

    # 限制显示数量
    display_orders = history_orders[:max_orders]

    # 智能标题：如果显示全部，就显示"全部"，否则显示数量
    if len(display_orders) == len(history_orders):
        title_text = f"## 最近交易记录（全部{len(history_orders)}条）"
    else:
        title_text = f"## 最近交易记录（显示最新{len(display_orders)}条，共{len(history_orders)}条）"

    # 添加交易统计信息
    profitable_count = sum(1 for order in history_orders if order['profit'] > 0)
    losing_count = sum(1 for order in history_orders if order['profit'] < 0)
    total_profit = sum(order['profit'] for order in history_orders)

    formatted_text = f"{title_text}\n"
    formatted_text += f"- **今日统计**: {profitable_count}笔盈利 / {losing_count}笔亏损 / 净盈亏:{total_profit:.2f}\n\n"

    for i, order in enumerate(display_orders, 1):
        # 格式化盈亏
        if order['profit'] > 0:
            profit_color = "[盈利]"
        elif order['profit'] < 0:
            profit_color = "[亏损]"
        else:
            profit_color = "[持平]"
        profit_text = f"{profit_color} {order['profit']:.2f}"

        # 格式化持仓时间
        if order['duration_minutes'] < 60:
            duration_text = f"{order['duration_minutes']}分钟"
        else:
            hours = order['duration_minutes'] // 60
            minutes = order['duration_minutes'] % 60
            duration_text = f"{hours}小时{minutes}分钟"

        # 格式化价格信息
        price_info = f"开仓:{order['price_open']:.5f}"
        if order['price_close']:
            price_info += f" → 平仓:{order['price_close']:.5f}"

        formatted_text += f"""**{i}. {order['symbol']} - {order['type']}**
- 订单号: {order['ticket']}
- 时间: {order['entry_time_str']} (持仓{duration_text})
- 价格: {price_info}
- 盈亏: {profit_text} ({order['outcome']}, {order['profit_pips']}点)
- 手数: {order['volume']}
- AI决策: {order['comment'][:100]}{'...' if len(order['comment']) > 100 else ''}

"""

    return formatted_text