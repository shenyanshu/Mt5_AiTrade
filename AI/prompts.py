# -*- coding: utf-8 -*-

import yaml
import datetime
import pytz
import MetaTrader5 as mt5
from MT5.order_info import get_active_positions, get_pending_orders
from MT5.market_info import get_pivot_points, get_rsi, get_macd, get_bollinger_bands, get_atr, get_adx, get_dynamic_support_resistance


def count_prompt_tokens(prompt_text, use_tiktoken=True):
    """计算prompt的token数量"""
    if use_tiktoken:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            return len(encoding.encode(prompt_text))
        except:
            return estimate_tokens_by_chars(prompt_text)
    else:
        return estimate_tokens_by_chars(prompt_text)


def estimate_tokens_by_chars(text):
    """通过字符数估算token数量"""
    if not text:
        return 0
    chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 2.5 + other_chars / 4)


def get_time_info():
    """获取当前时间和交易时段信息"""
    try:
        utc_now = datetime.datetime.now(pytz.UTC)

        # 判断主要外汇交易时段
        sessions = []
        if utc_now.hour >= 21 or utc_now.hour < 6:
            sessions.append("悉尼")
        if utc_now.hour >= 23 or utc_now.hour < 8:
            sessions.append("东京")
        if 7 <= utc_now.hour < 16:
            sessions.append("伦敦")
        if 12 <= utc_now.hour < 21:
            sessions.append("纽约")

        activity_level = "高" if len(sessions) >= 2 else "中" if len(sessions) == 1 else "低"
        is_weekend = utc_now.weekday() >= 5
        market_status = "周末休市" if is_weekend else "正常交易"

        return f"""## 时间信息
- UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} UTC
- 活跃时段: {', '.join(sessions) if sessions else '无'}
- 市场活跃度: {activity_level}
- 市场状态: {market_status}"""
    except Exception as e:
        return f"## 时间信息\n- 时间获取失败: {e}"


