# -*- coding: utf-8 -*-

"""
简化的AI交易分析模块
"""

import json
import re
import MetaTrader5 as mt5
from MT5.order_info import send_order_request, get_active_positions, get_pending_orders
from MT5.init import get_account_info
from utils.logger import get_trading_logger, get_error_logger
from AI.client import get_ai_client, AIClientError
from AI.realtime_calculator import calculate_simple_prices
from AI.prompts import count_prompt_tokens


class TradingAnalysisError(Exception):
    """交易分析异常"""
    pass


def clean_comment_for_mt5(comment: str) -> str:
    """
    清理注释以符合MT5要求（31字符限制）

    Args:
        comment: 原始注释

    Returns:
        str: 清理后的注释
    """
    if not comment:
        return "AI操作"

    # 移除特殊字符，只保留字母、数字、中文、空格和基本标点
    cleaned = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:-]', '', comment)

    # 移除多余空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # MT5 Python API注释限制：31字符
    if len(cleaned) > 31:
        cleaned = cleaned[:28] + "..."

    # 如果清理后为空，返回默认值
    if not cleaned:
        return "AI操作"

    return cleaned


def analyze_market(system_prompt: str, user_prompt: str) -> dict:
    """
    调用AI进行市场分析

    Args:
        system_prompt: AI系统提示词
        user_prompt: 用户提示词

    Returns:
        dict: AI分析结果
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        logger.info("开始AI市场分析")

        # 计算提示词token数量（额外的统计，AI客户端内部也会打印）
        system_tokens = count_prompt_tokens(system_prompt)
        user_tokens = count_prompt_tokens(user_prompt)
        total_tokens = system_tokens + user_tokens

        logger.info(f"提示词Token统计 - 系统: {system_tokens}, 用户: {user_tokens}, 总计: {total_tokens}")

        # 调用AI模型
        ai_client = get_ai_client()
        ai_response_dict = ai_client.analyze_market(system_prompt, user_prompt)
        ai_response = json.dumps(ai_response_dict, ensure_ascii=False)

        logger.info(f"AI响应获取成功，长度: {len(ai_response)} 字符")

        # 解析和验证AI响应
        analysis_result = parse_ai_response(ai_response)

        if not analysis_result:
            raise TradingAnalysisError("AI响应解析失败")

        logger.info(f"成功解析AI响应，获取到 {len(analysis_result.get('recommendations', []))} 个交易建议")
        return analysis_result

    except AIClientError as e:
        error_logger.error(f"AI模型调用失败: {e}")
        raise TradingAnalysisError(f"AI模型调用失败: {e}")
    except Exception as e:
        error_logger.error(f"AI市场分析失败: {e}")
        raise TradingAnalysisError(f"AI分析失败: {e}")


def parse_ai_response(response_text: str) -> dict:
    """
    解析AI返回的JSON响应

    Args:
        response_text: AI返回的原始文本

    Returns:
        dict: 解析后的交易建议
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        if not response_text or not response_text.strip():
            raise ValueError("AI响应为空")

        # 提取JSON片段
        start_brace = response_text.find('{')
        end_brace = response_text.rfind('}')

        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            json_candidate = response_text[start_brace:end_brace + 1]
            parsed_data = json.loads(json_candidate)
        else:
            raise ValueError("无法找到有效的JSON格式")

        # 验证基本结构
        if 'recommendations' not in parsed_data:
            raise ValueError("缺少recommendations字段")

        recommendations = parsed_data['recommendations']
        if not isinstance(recommendations, list):
            raise ValueError("recommendations必须是数组")

        logger.info(f"成功解析AI响应，包含 {len(recommendations)} 个建议")
        return parsed_data

    except json.JSONDecodeError as e:
        error_logger.error(f"JSON格式错误: {e}")
        raise ValueError(f"JSON解析失败: {e}")
    except Exception as e:
        error_logger.error(f"解析AI响应失败: {e}")
        raise ValueError(f"解析失败: {e}")


