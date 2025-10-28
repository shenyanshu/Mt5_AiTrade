"""
订单信息相关函数
此文件将包含获取订单信息、管理订单等功能
"""

from typing import List, Optional, Dict, Any

import MetaTrader5 as mt5

from config.config_manager import get_config_manager
from utils.database import get_order_comment
from utils.logger import get_trading_logger, get_error_logger, log_exception


def get_active_positions(
    magic_number: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    获取当前所有活动持仓订单的信息
    活动持仓指的是当前已成交但尚未平仓的订单，即当前持有的头寸。
    Args:
        magic_number (Optional[int]): 魔法数字，如果指定则只返回匹配的持仓
    Returns:
        Optional[List[Dict[str, Any]]]: 活动持仓信息列表，每个持仓包含详细信息字典。
                                       如果获取失败则返回None。
        每个持仓字典包含以下键:
        - ticket: 订单号 (int)
        - symbol: 交易品种 (str)
        - position_type: 持仓类型 (str) - "BUY" 或 "SELL"
        - volume: 持仓量 (float)
        - price_open: 开仓价格 (float)
        - sl: 止损价格 (float)
        - tp: 止盈价格 (float)
        - comment: 持仓注释 (str) - 完整注释（从数据库获取）
        - magic: 魔法数字 (int)
        - time: 开仓时间 (int)
        - profit: 当前利润 (float)
    """

    logger = get_trading_logger()

    error_logger = get_error_logger()

    # 如果未指定魔法数字，则从配置文件获取
    # 如果魔法数字为 -1，则表示获取所有订单（不进行魔法数字过滤）

    if magic_number is None:
        config_manager = get_config_manager()

        magic_number = config_manager.get("trading.magic_number", 100001)

    try:
        # 首先检查持仓数量，如果为0则直接返回空列表

        positions_count = mt5.positions_total()

        if positions_count is None:
            error_code = mt5.last_error()

            error_logger.error(f"获取持仓总数失败, 错误代码 = {error_code}")

            return None

        if positions_count == 0:
            logger.info("当前无活动持仓")

            return []

        # 获取所有活动持仓

        positions = mt5.positions_get()

        if positions is None:
            error_code = mt5.last_error()

            error_logger.error(f"获取活动持仓失败, 错误代码 = {error_code}")

            return None

        # 转换为标准字典格式，并用数据库中的完整注释替换MT5的截断注释

        positions_list = []

        for position in positions:
            # 如果指定了魔法数字且不是-1，则只添加匹配的持仓

            if magic_number != -1 and position.magic != magic_number:
                continue

            # 从数据库获取完整注释

            full_comment = get_order_comment(position.ticket)

            # 持仓类型映射

            position_type_map = {
                mt5.POSITION_TYPE_BUY: "Buy",
                mt5.POSITION_TYPE_SELL: "Sell",
            }

            position_dict = {
                "ticket": position.ticket,
                "symbol": position.symbol,
                "position_type": position_type_map.get(
                    position.type, f"UNKNOWN({position.type})"
                ),
                "volume": position.volume,
                "price_open": position.price_open,
                "sl": position.sl,
                "tp": position.tp,
                "comment": (
                    full_comment if full_comment is not None else position.comment
                ),
                "magic": position.magic,
                "time": position.time,
                "profit": position.profit,
            }

            positions_list.append(position_dict)

        logger.info(f"成功获取 {len(positions_list)} 个活动持仓")

        return positions_list

    except Exception as e:
        log_exception(error_logger, "获取活动持仓列表时发生异常")

        return None


def get_pending_orders(
    magic_number: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    获取当前所有活动挂单订单的信息
    活动挂单指的是当前尚未成交的限价单、止损单等订单。
    Args:
        magic_number (Optional[int]): 魔法数字，如果指定则只返回匹配的挂单
    Returns:
        Optional[List[Dict[str, Any]]]: 活动挂单信息列表，每个挂单包含详细信息字典。
                                       如果获取失败则返回None。
        每个挂单字典包含以下键:
        - ticket: 订单号 (int)
        - symbol: 交易品种 (str)
        - order_type: 订单类型 (str) - "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"等
        - volume: 订单量 (float)
        - price_open: 开仓价格 (float)
        - sl: 歌手止损价格 (float)
        - tp: 止盈价格 (float)
        - expiration: 过期时间 (int)
        - comment: 订单注释 (str) - 完整注释（从数据库获取）
        - magic: 魔法数字 (int)
        - time_setup: 订单设置时间 (int)
    """

    logger = get_trading_logger()

    error_logger = get_error_logger()

    # 如果未指定魔法数字，则从配置文件获取
    # 如果魔法数字为 -1，则表示获取所有订单（不进行魔法数字过滤）

    if magic_number is None:
        config_manager = get_config_manager()

        magic_number = config_manager.get("trading.magic_number", 100001)

    try:
        # 首先检查挂单数量，如果为0则直接返回空列表

        orders_count = mt5.orders_total()

        if orders_count is None:
            error_code = mt5.last_error()

            error_logger.error(f"获取挂单总数失败, 错误代码 = {error_code}")

            return None

        if orders_count == 0:
            logger.info("当前无活动挂单")

            return []

        # 获取所有活动订单

        orders = mt5.orders_get()

        if orders is None:
            error_code = mt5.last_error()

            error_logger.error(f"获取活动挂单失败, 错误代码 = {error_code}")

            return None

        # 转换为标准字典格式，并用数据库中的完整注释替换MT5的截断注释

        orders_list = []

        for order in orders:
            # 如果指定了魔法数字且不是-1，则只添加匹配的挂单

            if magic_number != -1 and order.magic != magic_number:
                continue

            # 从数据库获取完整注释

            full_comment = get_order_comment(order.ticket)

            # 订单类型映射

            order_type_map = {
                mt5.ORDER_TYPE_BUY: "Buy",
                mt5.ORDER_TYPE_SELL: "Sell",
                mt5.ORDER_TYPE_BUY_LIMIT: "Buy Limit",
                mt5.ORDER_TYPE_SELL_LIMIT: "Sell Limit",
                mt5.ORDER_TYPE_BUY_STOP: "Buy Stop",
                mt5.ORDER_TYPE_SELL_STOP: "Sell Stop",
                mt5.ORDER_TYPE_BUY_STOP_LIMIT: "Buy Stop Limit",
                mt5.ORDER_TYPE_SELL_STOP_LIMIT: "Sell Stop Limit",
                mt5.ORDER_TYPE_CLOSE_BY: "Close By",
            }

            order_dict = {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "order_type": order_type_map.get(order.type, f"UNKNOWN({order.type})"),
                "volume": order.volume_initial,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "expiration": order.time_expiration,
                "comment": full_comment if full_comment is not None else order.comment,
                "magic": order.magic,
                "time_setup": order.time_setup,
            }

            orders_list.append(order_dict)

        logger.info(f"成功获取 {len(orders_list)} 个活动挂单")

        return orders_list

    except Exception as e:
        log_exception(error_logger, "获取活动挂单订单列表时发生异常")

        return None


def send_order_request(
    request: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    发送订单请求到MT5平台

    该函数接受符合MT5 MqlTradeRequest结构的字典参数，与MT5的order_send() API保持一致。

    Args:
        request (Dict[str, Any]): MT5交易请求字典，包含以下常用字段：
            - action: 交易操作类型 (MT5.TRADE_ACTION_*)
            - symbol: 交易品种名称
            - volume: 交易量
            - type: 订单类型 (MT5.ORDER_TYPE_*)
            - price: 价格
            - sl: 止损价格 (可选)
            - tp: 止盈价格 (可选)
            - order: 订单编号 (用于取消/修改订单)
            - position: 持仓编号 (用于平仓)
            - deviation: 价格偏差 (默认10)
            - magic: 魔法数字 (可选，默认从配置获取)
            - comment: 订单注释 (可选)
            - expiration: 过期时间 (可选)
            - type_time: 订单时间类型 (可选)
            - type_filling: 成交模式 (可选)
            - 其他MT5支持的参数...

    Returns:
        Optional[Dict[str, Any]]: 订单发送结果，包含订单号等信息。如果发送失败则返回None。
    """

    logger = get_trading_logger()

    error_logger = get_error_logger()

    # 提取请求参数
    action = request.get('action')
    symbol = request.get('symbol')
    volume = request.get('volume', 0)
    price = request.get('price', 0)
    order_type = request.get('type')
    magic = request.get('magic')
    comment = request.get('comment', '')

    # 基本参数验证
    if action is None:
        error_logger.error("缺少必需参数: action")
        return None

    if symbol is None:
        error_logger.error("缺少必需参数: symbol")
        return None

    # 对于需要交易量的操作进行验证
    if action in [mt5.TRADE_ACTION_DEAL, mt5.TRADE_ACTION_PENDING]:
        if volume <= 0:
            error_logger.error("交易量必须大于0")
            return None

    # 对于需要价格的操作进行验证
    if action in [mt5.TRADE_ACTION_DEAL, mt5.TRADE_ACTION_PENDING]:
        if price <= 0:
            error_logger.error("价格必须大于0")
            return None

    # 如果未指定魔法数字，则从配置文件获取
    if magic is None:
        config_manager = get_config_manager()
        magic = config_manager.get("trading.magic_number", 100001)
        request['magic'] = magic

    # 验证订单类型与交易操作的匹配性（仅对需要order_type的操作）
    if action in [mt5.TRADE_ACTION_DEAL, mt5.TRADE_ACTION_PENDING]:
        if order_type is None:
            error_logger.error(f"交易操作 {action} 需要指定订单类型 (type)")
            return None

        if action == mt5.TRADE_ACTION_DEAL:
            if order_type not in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL):
                error_logger.error("TRADE_ACTION_DEAL操作必须使用BUY或SELL订单类型")
                return None
        elif action == mt5.TRADE_ACTION_PENDING:
            if order_type not in (
                mt5.ORDER_TYPE_BUY_LIMIT,
                mt5.ORDER_TYPE_SELL_LIMIT,
                mt5.ORDER_TYPE_BUY_STOP,
                mt5.ORDER_TYPE_SELL_STOP,
                mt5.ORDER_TYPE_BUY_STOP_LIMIT,
                mt5.ORDER_TYPE_SELL_STOP_LIMIT,
            ):
                error_logger.error("TRADE_ACTION_PENDING操作必须使用挂单类型")
                return None

    # 检查交易品种是否存在（对需要symbol的操作）
    if action != mt5.TRADE_ACTION_REMOVE:  # 取消订单操作不需要检查品种
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            error_logger.error(f"交易品种 {symbol} 不存在，无法发送订单")
            return None

        # 如果市场报价中没有此交易品种，则添加
        if not symbol_info.visible:
            logger.info(f"交易品种 {symbol} 不可见，尝试切换为可见")
            if not mt5.symbol_select(symbol, True):
                error_logger.error(f"无法将交易品种 {symbol} 设为可见")
                return None

    # 检查并截断注释，MT5平台限制注释最大长度为32个字符
    # 如果没有comment字段，跳过注释处理，避免MT5库验证错误
    if comment is not None and len(comment) > 0:
        # 过滤特殊字符，只保留ASCII可打印字符
        import re
        cleaned_comment = re.sub(r'[^\x20-\x7E]', '', str(comment))
        mt5_comment = cleaned_comment[:32] if len(cleaned_comment) > 32 else cleaned_comment
        logger.debug(f"注释处理: 原始='{comment}' -> 清理后='{mt5_comment}' (长度={len(mt5_comment)})")
        # 更新请求中的注释为处理后的版本
        request['comment'] = mt5_comment
    else:
        # 如果没有comment字段，从request中移除以避免MT5库验证错误
        if 'comment' in request:
            del request['comment']
        logger.debug(f"无comment字段，跳过注释处理")

    # 设置默认参数
    if 'deviation' not in request:
        request['deviation'] = 10
    if 'type_time' not in request:
        request['type_time'] = mt5.ORDER_TIME_GTC
    if 'type_filling' not in request:
        request['type_filling'] = mt5.ORDER_FILLING_IOC

    # 构建最终的MT5请求字典，移除不必要的参数
    # 不包含comment字段，避免MT5库验证错误
    mt5_request = {}
    valid_keys = [
        'action', 'symbol', 'volume', 'type', 'price', 'sl', 'tp',
        'deviation', 'magic', 'expiration', 'position',
        'position_by', 'type_time', 'type_filling', 'stoplimit', 'order'
        # 移除'comment'字段，避免MT5库验证错误
    ]

    for key in valid_keys:
        if key in request:
            mt5_request[key] = request[key]

    try:
        # 发送订单请求到MT5平台
        result = mt5.order_send(mt5_request)

        # 检查订单发送结果
        if result is None:
            error_code = mt5.last_error()
            error_logger.error(f"发送订单请求失败，错误代码 = {error_code}")
            return None

        # 将结果转换为字典格式
        result_dict = {
            "retcode": result.retcode,
            "deal": result.deal,
            "order": result.order,
            "volume": result.volume,
            "price": result.price,
            "bid": result.bid,
            "ask": result.ask,
            "comment": result.comment,
            "request_id": result.request_id,
            "retcode_external": result.retcode_external,
        }

        # 检查返回码，记录详细日志
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            # 获取错误码描述
            retcode_descriptions = {
                mt5.TRADE_RETCODE_DONE: "请求完全处理",
                mt5.TRADE_RETCODE_INVALID: "交易参数错误",
                mt5.TRADE_RETCODE_INVALID_VOLUME: "交易量错误",
                mt5.TRADE_RETCODE_INVALID_PRICE: "价格错误",
                mt5.TRADE_RETCODE_INVALID_STOPS: "止损止盈错误",
                mt5.TRADE_RETCODE_TRADE_DISABLED: "交易禁用",
                mt5.TRADE_RETCODE_MARKET_CLOSED: "市场收盘",
                mt5.TRADE_RETCODE_NO_MONEY: "资金不足",
                mt5.TRADE_RETCODE_PRICE_CHANGED: "价格变动",
                mt5.TRADE_RETCODE_PRICE_OFF: "报价偏离",
                mt5.TRADE_RETCODE_TOO_MANY_REQUESTS: "请求过于频繁",
                mt5.TRADE_RETCODE_REQUOTE: "重新报价",
                mt5.TRADE_RETCODE_ORDER_CHANGED: "订单已更改",
                mt5.TRADE_RETCODE_NO_CHANGES: "无变更",
                mt5.TRADE_RETCODE_SERVER_DISABLES_AT: "自动交易在服务器端禁用",
                mt5.TRADE_RETCODE_CLIENT_DISABLES_AT: "自动交易在客户端禁用",
                mt5.TRADE_RETCODE_LOCKED: "请求锁定",
                mt5.TRADE_RETCODE_FROZEN: "订单或持仓冻结",
                mt5.TRADE_RETCODE_INVALID_FILL: "成交模式不支持",
                mt5.TRADE_RETCODE_CONNECTION: "与交易服务器无连接",
                mt5.TRADE_RETCODE_TIMEOUT: "操作超时",
                mt5.TRADE_RETCODE_CANCEL: "已取消",
            }

            error_description = retcode_descriptions.get(result.retcode, "未知错误")

            # 对于10011错误，进行更详细的分析
            if result.retcode == 10011:
                logger.error(f"🔍 === 10011错误详细分析 ===")
                logger.error(f"请求参数: {json.dumps(mt5_request, ensure_ascii=False, indent=2)}")

                # 检查各种可能的问题
                if price <= 0:
                    logger.error(f"❌ 价格问题: price={price}")
                if volume <= 0:
                    logger.error(f"❌ 交易量问题: volume={volume}")

                # 检查品种信息
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    logger.error(f"品种信息: {symbol}")
                    logger.error(f"交易模式: {symbol_info.trade_mode}")
                    logger.error(f"最小交易量: {symbol_info.volume_min}")
                    logger.error(f"最大交易量: {symbol_info.volume_max}")
                    logger.error(f"交易量步长: {symbol_info.volume_step}")

                    # 检查交易量是否符合要求
                    if volume < symbol_info.volume_min:
                        logger.error(f"❌ 交易量过小: {volume} < {symbol_info.volume_min}")
                    if volume > symbol_info.volume_max:
                        logger.error(f"❌ 交易量过大: {volume} > {symbol_info.volume_max}")
                    if abs(volume / symbol_info.volume_step - round(volume / symbol_info.volume_step)) > 0.001:
                        logger.error(f"❌ 交易量步长不符合要求: {volume} (步长: {symbol_info.volume_step})")

                    # 检查价格精度
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        digits = symbol_info.digits
                        logger.error(f"价格精度: {digits} 位小数")
                        logger.error(f"当前价格: bid={tick.bid}, ask={tick.ask}")
                        logger.error(f"请求价格: {price}")

                        # 检查价格是否在合理范围内
                        if action == mt5.ORDER_TYPE_BUY:
                            if abs(price - tick.ask) > tick.ask * 0.01:  # 1%偏差
                                logger.error(f"❌ 买入价格偏差过大: {price} vs {tick.ask}")
                        else:
                            if abs(price - tick.bid) > tick.bid * 0.01:  # 1%偏差
                                logger.error(f"❌ 卖出价格偏差过大: {price} vs {tick.bid}")

                logger.error(f"========================")

            logger.warning(
                f"订单发送失败: {result.retcode} - {error_description}, 信息: {result.comment}"
            )
        else:
            logger.info(f"订单发送成功，订单号: {result.order}")

        # 如果有注释且订单发送成功，保存注释到数据库
        # 优先使用original_comment（完整决策信息），如果没有则使用comment
        original_comment = request.get('original_comment')
        if original_comment and result.retcode == mt5.TRADE_RETCODE_DONE and result.order > 0:
            from utils.database import save_order_comment
            save_order_comment(result.order, original_comment)
            logger.debug(f"保存完整注释到数据库，订单号: {result.order}")

        return result_dict

    except Exception as e:

        log_exception(error_logger, "发送订单请求时发生异常")

        return None