def get_short_term_indicators(symbol, current_price=None):
    """获取短期趋势跟踪所需的技术指标"""
    indicators = {}

    # 如果没有提供当前价格，尝试获取
    if current_price is None:
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                current_price = (tick.bid + tick.ask) / 2
            else:
                current_price = 0
        except:
            current_price = 0

    try:
        # M1 时间框架 - 精确入场
        indicators['M1'] = {}

        # RSI (M1)
        rsi_m1 = get_rsi(symbol, mt5.TIMEFRAME_M1, 14, 5)
        if rsi_m1 and len(rsi_m1) >= 3:
            indicators['M1']['rsi'] = rsi_m1[-1] if rsi_m1 else None
            indicators['M1']['rsi_trend'] = "上升" if rsi_m1[-1] > rsi_m1[-3] else "下降"
            indicators['M1']['rsi_extreme'] = "超买" if rsi_m1[-1] > 70 else "超卖" if rsi_m1[-1] < 30 else "中性"

        # MACD (M1)
        macd_m1 = get_macd(symbol, mt5.TIMEFRAME_M1, 12, 26, 9, 5)
        if macd_m1 and len(macd_m1[0]) >= 3:
            indicators['M1']['macd'] = macd_m1[0][-1] if macd_m1[0] else None
            indicators['M1']['macd_signal'] = macd_m1[1][-1] if macd_m1[1] else None
            indicators['M1']['macd_histogram'] = macd_m1[2][-1] if macd_m1[2] else None

            # MACD信号分析
            macd_current = macd_m1[0][-1]
            macd_signal_current = macd_m1[1][-1]
            macd_signal_prev = macd_m1[1][-2] if len(macd_m1[1]) >= 2 else macd_signal_current

            # 判断金叉死叉
            if len(macd_m1[0]) >= 2:
                macd_prev = macd_m1[0][-2]
                if macd_prev <= macd_signal_prev and macd_current > macd_signal_current:
                    indicators['M1']['macd_signal_type'] = "金叉"
                elif macd_prev >= macd_signal_prev and macd_current < macd_signal_current:
                    indicators['M1']['macd_signal_type'] = "死叉"
                else:
                    indicators['M1']['macd_signal_type'] = "震荡"
            else:
                indicators['M1']['macd_signal_type'] = "未知"

        # 布林带 (M1)
        bb_m1 = get_bollinger_bands(symbol, mt5.TIMEFRAME_M1, 20, 2.0, 5)
        if bb_m1 and len(bb_m1) >= 3:
            indicators['M1']['bb_upper'] = bb_m1[0][-1] if bb_m1[0] else None
            indicators['M1']['bb_middle'] = bb_m1[1][-1] if bb_m1[1] else None
            indicators['M1']['bb_lower'] = bb_m1[2][-1] if bb_m1[2] else None

            # 布林带位置分析
            bb_upper = bb_m1[0][-1]
            bb_lower = bb_m1[2][-1]
            bb_width = bb_upper - bb_lower

            if current_price > bb_upper:
                indicators['M1']['bb_position'] = "上轨上方(突破)"
            elif current_price < bb_lower:
                indicators['M1']['bb_position'] = "下轨下方(突破)"
            else:
                total_range = bb_upper - bb_lower
                position_ratio = (current_price - bb_lower) / total_range
                if position_ratio > 0.8:
                    indicators['M1']['bb_position'] = "上轨附近"
                elif position_ratio < 0.2:
                    indicators['M1']['bb_position'] = "下轨附近"
                else:
                    indicators['M1']['bb_position'] = "中轨区域"

            # 布林带宽度状态 (比较当前与历史平均宽度)
            if len(bb_m1[0]) >= 5:  # 需要足够的历史数据
                recent_widths = [bb_m1[0][i] - bb_m1[2][i] for i in range(-5, 0)]
                avg_width = sum(recent_widths) / len(recent_widths)
                indicators['M1']['bb_width_status'] = "扩张" if bb_width > avg_width * 1.1 else "收缩" if bb_width < avg_width * 0.9 else "正常"
            else:
                indicators['M1']['bb_width_status'] = "正常"

        # M5 时间框架 - 短期确认
        indicators['M5'] = {}

        # RSI (M5)
        rsi_m5 = get_rsi(symbol, mt5.TIMEFRAME_M5, 14, 5)
        if rsi_m5 and len(rsi_m5) >= 3:
            indicators['M5']['rsi'] = rsi_m5[-1] if rsi_m5 else None
            indicators['M5']['rsi_trend'] = "上升" if rsi_m5[-1] > rsi_m5[-3] else "下降"
            indicators['M5']['rsi_extreme'] = "超买" if rsi_m5[-1] > 70 else "超卖" if rsi_m5[-1] < 30 else "中性"

        # MACD (M5)
        macd_m5 = get_macd(symbol, mt5.TIMEFRAME_M5, 12, 26, 9, 5)
        if macd_m5 and len(macd_m5[0]) >= 3:
            indicators['M5']['macd'] = macd_m5[0][-1] if macd_m5[0] else None
            indicators['M5']['macd_signal'] = macd_m5[1][-1] if macd_m5[1] else None
            indicators['M5']['macd_histogram'] = macd_m5[2][-1] if macd_m5[2] else None

            # MACD信号分析
            macd_current = macd_m5[0][-1]
            macd_signal_current = macd_m5[1][-1]
            macd_signal_prev = macd_m5[1][-2] if len(macd_m5[1]) >= 2 else macd_signal_current

            # 判断金叉死叉
            if len(macd_m5[0]) >= 2:
                macd_prev = macd_m5[0][-2]
                if macd_prev <= macd_signal_prev and macd_current > macd_signal_current:
                    indicators['M5']['macd_signal_type'] = "金叉"
                elif macd_prev >= macd_signal_prev and macd_current < macd_signal_current:
                    indicators['M5']['macd_signal_type'] = "死叉"
                else:
                    indicators['M5']['macd_signal_type'] = "震荡"
            else:
                indicators['M5']['macd_signal_type'] = "未知"

        # 移动平均线 (M5)
        ma_m5 = get_dynamic_support_resistance(symbol, mt5.TIMEFRAME_M5, 5, 10, 5)
        if ma_m5 and len(ma_m5) >= 2:
            indicators['M5']['ma5'] = ma_m5[0][-1] if ma_m5[0] else None  # 5EMA
            indicators['M5']['ma10'] = ma_m5[1][-1] if ma_m5[1] else None  # 10EMA

        # ATR (M1) - 超短期波动
        atr_m1 = get_atr(symbol, mt5.TIMEFRAME_M1, 14, 5)
        if atr_m1 and len(atr_m1) >= 3:
            indicators['M1']['atr'] = atr_m1[-1] if atr_m1 else None
            indicators['M1']['atr_trend'] = "上升" if atr_m1[-1] > atr_m1[-3] else "下降"
            # 相对波动性判断
            atr_avg = sum(atr_m1) / len(atr_m1)
            indicators['M1']['atr_volatility'] = "高" if atr_m1[-1] > atr_avg * 1.2 else "低"

        # ATR (M5) - 短期波动
        atr_m5 = get_atr(symbol, mt5.TIMEFRAME_M5, 14, 5)
        if atr_m5 and len(atr_m5) >= 3:
            indicators['M5']['atr'] = atr_m5[-1] if atr_m5 else None
            indicators['M5']['atr_trend'] = "上升" if atr_m5[-1] > atr_m5[-3] else "下降"
            # 相对波动性判断
            atr_avg = sum(atr_m5) / len(atr_m5)
            indicators['M5']['atr_volatility'] = "高" if atr_m5[-1] > atr_avg * 1.2 else "低"

    except Exception as e:
        print(f"获取 {symbol} M1/M5指标时出错: {e}")

    return indicators