def execute_trading_plan(analysis_result: dict) -> list:
    """
    执行交易计划

    Args:
        analysis_result: AI分析结果

    Returns:
        list: 执行结果
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()
    execution_results = []

    try:
        recommendations = analysis_result.get('recommendations', [])
        if not recommendations:
            logger.info("无交易建议需要执行")
            return execution_results

        logger.info(f"开始执行 {len(recommendations)} 个交易建议")

        # 获取账户信息
        account_info = get_account_info()
        if not account_info:
            error_logger.error("无法获取账户信息")
            return execution_results

        # 执行每个交易建议
        for i, rec in enumerate(recommendations):
            try:
                logger.info(f"执行交易建议 {i+1}/{len(recommendations)}: {rec.get('symbol')} {rec.get('action')}")

                # 处理不同类型的交易动作
                action = rec.get('action')

                # 跳过非交易操作
                if action in ['HOLD', 'NO_TRADE', 'NO_NEW_POSITIONS', 'WAIT', 'SKIP']:
                    logger.info(f"跳过非交易操作: {rec.get('symbol')} {action}")
                    execution_results.append({
                        'symbol': rec.get('symbol'),
                        'action': action,
                        'success': True,
                        'reason': f"跳过非交易操作: {action}",
                        'order_ticket': None
                    })
                    continue

                # 执行实际交易操作
                if action in ['CLOSE', 'CANCEL']:
                    result = execute_close_cancel(rec)
                elif action == 'MODIFY':
                    result = execute_modify(rec)
                elif action in ['BUY', 'SELL']:
                    result = execute_buy_sell(rec, account_info)
                else:
                    # 未知操作类型
                    logger.warning(f"未知的交易操作类型: {action}, 跳过执行")
                    execution_results.append({
                        'symbol': rec.get('symbol'),
                        'action': action,
                        'success': False,
                        'reason': f"未知的操作类型: {action}",
                        'order_ticket': None
                    })
                    continue

                execution_results.append(result)

                # 记录详细执行结果
                if result.get('success'):
                    logger.info(f"✅ {rec.get('action')}操作成功: {rec.get('symbol')} 订单号{result.get('order_ticket')}")
                else:
                    logger.error(f"❌ {rec.get('action')}操作失败: {rec.get('symbol')} - {result.get('reason')}")

            except Exception as e:
                error_logger.error(f"执行交易建议失败: {rec.get('symbol')} {rec.get('action')}, 错误: {e}")
                execution_results.append({
                    'symbol': rec.get('symbol'),
                    'action': rec.get('action'),
                    'success': False,
                    'reason': f"执行异常: {str(e)}",
                    'order_ticket': None
                })

        # 记录执行结果摘要
        successful_trades = sum(1 for result in execution_results if result.get('success'))
        logger.info(f"交易计划执行完成: 成功 {successful_trades}/{len(execution_results)} 笔交易")

        return execution_results

    except Exception as e:
        error_logger.error(f"执行交易计划失败: {e}")
        return execution_results


def execute_buy_sell(rec: dict, account_info: dict) -> dict:
    """
    执行买入/卖出交易

    Args:
        rec: 交易建议
        account_info: 账户信息

    Returns:
        dict: 执行结果
    """
    logger = get_trading_logger()

    try:
        symbol = rec.get('symbol')
        action = rec.get('action')
        volume = rec.get('volume', 0.01)

        # 计算实时价格
        price_result = calculate_simple_prices(
            symbol=symbol,
            action=action,
            volume=volume,
            entry_offset_points=rec.get('entry_offset_points', 0),
            stop_loss_points=rec.get('stop_loss_points', 20),
            take_profit_points=rec.get('take_profit_points', 30)
        )

        if not price_result['success']:
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': price_result['error'],
                'order_ticket': None
            }

        # 构建完整的决策注释信息
        ai_comment = rec.get('comment', '')
        ai_reasoning = rec.get('reasoning', '')

        # 构建完整注释：包含AI的comment和reasoning
        full_comment = f"{ai_comment} | {ai_reasoning}" if ai_reasoning else ai_comment

        # 构建MT5参数 - 不传递comment字段避免MT5库验证错误
        mt5_params = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL,
            'price': price_result['entry_price'],
            'sl': price_result['stop_loss'],
            'tp': price_result['take_profit'],
            'original_comment': full_comment,  # 保存到数据库的完整注释
            'deviation': 10,
            'type_filling': mt5.ORDER_FILLING_IOC,
            'type_time': mt5.ORDER_TIME_GTC
        }

        logger.info(f"📝 完整决策注释将保存到数据库: {full_comment}")
        logger.debug(f"📝 注释不再传递给MT5，避免参数验证错误")

        # 详细的订单调试信息
        logger.info(f"准备发送{action}订单 - {symbol}")
        logger.info(f"价格计算结果: {json.dumps(price_result, ensure_ascii=False)}")
        logger.info(f"MT5参数: {json.dumps(mt5_params, ensure_ascii=False, indent=2)}")

        # 验证关键参数
        if mt5_params['price'] <= 0:
            logger.error(f"❌ 价格无效: {mt5_params['price']}")
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': f'价格计算错误: {mt5_params["price"]}',
                'order_ticket': None
            }

        if mt5_params['volume'] <= 0:
            logger.error(f"❌ 交易量无效: {mt5_params['volume']}")
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': f'交易量错误: {mt5_params["volume"]}',
                'order_ticket': None
            }

        # 验证止损止盈逻辑
        if mt5_params['sl'] > 0 or mt5_params['tp'] > 0:
            symbol_info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if symbol_info and tick:
                entry_price = mt5_params['price']
                sl_price = mt5_params['sl']
                tp_price = mt5_params['tp']

                if mt5_params['type'] == mt5.ORDER_TYPE_BUY:
                    # 买单：止损应该在入场价下方，止盈在上方
                    if sl_price > 0 and sl_price >= entry_price:
                        logger.error(f"❌ 买单止损设置错误: 止损({sl_price}) >= 入场价({entry_price})")
                        return {
                            'symbol': symbol,
                            'action': action,
                            'success': False,
                            'reason': f'买单止损逻辑错误',
                            'order_ticket': None
                        }
                    if tp_price > 0 and tp_price <= entry_price:
                        logger.error(f"❌ 买单止盈设置错误: 止盈({tp_price}) <= 入场价({entry_price})")
                        return {
                            'symbol': symbol,
                            'action': action,
                            'success': False,
                            'reason': f'买单止盈逻辑错误',
                            'order_ticket': None
                        }

                elif mt5_params['type'] == mt5.ORDER_TYPE_SELL:
                    # 卖单：止损应该在入场价上方，止盈在下方
                    if sl_price > 0 and sl_price <= entry_price:
                        logger.error(f"❌ 卖单止损设置错误: 止损({sl_price}) <= 入场价({entry_price})")
                        return {
                            'symbol': symbol,
                            'action': action,
                            'success': False,
                            'reason': f'卖单止损逻辑错误',
                            'order_ticket': None
                        }
                    if tp_price > 0 and tp_price >= entry_price:
                        logger.error(f"❌ 卖单止盈设置错误: 止盈({tp_price}) >= 入场价({entry_price})")
                        return {
                            'symbol': symbol,
                            'action': action,
                            'success': False,
                            'reason': f'卖单止盈逻辑错误',
                            'order_ticket': None
                        }

                logger.info(f"✅ 止损止盈逻辑验证通过: 入场={entry_price}, 止损={sl_price}, 止盈={tp_price}")

        # 发送订单
        logger.info(f"📤 发送MT5订单请求...")
        order_result = send_order_request(mt5_params)

        if order_result and order_result.get('retcode') == mt5.TRADE_RETCODE_DONE:
            logger.info(f"交易执行成功: 订单号={order_result.get('order')}, {symbol} {action}")
            return {
                'symbol': symbol,
                'action': action,
                'success': True,
                'reason': '执行成功',
                'order_ticket': order_result.get('order'),
                'volume': order_result.get('volume'),
                'price': order_result.get('price')
            }
        else:
            error_msg = order_result.get('comment', '未知错误') if order_result else '订单发送失败'
            logger.error(f"交易执行失败: {symbol} {action}, 原因: {error_msg}")
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': f"执行失败: {error_msg}",
                'order_ticket': None
            }

    except Exception as e:
        logger.error(f"执行买卖交易异常: {rec.get('symbol')} {rec.get('action')}, 错误: {e}")
        return {
            'symbol': rec.get('symbol'),
            'action': rec.get('action'),
            'success': False,
            'reason': f"执行异常: {str(e)}",
            'order_ticket': None
        }


def execute_close_cancel(rec: dict) -> dict:
    """
    执行平仓/撤单操作

    Args:
        rec: 交易建议

    Returns:
        dict: 执行结果
    """
    logger = get_trading_logger()

    try:
        symbol = rec.get('symbol')
        action = rec.get('action')
        order_id = rec.get('order_id')

        logger.info(f"CLOSE/CANCEL操作详情: symbol={symbol}, action={action}, order_id={order_id}")

        if not order_id:
            logger.error(f"CLOSE/CANCEL失败: 缺少订单号，AI返回数据: {rec}")
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': '缺少订单号',
                'order_ticket': None
            }

        if action == 'CLOSE':
            # 平仓操作
            logger.info(f"验证持仓存在性: 订单号={order_id}")

            # 先获取所有当前持仓进行验证
            all_positions = mt5.positions_get()
            if not all_positions:
                logger.warning("当前没有任何持仓")
                return {
                    'symbol': symbol,
                    'action': action,
                    'success': False,
                    'reason': '当前无持仓',
                    'order_ticket': None
                }

            # 检查指定订单号的持仓是否存在
            position_info = mt5.positions_get(ticket=order_id)
            if not position_info:
                logger.warning(f"持仓不存在: 订单号={order_id}")
                logger.info(f"当前持仓列表:")
                for pos in all_positions:
                    logger.info(f"  订单号: {pos.ticket}, 品种: {pos.symbol}, 类型: {pos.type}, 手数: {pos.volume}")

                return {
                    'symbol': symbol,
                    'action': action,
                    'success': False,
                    'reason': f'持仓不存在，订单号: {order_id}',
                    'order_ticket': None
                }

            pos = position_info[0]
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return {
                    'symbol': symbol,
                    'action': action,
                    'success': False,
                    'reason': '无法获取价格',
                    'order_ticket': None
                }

            # 确定平仓方向
            if pos.type == mt5.POSITION_TYPE_BUY:
                mt5_order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                mt5_order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask

            mt5_params = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': pos.volume,
                'type': mt5_order_type,
                'price': price,
                'original_comment': f"AI平仓 {symbol} 订单{order_id}",
                'deviation': 10,
                'type_filling': mt5.ORDER_FILLING_IOC,
                'type_time': mt5.ORDER_TIME_GTC,
                'position': order_id
            }

        else:  # CANCEL
            # 撤单操作
            mt5_params = {
                'action': mt5.TRADE_ACTION_REMOVE,
                'symbol': symbol,
                'order': order_id,
                'original_comment': f"AI撤单 {symbol} 订单{order_id}"
            }

        # 执行操作
        order_result = send_order_request(mt5_params)

        if order_result and order_result.get('retcode') == mt5.TRADE_RETCODE_DONE:
            logger.info(f"{action}操作成功: 订单号={order_id}, {symbol}")
            return {
                'symbol': symbol,
                'action': action,
                'success': True,
                'reason': '执行成功',
                'order_ticket': order_id
            }
        else:
            error_msg = order_result.get('comment', '未知错误') if order_result else '操作失败'
            logger.error(f"{action}操作失败: {symbol}, 原因: {error_msg}")
            return {
                'symbol': symbol,
                'action': action,
                'success': False,
                'reason': f"执行失败: {error_msg}",
                'order_ticket': None
            }

    except Exception as e:
        logger.error(f"执行{rec.get('action')}操作异常: {rec.get('symbol')}, 错误: {e}")
        return {
            'symbol': rec.get('symbol'),
            'action': rec.get('action'),
            'success': False,
            'reason': f"执行异常: {str(e)}",
            'order_ticket': None
        }


def execute_modify(rec: dict) -> dict:
    """
    执行修改持仓操作

    Args:
        rec: 交易建议

    Returns:
        dict: 执行结果
    """
    logger = get_trading_logger()

    try:
        symbol = rec.get('symbol')
        order_id = rec.get('order_id')
        stop_loss_points = rec.get('stop_loss_points', 0)
        take_profit_points = rec.get('take_profit_points', 0)

        logger.info(f"MODIFY操作详情: symbol={symbol}, order_id={order_id}, stop_loss_points={stop_loss_points}, take_profit_points={take_profit_points}")

        if not order_id:
            logger.error(f"MODIFY失败: 缺少订单号，AI返回数据: {rec}")
            return {
                'symbol': symbol,
                'action': 'MODIFY',
                'success': False,
                'reason': '缺少订单号',
                'order_ticket': None
            }

        # 获取持仓信息
        position_info = mt5.positions_get(ticket=order_id)
        if not position_info:
            # 检查是否是挂单（错误地使用了MODIFY）
            pending_order = mt5.orders_get(ticket=order_id)
            if pending_order:
                logger.error(f"MODIFY操作错误: 订单号{order_id}是挂单，不是持仓。挂单应该使用CANCEL操作")
                return {
                    'symbol': symbol,
                    'action': 'MODIFY',
                    'success': False,
                    'reason': '订单号是挂单，应使用CANCEL而非MODIFY',
                    'order_ticket': None
                }

            return {
                'symbol': symbol,
                'action': 'MODIFY',
                'success': False,
                'reason': '持仓不存在',
                'order_ticket': None
            }

        pos = position_info[0]

        # 计算新的止损止盈价格
        if stop_loss_points > 0:
            if pos.type == mt5.POSITION_TYPE_BUY:
                new_sl = pos.price_open - (stop_loss_points * mt5.symbol_info(symbol).point)
            else:
                new_sl = pos.price_open + (stop_loss_points * mt5.symbol_info(symbol).point)
        else:
            new_sl = pos.sl

        if take_profit_points > 0:
            if pos.type == mt5.POSITION_TYPE_BUY:
                new_tp = pos.price_open + (take_profit_points * mt5.symbol_info(symbol).point)
            else:
                new_tp = pos.price_open - (take_profit_points * mt5.symbol_info(symbol).point)
        else:
            new_tp = pos.tp

        # 构建修改参数 - 不传递comment字段避免MT5库验证错误
        mt5_params = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': order_id,
            'sl': new_sl,
            'tp': new_tp,
            'original_comment': f"AI修改持仓 {symbol} 订单{order_id}: {rec.get('reasoning', '')}"
        }

        # 执行修改
        order_result = send_order_request(mt5_params)

        if order_result and order_result.get('retcode') == mt5.TRADE_RETCODE_DONE:
            logger.info(f"修改持仓成功: 订单号={order_id}, {symbol}")
            return {
                'symbol': symbol,
                'action': 'MODIFY',
                'success': True,
                'reason': '修改成功',
                'order_ticket': order_id
            }
        else:
            error_msg = order_result.get('comment', '未知错误') if order_result else '修改失败'
            logger.error(f"修改持仓失败: {symbol}, 原因: {error_msg}")
            return {
                'symbol': symbol,
                'action': 'MODIFY',
                'success': False,
                'reason': f"修改失败: {error_msg}",
                'order_ticket': None
            }

    except Exception as e:
        logger.error(f"修改持仓异常: {rec.get('symbol')}, 错误: {e}")
        return {
            'symbol': rec.get('symbol'),
            'action': 'MODIFY',
            'success': False,
            'reason': f"修改异常: {str(e)}",
            'order_ticket': None
        }