def get_m15_m30_indicators(symbol):
    """获取M15/M30时间框架的趋势确认指标"""
    indicators = {}

    try:
        # M15 时间框架 - 中期趋势
        indicators['M15'] = {}

        # ADX (M15) - 趋势强度
        adx_m15 = get_adx(symbol, mt5.TIMEFRAME_M15, 14, 5)
        if adx_m15 and len(adx_m15) >= 3:
            indicators['M15']['adx'] = adx_m15[0][-1] if adx_m15[0] else None
            indicators['M15']['di_plus'] = adx_m15[1][-1] if adx_m15[1] else None
            indicators['M15']['di_minus'] = adx_m15[2][-1] if adx_m15[2] else None

        # ATR (M15) - 波动性
        atr_m15 = get_atr(symbol, mt5.TIMEFRAME_M15, 14, 5)
        if atr_m15 and len(atr_m15) >= 3:
            indicators['M15']['atr'] = atr_m15[-1] if atr_m15 else None
            indicators['M15']['atr_trend'] = "上升" if atr_m15[-1] > atr_m15[-3] else "下降"
            # 相对波动性判断
            atr_avg = sum(atr_m15) / len(atr_m15)
            indicators['M15']['atr_volatility'] = "高" if atr_m15[-1] > atr_avg * 1.2 else "低"

        # 20EMA (M15)
        ma_m15 = get_dynamic_support_resistance(symbol, mt5.TIMEFRAME_M15, 20, 50, 5)
        if ma_m15:
            indicators['M15']['ema20'] = ma_m15[0][-1] if ma_m15[0] else None

        # M30 时间框架 - 趋势确认
        indicators['M30'] = {}

        # ADX (M30)
        adx_m30 = get_adx(symbol, mt5.TIMEFRAME_M30, 14, 5)
        if adx_m30 and len(adx_m30) >= 3:
            indicators['M30']['adx'] = adx_m30[0][-1] if adx_m30[0] else None
            indicators['M30']['di_plus'] = adx_m30[1][-1] if adx_m30[1] else None
            indicators['M30']['di_minus'] = adx_m30[2][-1] if adx_m30[2] else None

        # ATR (M30)
        atr_m30 = get_atr(symbol, mt5.TIMEFRAME_M30, 14, 5)
        if atr_m30 and len(atr_m30) >= 3:
            indicators['M30']['atr'] = atr_m30[-1] if atr_m30 else None
            indicators['M30']['atr_trend'] = "上升" if atr_m30[-1] > atr_m30[-3] else "下降"
            # 相对波动性判断
            atr_avg = sum(atr_m30) / len(atr_m30)
            indicators['M30']['atr_volatility'] = "高" if atr_m30[-1] > atr_avg * 1.2 else "低"

    except Exception as e:
        print(f"获取 {symbol} M15/M30指标时出错: {e}")

    return indicators


def format_short_term_indicators(scalping_data, m15_m30_data, current_price):
    """格式化短期趋势指标为易读的文本"""
    formatted = "### 📊 技术指标分析\n"

    # M1/M5 精确入场指标
    formatted += "**M1/M5 (精确入场):**\n"

    # RSI信号 (增强版)
    if 'M1' in scalping_data and 'rsi' in scalping_data['M1']:
        rsi_m1 = scalping_data['M1']['rsi']
        rsi_trend = scalping_data['M1'].get('rsi_trend', '未知')
        rsi_extreme = scalping_data['M1'].get('rsi_extreme', '中性')
        trend_icon = "📈" if rsi_trend == "上升" else "📉"
        extreme_icon = "🔴" if rsi_extreme == "超买" else "🟢" if rsi_extreme == "超卖" else "🟡"
        formatted += f"- RSI(M1): {rsi_m1:.1f} {extreme_icon}{rsi_extreme} {trend_icon}{rsi_trend}\n"

    if 'M5' in scalping_data and 'rsi' in scalping_data['M5']:
        rsi_m5 = scalping_data['M5']['rsi']
        rsi_trend = scalping_data['M5'].get('rsi_trend', '未知')
        rsi_extreme = scalping_data['M5'].get('rsi_extreme', '中性')
        trend_icon = "📈" if rsi_trend == "上升" else "📉"
        extreme_icon = "🔴" if rsi_extreme == "超买" else "🟢" if rsi_extreme == "超卖" else "🟡"
        formatted += f"- RSI(M5): {rsi_m5:.1f} {extreme_icon}{rsi_extreme} {trend_icon}{rsi_trend}\n"

    # MACD信号 (增强版)
    if 'M1' in scalping_data and all(k in scalping_data['M1'] for k in ['macd', 'macd_signal', 'macd_histogram']):
        macd = scalping_data['M1']['macd']
        signal = scalping_data['M1']['macd_signal']
        hist = scalping_data['M1']['macd_histogram']
        signal_type = scalping_data['M1'].get('macd_signal_type', '震荡')

        # MACD状态判断
        if signal_type == "金叉":
            macd_trend = "🟢金叉看涨"
        elif signal_type == "死叉":
            macd_trend = "🔴死叉看跌"
        else:
            macd_trend = "🟡震荡整理"

        formatted += f"- MACD(M1): {macd_trend} ({signal_type}) 柱:{hist:.5f}\n"

    # 布林带位置 (增强版)
    if 'M1' in scalping_data and all(k in scalping_data['M1'] for k in ['bb_upper', 'bb_middle', 'bb_lower']):
        bb_position = scalping_data['M1'].get('bb_position', '通道内')
        bb_width_status = scalping_data['M1'].get('bb_width_status', '正常')

        # 布林带位置图标
        if "突破" in bb_position:
            position_icon = "⚡"
        elif "上轨" in bb_position:
            position_icon = "🔴"
        elif "下轨" in bb_position:
            position_icon = "🟢"
        else:
            position_icon = "🟡"

        # 宽度状态图标
        width_icon = "📈" if bb_width_status == "扩张" else "📉" if bb_width_status == "收缩" else "➡️"

        formatted += f"- 布林带(M1): {position_icon}{bb_position} {width_icon}{bb_width_status}带宽\n"

    # 移动平均线趋势
    if 'M5' in scalping_data and all(k in scalping_data['M5'] for k in ['ma5', 'ma10']):
        ma5 = scalping_data['M5']['ma5']
        ma10 = scalping_data['M5']['ma10']
        if current_price > ma5 > ma10:
            ma_trend = "🟢强势上涨"
        elif current_price < ma5 < ma10:
            ma_trend = "🔴强势下跌"
        else:
            ma_trend = "🟡整理中"
        formatted += f"- EMA趋势(M5): {ma_trend}\n"

    # M15/M30 趋势确认
    formatted += "\n**M15/M30 (趋势确认):**\n"

    # ADX趋势强度
    if 'M15' in m15_m30_data and 'adx' in m15_m30_data['M15']:
        adx = m15_m30_data['M15']['adx']
        if adx > 25:
            adx_strength = "🟢强趋势"
        elif adx > 20:
            adx_strength = "🟡中等趋势"
        else:
            adx_strength = "🔴弱趋势"
        formatted += f"- ADX(M15): {adx:.1f} {adx_strength}\n"

    # 多时间框架ATR波动性分析 (增强版)
    formatted += "- **ATR波动性分析:**\n"

    # M1 ATR - 超短期
    if 'M1' in scalping_data and 'atr' in scalping_data['M1']:
        atr_m1 = scalping_data['M1']['atr']
        atr_trend_m1 = scalping_data['M1'].get('atr_trend', '未知')
        atr_vol_m1 = scalping_data['M1'].get('atr_volatility', '低')
        trend_icon_m1 = "📈" if atr_trend_m1 == "上升" else "📉"
        vol_icon_m1 = "🔴" if atr_vol_m1 == "高" else "🟢"
        formatted += f"  - ATR(M1): {atr_m1:.5f} {vol_icon_m1}{atr_vol_m1}波动 {trend_icon_m1}{atr_trend_m1} - 超短期参考\n"

    # M5 ATR - 短期主要参考
    if 'M5' in scalping_data and 'atr' in scalping_data['M5']:
        atr_m5 = scalping_data['M5']['atr']
        atr_trend_m5 = scalping_data['M5'].get('atr_trend', '未知')
        atr_vol_m5 = scalping_data['M5'].get('atr_volatility', '低')
        trend_icon_m5 = "📈" if atr_trend_m5 == "上升" else "📉"
        vol_icon_m5 = "🔴" if atr_vol_m5 == "高" else "🟢"
        formatted += f"  - ATR(M5): {atr_m5:.5f} {vol_icon_m5}{atr_vol_m5}波动 {trend_icon_m5}{atr_trend_m5} - **主要参考**\n"

    # M15 ATR - 趋势背景
    if 'M15' in m15_m30_data and 'atr' in m15_m30_data['M15']:
        atr_m15 = m15_m30_data['M15']['atr']
        atr_trend_m15 = m15_m30_data['M15'].get('atr_trend', '未知')
        atr_vol_m15 = m15_m30_data['M15'].get('atr_volatility', '低')
        trend_icon_m15 = "📈" if atr_trend_m15 == "上升" else "📉"
        vol_icon_m15 = "🔴" if atr_vol_m15 == "高" else "🟢"
        formatted += f"  - ATR(M15): {atr_m15:.5f} {vol_icon_m15}{atr_vol_m15}波动 {trend_icon_m15}{atr_trend_m15} - 趋势背景\n"

    # ATR使用建议
    formatted += "  - **建议**: 基于M5 ATR设置止损，参考M1调整精度，考虑M15判断趋势\n"

    return formatted


def get_ai_system_prompt():
    """短期趋势跟踪交易AI系统提示词"""
    return """你是一个专业的短期趋势跟踪交易员，专注于捕捉5-30分钟的短期趋势机会。

## 🎯 交易策略核心
**短期趋势跟踪原则**：
- 持仓时间：通常5-15分钟，最长不超过30分钟
- 寻找高质量的短期趋势机会
- 设置合理的止损控制风险
- 精选交易：等待高概率信号，避免过度交易
- **多货币对交易**：即使已有持仓，也要观察所有监控货币对，寻找更多机会
- **收益最大化**：通过把握优质趋势机会，提升整体收益比率

## 🚨 交易类型严格要求
**你必须只使用以下5种标准交易类型：**
1. `BUY` - 开买入仓位
2. `SELL` - 开卖出仓位
3. `CLOSE` - 平现有仓位（需要提供准确的order_id）
4. `CANCEL` - 撤销挂单（需要提供准确的order_id）
5. `MODIFY` - 修改现有仓位的止损止盈（需要提供准确的order_id）

**绝对禁止使用任何其他类型：**
- 禁止：NO_TRADE, NO_NEW_POSITIONS, WAIT, SKIP, HOLD
- 禁止：任何自定义的非标准操作类型
- 如果没有合适的交易机会，可以不返回任何recommendations或返回空数组[]

## 📊 技术指标优先级
**M5/M15时间框架（主要）**：
- RSI < 30 🟢 超卖买入机会 | RSI > 70 🔴 超买卖出机会
- MACD金叉 🟢 买入信号 | MACD死叉 🔴 卖出信号
- 布林带突破：价格突破上轨🔴追涨 | 跌破下轨🟢追跌
- EMA趋势：价格 > 5EMA > 10EMA 🟢强势 | 价格 < 5EMA < 10EMA 🔴弱势

**M1时间框架（辅助）**：
- 用于选择精确入场时机
- 避免基于M1信号单独开仓
- 配合M5/M15信号优化入场点

**M30时间框架（趋势背景）**：
- ADX > 25 🟢强趋势适合跟踪 | ADX < 20 🔴弱趋势避免交易
- ATR波动性：高波动🔴调整止损 | 低波动🟢稳定盈利

## 🚨 关键指令 - 订单号处理
**非常重要：必须正确区分持仓(position)和挂单(pending order)**

### 持仓处理 (CLOSE/MODIFY)
- **CLOSE操作**: 用于平仓，从"当前持仓"部分找订单号
- **MODIFY操作**: 用于修改持仓的止损止盈，从"当前持仓"部分找订单号
- 持仓信息格式：`订单号: 123456 | XAUUSDm | 买入 | 手数:0.01 | 盈亏:15.20`

### 挂单处理 (CANCEL)
- **CANCEL操作**: 用于撤单，从"当前挂单"部分找订单号
- 挂单信息格式：`订单号: 123456 | XAUUSDm | Buy Limit | 手数:0.01 | 价格:1.16525`

**重要提醒**:
- 持仓可以用MODIFY修改止损止盈，不能用CANCEL
- 挂单只能用CANCEL删除，不能用MODIFY
- 必须从对应的列表中找到正确的订单号

## ⚡ 短期趋势跟踪响应格式

### 🚨 重要：只允许使用以下标准交易类型
**允许的action类型（必须严格使用）：**
- `BUY` - 开买入仓
- `SELL` - 开卖出仓
- `CLOSE` - 平仓（需要提供order_id）
- `CANCEL` - 撤销挂单（需要提供order_id）
- `MODIFY` - 修改持仓止损止盈（需要提供order_id）

**禁止使用的类型：**
- ❌ NO_TRADE, NO_NEW_POSITIONS, WAIT, SKIP, HOLD 等自定义类型
- ❌ 任何不在上面允许列表中的action

### 开新仓格式：
```json
{
  "recommendations": [
    {
      "symbol": "XAUUSDm",
      "action": "BUY",
      "order_type": "MARKET",
      "volume": 0.01,
      "entry_offset_points": 0,
      "stop_loss_points": [根据市场情况自主判断],
      "take_profit_points": [根据市场情况自主判断],
      "comment": "RSI超卖反弹+MACD金叉",
      "reasoning": "RSI超卖，MACD金叉形成，布林带下轨支撑，适合短期趋势跟踪"
    }
  ]
}
```

**点差数据示例**：
- EURUSDm：点差2点，成本$2.00/标准手
- GBPJPY：点差7点，成本$7.00/标准手
- 其他货币对：点差不同，成本各异

### 平仓/撤单格式：
```json
{
  "recommendations": [
    {
      "symbol": "XAUUSDm",
      "action": "CLOSE",
      "order_id": 123456,
      "reasoning": "达到目标盈利或出现反转信号"
    }
  ]
}
```

### 修改持仓格式：
```json
{
  "recommendations": [
    {
      "symbol": "XAUUSDm",
      "action": "MODIFY",
      "order_id": 123456,
      "stop_loss_points": [根据市场情况自主判断],
      "take_profit_points": [根据市场情况自主判断],
      "reasoning": "快速盈利中，调整止损保护利润"
    }
  ]
}
```

## ⚠️ 短期趋势跟踪交易纪律
1. **严格止损**：单笔亏损不超过账户1%
2. **耐心持盈**：给趋势足够发展时间，避免过早平仓
3. **顺势交易**：严格顺着M15/M30趋势方向交易
4. **精选机会**：宁缺毋滥，等待高质量信号确认
5. **关注点差成本**：确保交易成本合理
6. **多元化交易**：即使已有持仓，也要分析所有监控货币对，寻找最佳交易机会
7. **资金管理**：同时持仓多个订单时，总风险控制在账户可承受范围内
8. **趋势识别**：专注于识别和跟踪短期趋势的启动和延续

## 📊 ATR波动性分析与止损设置
**多时间框架ATR使用策略**：
- **ATR(M1)**：入场时机参考，用于优化精确入场点
- **ATR(M5)**：主要止损参考，适用于5-15分钟的趋势跟踪止损
- **ATR(M15)**：趋势背景判断，帮助判断市场整体波动环境

**ATR-based止损建议**：
- **高波动市场**（ATR较大）：适当增大止损距离，避免正常波动误触发
- **低波动市场**（ATR较小）：可设置较紧止损，提高风险回报比
- **止损范围参考**：通常为ATR(M5)的1.5-3倍，根据具体市场情况调整
- **动态调整**：结合ATR(M1)优化入场，考虑ATR(M15)判断趋势强度

**重要提醒**：ATR是重要的参考信息，但你仍需结合技术指标、支撑阻力位、市场情绪等综合判断，自主决定最合适的止损距离。

## 💰 点差信息说明
**每个货币对的点差都不同，这是交易的基本成本。**

### 点差数据：
- **点差**：买入价和卖出价之间的差额（以点为单位）
- **成本**：标准手数的点差成本金额
- **影响**：点差是开仓时即产生的成本

### 自动调整规则：
系统会自动调整你的止损止盈设置以符合MT5要求：
- 最小止损距离：基于MT5的最小止损要求和点差
- 你的设置如果小于要求，系统会自动调整到合规距离

## 🎯 建议参数（仅供参考）
根据短期趋势跟踪特点，以下参数范围可供参考：
- 止损点数：根据市场波动和点差成本自行判断
- 止盈点数：根据风险回报比和市场情况自行判断
- 风险回报比：确保合理性和可持续性

请根据当前市场条件、点差成本和技术分析结果，自主判断并设置最合适的止损止盈间隔。

## 💼 多货币对交易策略
**重要提醒**：
- **不要因为已有持仓而忽略其他货币对的机会**
- **每个货币对都是独立的分析机会**
- **分散投资可以降低整体风险，提升收益稳定性**
- **同时监控多个货币对的技术信号和市场状态**

**执行原则**：
1. **全面分析**：分析所有监控货币对，不受当前持仓影响
2. **机会优先**：哪个货币对出现最佳信号就交易哪个
3. **风险分散**：适当分配资金到不同货币对
4. **收益最大化**：通过多个优质机会提升整体收益

## 📋 持仓分析策略
**重要**：仔细分析当前持仓的完整注释信息！

### 🔍 持仓注释分析要求：
- **认真阅读每个持仓的完整注释**：包含开仓时的技术分析和推理过程
- **对比当前市场状况**：与开仓时的技术信号进行对比
- **评估持仓有效性**：判断开仓理由是否仍然有效
- **决定持仓策略**：
  - **继续持有**：如果开仓理由依然有效且趋势未变
  - **立即平仓**：如果开仓理由已失效或出现反转信号
  - **调整止损止盈**：如果市场情况发生变化但趋势方向未改

### 📊 分析重点：
1. **技术指标对比**：当前的RSI、MACD、布林带等指标与开仓时的对比
2. **趋势持续性**：开仓时的趋势是否仍在继续
3. **信号反转**：是否出现与开仓理由相反的强信号
4. **盈亏状态**：结合当前盈亏情况和技术分析决定是否平仓

**记住**：每个持仓的注释都是你之前决策的完整记录，要认真分析并对比当前市场状况！

## 📈 信号确认要求
**开仓条件（必须满足3个以上，且包含主要信号）**：
- **主要信号**：RSI极端信号（<30或>70）+ MACD明确交叉信号
- **次要信号**：布林带突破或反弹、EMA趋势方向一致
- **趋势确认**：ADX显示足够趋势强度，M15趋势方向一致
- **质量优先**：宁可错过机会，也不要低质量信号

## 重要约束
- 只使用监控列表中的外汇对
- volume > 0
- 止损止盈点数 > 0
- 开新仓时entry_offset_points为0（市价单）
- 根据市场情况自主判断止损止盈间隔
- **可以同时持有多个货币对的订单**
- **每个货币对独立分析，不受当前持仓状态影响**

系统会根据这些偏移量实时计算具体价格。"""


def count_prompt_tokens(prompt_text, use_tiktoken=True):
    """计算prompt的token数量"""
    if use_tiktoken:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            return len(encoding.encode(prompt_text))
        except:
            return estimate_tokens_by_chars(prompt_text)
    else:
        return estimate_tokens_by_chars(prompt_text)


def get_user_prompt():
    """简化的用户提示词"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except:
        config = {}

    # 获取账户信息
    try:
        if mt5.initialize():
            account_info = mt5.account_info()
            if account_info:
                acct = account_info._asdict()
                account_text = f"""- 余额: {acct.get('balance', 0)} {acct.get('currency', 'USD')}
- 净值: {acct.get('equity', 0)} {acct.get('currency', 'USD')}
- 杠杆: 1:{acct.get('leverage', 0)}
- 浮动盈亏: {acct.get('profit', 0)}"""
            else:
                account_text = "账户信息获取失败"
        else:
            account_text = "MT5连接失败"
    except Exception as e:
        account_text = f"账户信息错误: {e}"

    # 获取持仓信息
    try:
        positions = get_active_positions()
        if positions and len(positions) > 0:
            positions_text = ""
            for pos in positions[:5]:  # 最多显示5个持仓
                # 计算持仓时间
                try:
                    import datetime
                    current_time = datetime.datetime.now()
                    open_time = datetime.datetime.fromtimestamp(pos['time'])
                    holding_duration = current_time - open_time
                    holding_minutes = int(holding_duration.total_seconds() / 60)
                except:
                    holding_minutes = 0

                positions_text += f"""订单号: {pos['ticket']} | {pos['symbol']} | {pos['position_type']} | 手数:{pos['volume']} | 持仓{holding_minutes}分钟 | 盈亏:{pos['profit']:.2f}\n"""
        else:
            positions_text = "- 当前无持仓"
    except:
        positions_text = "持仓信息获取失败"

    # 获取挂单信息
    try:
        orders = get_pending_orders()
        if orders and len(orders) > 0:
            orders_text = ""
            for order in orders[:5]:  # 最多显示5个挂单
                # 计算挂单时间
                try:
                    import datetime
                    current_time = datetime.datetime.now()
                    order_time = datetime.datetime.fromtimestamp(order['time'])
                    pending_duration = current_time - order_time
                    pending_minutes = int(pending_duration.total_seconds() / 60)
                except:
                    pending_minutes = 0

                orders_text += f"""订单号: {order['ticket']} | {order['symbol']} | {order['order_type']} | 手数:{order['volume']} | 挂单{pending_minutes}分钟 | 价格:{order['price_open']:.5f}\n"""
        else:
            orders_text = "- 当前无挂单"
    except:
        orders_text = "挂单信息获取失败"

    # 获取监控外汇对信息
    forex_pairs_info = ""
    try:
        monitored_pairs = config.get('forex_pairs', {}).get('monitored_pairs', [])
        if monitored_pairs:
            forex_pairs_info = "## 📈 监控外汇对 (短期趋势跟踪模式)\n"
            for symbol in monitored_pairs:
                # 获取品种信息
                symbol_info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if symbol_info and tick:
                    current_price = (tick.bid + tick.ask) / 2  # 中间价
                    spread_points = symbol_info.spread  # MT5提供的点差（点数）
                    spread_value = tick.ask - tick.bid  # 点差价值
                    spread_cost = spread_value * 100000  # 标准手数的成本

                    # 点差信息显示（仅客观数据）
                    spread_status = f"{spread_points}点"

                    # 获取技术指标
                    try:
                        # 获取M1/M5指标
                        scalping_data = get_short_term_indicators(symbol, current_price)

                        # 获取M15/M30指标
                        trend_data = get_m15_m30_indicators(symbol)

                        # 格式化技术指标
                        indicators_text = format_short_term_indicators(scalping_data, trend_data, current_price)
                    except Exception as e:
                        indicators_text = f"- 技术指标获取失败: {e}\n"

                    # 获取枢轴点
                    try:
                        pivot_points = get_pivot_points(symbol)
                        pivot_text = ""
                        if pivot_points:
                            p, r1, s1, r2, s2, r3, s3 = pivot_points

                            # 判断价格与枢轴点关系
                            if current_price > p:
                                if current_price > r2:
                                    pivot_relation = "🔴远超枢轴点"
                                elif current_price > r1:
                                    pivot_relation = "🟡突破R1"
                                else:
                                    pivot_relation = "🟢枢轴点上方"
                            else:
                                if current_price < s2:
                                    pivot_relation = "🟢远低于枢轴点"
                                elif current_price < s1:
                                    pivot_relation = "🔴跌破S1"
                                else:
                                    pivot_relation = "🟡枢轴点下方"

                            pivot_text = f"枢轴点: {p:.5f} | {pivot_relation}\n  R1:{r1:.5f} S1:{s1:.5f}"
                    except:
                        pivot_text = "枢轴点获取失败"

                    # 价格和点差信息（仅客观数据）
                    current_price_info = f"买价:{tick.bid:.5f} | 卖价:{tick.ask:.5f}"
                    spread_info = f"点差: {spread_points}点 | 成本: ${spread_cost:.2f}/标准手"

                    # 计算信息（仅客观数据）
                    profit_info = f"当前点差: {spread_points}点，请根据点差成本合理设置止盈"

                    forex_pairs_info += f"""### {symbol}
**💰 价格信息:**
- 当前价格: {current_price_info}
- {spread_info}
- {profit_info}

**📍 关键水平:**
- {pivot_text}

{indicators_text}

---
"""
                else:
                    forex_pairs_info += f"### {symbol}\n- 价格信息获取失败\n\n"
        else:
            forex_pairs_info = "## 监控外汇对\n- 无配置"
    except Exception as e:
        forex_pairs_info = f"## 监控外汇对\n- 获取失败: {e}"

    # 获取时间信息
    time_info = get_time_info()

    return f"""{time_info}

## 账户信息
{account_text}

## 当前持仓
{positions_text}

## 当前挂单
{orders_text}

## 💡 多货币对交易提醒
**重要**：请分析所有监控的货币对，即使已有持仓也要寻找其他货币对的机会！
**目标**：通过多货币对分散投资，最大化整体收益比率。

{forex_pairs_info}"""