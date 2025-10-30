# -*- coding: utf-8 -*-

import yaml
import datetime
import pytz
import MetaTrader5 as mt5
from MT5.order_info import get_active_positions, get_pending_orders
from MT5.history_info import get_history_orders, format_history_for_prompt
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
        # M5 时间框架 - 主要分析时间框架
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

        # ATR (M5) - 主要波动性参考
        atr_m5 = get_atr(symbol, mt5.TIMEFRAME_M5, 14, 5)
        if atr_m5 and len(atr_m5) >= 3:
            indicators['M5']['atr'] = atr_m5[-1] if atr_m5 else None
            indicators['M5']['atr_trend'] = "上升" if atr_m5[-1] > atr_m5[-3] else "下降"
            # 相对波动性判断
            atr_avg = sum(atr_m5) / len(atr_m5)
            indicators['M5']['atr_volatility'] = "高" if atr_m5[-1] > atr_avg * 1.2 else "低"

    except Exception as e:
        print(f"获取 {symbol} M5指标时出错: {e}")

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

    # M5 主要指标
    formatted += "**M5 (主要分析):**\n"

    # RSI信号 (增强版)
    if 'M5' in scalping_data and 'rsi' in scalping_data['M5']:
        rsi_m5 = scalping_data['M5']['rsi']
        rsi_trend = scalping_data['M5'].get('rsi_trend', '未知')
        rsi_extreme = scalping_data['M5'].get('rsi_extreme', '中性')
        trend_icon = "📈" if rsi_trend == "上升" else "📉"
        extreme_icon = "🔴" if rsi_extreme == "超买" else "🟢" if rsi_extreme == "超卖" else "🟡"
        formatted += f"- RSI(M5): {rsi_m5:.1f} {extreme_icon}{rsi_extreme} {trend_icon}{rsi_trend}\n"

    # MACD信号 (增强版)
    if 'M5' in scalping_data and all(k in scalping_data['M5'] for k in ['macd', 'macd_signal', 'macd_histogram']):
        macd = scalping_data['M5']['macd']
        signal = scalping_data['M5']['macd_signal']
        hist = scalping_data['M5']['macd_histogram']
        signal_type = scalping_data['M5'].get('macd_signal_type', '震荡')

        # MACD状态判断
        if signal_type == "金叉":
            macd_trend = "🟢金叉看涨"
        elif signal_type == "死叉":
            macd_trend = "🔴死叉看跌"
        else:
            macd_trend = "🟡震荡整理"

        formatted += f"- MACD(M5): {macd_trend} ({signal_type}) 柱:{hist:.5f}\n"

    # 布林带位置 (增强版)
    if 'M5' in scalping_data and all(k in scalping_data['M5'] for k in ['bb_upper', 'bb_middle', 'bb_lower']):
        bb_position = scalping_data['M5'].get('bb_position', '通道内')
        bb_width_status = scalping_data['M5'].get('bb_width_status', '正常')

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

        formatted += f"- 布林带(M5): {position_icon}{bb_position} {width_icon}{bb_width_status}带宽\n"

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

    # M5 ATR - 主要波动性参考
    if 'M5' in scalping_data and 'atr' in scalping_data['M5']:
        atr_m5 = scalping_data['M5']['atr']
        atr_trend_m5 = scalping_data['M5'].get('atr_trend', '未知')
        atr_vol_m5 = scalping_data['M5'].get('atr_volatility', '低')
        trend_icon_m5 = "📈" if atr_trend_m5 == "上升" else "📉"
        vol_icon_m5 = "🔴" if atr_vol_m5 == "高" else "🟢"
        formatted += f"  - ATR(M5): {atr_m5:.5f} {vol_icon_m5}{atr_vol_m5}波动 {trend_icon_m5}{atr_trend_m5} - **主要波动性参考**\n"

    # M15 ATR - 趋势背景
    if 'M15' in m15_m30_data and 'atr' in m15_m30_data['M15']:
        atr_m15 = m15_m30_data['M15']['atr']
        atr_trend_m15 = m15_m30_data['M15'].get('atr_trend', '未知')
        atr_vol_m15 = m15_m30_data['M15'].get('atr_volatility', '低')
        trend_icon_m15 = "📈" if atr_trend_m15 == "上升" else "📉"
        vol_icon_m15 = "🔴" if atr_vol_m15 == "高" else "🟢"
        formatted += f"  - ATR(M15): {atr_m15:.5f} {vol_icon_m15}{atr_vol_m15}波动 {trend_icon_m15}{atr_trend_m15} - 趋势背景\n"

    return formatted


def get_ai_system_prompt(monitored_pairs_list=None):
    """简化的多策略交易AI系统提示词"""

    # 准备监控货币对列表文本
    if monitored_pairs_list and len(monitored_pairs_list) > 0:
        pairs_text = "- " + "\n- ".join(monitored_pairs_list)
    else:
        pairs_text = "- 无监控货币对配置"

    base_prompt = """你是一个专业的交易AI，能够根据市场条件灵活选择最适合的交易策略来实现盈利最大化。"""

    # 获取完整的系统提示词
    full_prompt = base_prompt + """

## 🎯 核心原则
**灵活应变，盈利优先**：
- 根据实时市场条件自主选择最优策略
- 唯一目标：在风险可控的前提下实现持续盈利
- 可用策略：趋势跟踪、均值回归、突破、区间交易、动量交易
- 支持多货币对同时交易，寻找所有可用机会

## 📊 策略指南
### 趋势跟踪
- **适用**：强趋势市场，ADX > 25
- **信号**：MACD金叉死叉、EMA排列、价格突破均线
- **特点**：顺势而为，持仓时间相对较长

### 均值回归
- **适用**：震荡市场，RSI极端值（<30或>70）
- **信号**：布林带边界反弹、价格远离均线
- **特点**：快进快出，利用价格反转

### 突破策略
- **适用**：关键价位突破，技术形态突破
- **信号**：支撑阻力位突破、成交量放大
- **特点**：追涨杀跌，注意假突破风险

### 区间交易
- **适用**：明确的箱体震荡
- **信号**：价格在区间内反复测试边界
- **特点**：高抛低吸，边界止损

### 动量策略
- **适用**：快速价格运动，新闻驱动
- **信号**：成交量激增、跳空缺口
- **特点**：抓住短期动量，快速退出

## 🧠 策略选择建议
根据市场条件灵活选择：
- **ADX > 25**：考虑趋势跟踪策略
- **ADX < 20**：考虑均值回归或区间交易策略
- **高波动**：考虑突破或动量策略
- **布林带边界**：考虑均值回归策略
- **关键价位**：考虑突破策略

**重要**：这些建议仅供参考，你可以根据实际情况选择任意策略组合。

## 📈 技术指标解读
### RSI
- > 70：超买，考虑均值回归机会
- < 30：超卖，考虑均值回归机会
- > 50：偏向看涨
- < 50：偏向看跌

### MACD
- 金叉：看涨信号
- 死叉：看跌信号
- 柱状体变化：动量强弱

### 布林带
- 价格触及边界：均值回归信号
- 价格突破边界：突破信号
- 价格在中部：区间交易信号

### EMA均线
- 价格 > 5EMA > 10EMA：强势上涨
- 价格 < 5EMA < 10EMA：强势下跌
- 均线交叉：趋势转换信号

## 🚨 交易类型和要求
**允许的交易类型**：
- `BUY` - 开买入仓位
- `SELL` - 开卖出仓位
- `CLOSE` - 平现有仓位（需要order_id）
- `CANCEL` - 撤销挂单（需要order_id）
- `MODIFY` - 修改持仓止损止盈（需要order_id）

**重要约束**：
- 只能使用监控列表中的外汇对（具体货币对请查看当前提供的市场数据）
- volume > 0，止损止盈点数 > 0
- 开新仓时entry_offset_points为0（市价单）
- 可以同时持有多个货币对的订单
- 每个货币对独立分析，不受当前持仓状态影响

## ⚡ 风险控制原则
1. **风险控制优先**：任何交易都要控制风险
2. **灵活设置止损**：根据市场波动性和策略特点设置止损
3. **合理设置止盈**：考虑风险回报比，不要过度贪婪
4. **资金管理**：根据账户规模合理分配资金
5. **多元化交易**：在不同货币对上分散风险

## 💡 参数设置原则
**重要**：你应该根据实时市场条件自主判断并设置最合适的交易参数。记住，成功的交易在于灵活应变，而不是固守规则。

## 📊 动态调用间隔
根据市场活跃度和策略特点动态建议下次调用间隔：

**返回格式要求**：
```json
{
  "analysis": "你的市场分析和策略选择说明...",
  "recommendations": [...],
  "next_call_interval": 300,
  "interval_reason": "某个监控货币对处于趋势跟踪中，建议5分钟后确认趋势延续"
}
```

**间隔设置原则**：
- **next_call_interval**: 下次建议调用间隔（秒数）
- **范围**: 60-1800秒（1分钟-30分钟）
- **interval_reason**: 说明间隔设置原因

**参考间隔**：
- 动量策略：60-300秒（需要快速反应）
- 均值回归：120-600秒（等待反转信号）
- 趋势跟踪：300-1200秒（给趋势发展时间）
- 突破策略：60-600秒（确认突破有效性）
- 区间交易：300-1200秒（等待价格触及边界）

## 🎯 响应格式示例

### 开新仓：
```json
{
  "analysis": "某个监控货币对处于强上升趋势，MACD金叉，选择趋势跟踪策略...",
  "recommendations": [
    {
      "symbol": "监控货币对的名称",
      "action": "BUY",
      "order_type": "MARKET",
      "volume": 0.01,
      "entry_offset_points": 0,
      "stop_loss_points": 20,
      "take_profit_points": 40,
      "comment": "趋势跟踪：MACD金叉+EMA支撑",
      "reasoning": "ADX=28强趋势，MACD金叉确认，价格突破关键阻力位"
    }
  ],
  "next_call_interval": 300,
  "interval_reason": "趋势跟踪中，建议5分钟后确认"
}
```

### 平仓/修改：
```json
{
  "analysis": "持仓达到盈利目标，技术指标出现反转信号...",
  "recommendations": [
    {
      "symbol": "监控货币对的名称",
      "action": "CLOSE",
      "order_id": 123456,
      "reasoning": "达到目标盈利，MACD柱状体收缩"
    }
  ],
  "next_call_interval": 600,
  "interval_reason": "平仓后观察，建议10分钟后重新分析"
}
```

## 🚨 MODIFY操作规则
**MT5约束**：
- 买单：止损价 ≤ 开仓价，止盈价 ≥ 开仓价
- 卖单：止损价 ≥ 开仓价，止盈价 ≤ 开仓价
- 止损止盈点数必须为正数

## ⚠️ 交易纪律
1. **灵活应变**：根据市场变化调整策略
2. **风险控制**：任何时候都要控制风险
3. **精选机会**：宁可错过，不要做错
4. **持续学习**：根据结果不断优化策略
5. **保持冷静**：不要被情绪影响决策

## 💰 点差成本
- 每个货币对点差不同，这是交易成本
- 系统会自动调整不符合MT5最小要求的止损止盈
- 建议确保止盈距离大于点差成本

## 🎯 当前监控货币对
**重要**：以下是你当前可以交易的货币对列表：
{{MONITORED_PAIRS_LIST}}

你只能对上述列出的货币对进行交易，请确保使用准确的货币对名称。

## 🎯 历史交易分析
**重要**：你会看到最近1天的完整历史交易记录，包括你之前的AI决策和最终盈亏结果。这些记录只包含你自己生成的订单（魔数：100001），并提供了今日的统计数据。

**学习目标**：
- **识别成功模式**：分析所有盈利交易的共同特征和策略选择规律
- **避免重复错误**：全面识别亏损交易的问题并系统性改进
- **策略评估**：根据完整的交易数据评估不同策略的实际表现
- **持续改进**：基于全面的交易反馈优化决策逻辑

**分析方法**：
1. **模式识别**：从大量交易中识别成功的信号组合和策略模式
2. **策略验证**：验证不同策略在全天市场变化中的有效性
3. **风险管理**：评估整体风险控制效果和资金管理策略
4. **时机优化**：分析入场和出场时机的准确性，识别最佳操作窗口
5. **市场适应**：了解你的策略在不同市场时段的适应性

## 🎯 最终目标
根据实时市场条件和历史交易经验，灵活选择最优策略，在风险可控的前提下实现持续盈利。记住，成功的交易在于灵活应变和持续学习，而不是固守规则。系统会根据这些偏移量实时计算具体价格。"""

    # 替换货币对列表占位符
    final_prompt = full_prompt.replace("{{MONITORED_PAIRS_LIST}}", pairs_text)

    return final_prompt


def format_multi_strategy_indicators(scalping_data, trend_data, current_price, symbol):
    """为多策略交易格式化技术指标分析"""
    formatted = "### 📊 多策略技术指标分析\n"

    # 市场状态判断
    adx_value = None
    if 'M15' in trend_data and 'adx' in trend_data['M15']:
        adx_value = trend_data['M15']['adx']

    # 市场状态标题
    if adx_value:
        if adx_value > 25:
            market_state = "🟈 **强趋势市场** - 优先考虑趋势跟踪策略"
        elif adx_value < 20:
            market_state = "🔄 **震荡市场** - 优先考虑均值回归/区间交易策略"
        else:
            market_state = "⚖️ **中等强度市场** - 可考虑多策略组合"
        formatted += f"{market_state} (ADX: {adx_value:.1f})\n\n"

    # 不同策略视角的信号分析
    formatted += "**多策略信号解读：**\n"

    # M5 主要指标 - 多策略解读
    formatted += "**M5 (主要入场时机):**\n"

    # RSI的多策略解读
    if 'M5' in scalping_data and 'rsi' in scalping_data['M5']:
        rsi = scalping_data['M5']['rsi']
        if rsi > 70:
            formatted += f"- RSI: {rsi:.1f} 🔴**均值回归信号** - 超买，考虑卖出机会\n"
        elif rsi < 30:
            formatted += f"- RSI: {rsi:.1f} 🟢**均值回归信号** - 超卖，考虑买入机会\n"
        elif rsi > 50:
            formatted += f"- RSI: {rsi:.1f} 🟈**趋势跟踪信号** - 偏向看涨\n"
        else:
            formatted += f"- RSI: {rsi:.1f} 📉**趋势跟踪信号** - 偏向看跌\n"

    # MACD的多策略解读
    if 'M5' in scalping_data and all(k in scalping_data['M5'] for k in ['macd', 'macd_signal', 'macd_signal_type']):
        signal_type = scalping_data['M5']['macd_signal_type']
        if signal_type == "金叉":
            formatted += f"- MACD: 🟈**趋势跟踪信号** - 金叉形成，顺势买入\n"
        elif signal_type == "死叉":
            formatted += f"- MACD: 📉**趋势跟踪信号** - 死叉形成，顺势卖出\n"
        else:
            formatted += f"- MACD: 🔄**震荡信号** - 震荡整理，等待明确方向\n"

    # 布林带的多策略解读
    if 'M5' in scalping_data and 'bb_position' in scalping_data['M5']:
        bb_position = scalping_data['M5']['bb_position']
        if "突破" in bb_position:
            formatted += f"- 布林带: ⚡**突破信号** - {bb_position}，可能开始新趋势\n"
        elif "上轨" in bb_position:
            formatted += f"- 布林带: 🔄**均值回归信号** - 触及上轨，考虑回调\n"
        elif "下轨" in bb_position:
            formatted += f"- 布林带: 🔄**均值回归信号** - 触及下轨，考虑反弹\n"
        else:
            formatted += f"- 布林带: ⚖️**区间交易信号** - {bb_position}，区间内运行\n"

    # EMA趋势的多策略解读
    if 'M5' in scalping_data and all(k in scalping_data['M5'] for k in ['ma5', 'ma10']):
        ma5 = scalping_data['M5']['ma5']
        ma10 = scalping_data['M5']['ma10']
        if current_price > ma5 > ma10:
            formatted += f"- EMA趋势: 🟈**趋势跟踪确认** - 强势上涨趋势\n"
        elif current_price < ma5 < ma10:
            formatted += f"- EMA趋势: 📉**趋势跟踪确认** - 强势下跌趋势\n"
        else:
            formatted += f"- EMA趋势: 🔄**震荡确认** - 趋势不明确，震荡整理\n"

    # M15/M30 趋势背景
    formatted += "\n**M15/M30 (策略选择背景):**\n"

    # ADX趋势强度 - 策略选择指导
    if adx_value:
        if adx_value > 25:
            formatted += f"- ADX强度: {adx_value:.1f} 🟈**适合趋势跟踪策略** - 趋势明显\n"
        elif adx_value < 20:
            formatted += f"- ADX强度: {adx_value:.1f} 🔄**适合震荡策略** - 趋势不明显\n"
        else:
            formatted += f"- ADX强度: {adx_value:.1f} ⚖️**可多策略组合** - 中等趋势强度\n"

    # ATR波动性 - 策略选择指导
    if 'M5' in scalping_data and 'atr' in scalping_data['M5']:
        atr_m5 = scalping_data['M5']['atr']
        atr_vol = scalping_data['M5'].get('atr_volatility', '低')

        if atr_vol == "高":
            formatted += f"- ATR(M5): {atr_m5:.5f} ⚡**高波动** - 适合突破/动量策略\n"
        else:
            formatted += f"- ATR(M5): {atr_m5:.5f} 🔄**低波动** - 适合均值回归/区间策略\n"

    # 策略建议总结
    formatted += "\n**📋 策略建议总结:**\n"
    if adx_value:
        if adx_value > 25:
            formatted += "- 🟈 **推荐策略**: 趋势跟踪策略为主\n"
        elif adx_value < 20:
            formatted += "- 🔄 **推荐策略**: 均值回归/区间交易策略为主\n"
        else:
            formatted += "- ⚖️ **推荐策略**: 多策略组合使用\n"

    return formatted


def get_user_prompt():
    """简化的多策略融合用户提示词"""
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
    monitored_pairs = []
    try:
        monitored_pairs = config.get('forex_pairs', {}).get('monitored_pairs', [])
        if monitored_pairs:
            forex_pairs_info = "## 📈 监控外汇对\n"
            for symbol in monitored_pairs:
                # 获取品种信息
                symbol_info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if symbol_info and tick:
                    current_price = (tick.bid + tick.ask) / 2  # 中间价
                    spread_points = symbol_info.spread  # MT5提供的点差（点数）
                    spread_value = tick.ask - tick.bid  # 点差价值
                    spread_cost = spread_value * 100000  # 标准手数的成本

                    # 价格和点差信息（仅客观数据）
                    current_price_info = f"买价:{tick.bid:.5f} | 卖价:{tick.ask:.5f}"
                    spread_info = f"点差: {spread_points}点 | 成本: ${spread_cost:.2f}/标准手"

                    # 获取技术指标
                    try:
                        # 获取M5指标
                        scalping_data = get_short_term_indicators(symbol, current_price)

                        # 获取M15/M30指标
                        trend_data = get_m15_m30_indicators(symbol)

                        # 格式化多策略技术指标
                        indicators_text = format_multi_strategy_indicators(scalping_data, trend_data, current_price, symbol)
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

                    forex_pairs_info += f"""### {symbol}
**💰 价格信息:**
- 当前价格: {current_price_info}
- {spread_info}

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

    # 获取历史交易记录（只获取AI自己生成的订单）
    try:
        history_orders = get_history_orders(days_back=1)  # 获取最近1天的历史记录

        # 动态限制显示数量：如果订单少于等于10条，显示全部；否则显示最近10条
        max_display = 10 if len(history_orders) > 10 else len(history_orders)
        history_text = format_history_for_prompt(history_orders, max_orders=max_display)
    except Exception as e:
        history_text = f"- 历史交易记录获取失败: {e}"

    # 获取时间信息
    time_info = get_time_info()

    return f"""{time_info}

## 账户信息
{account_text}

## 当前持仓
{positions_text}

## 当前挂单
{orders_text}

{history_text}

## 💡 多货币对交易提醒
分析所有监控的货币对，寻找最佳交易机会。每个货币对独立判断，不受现有持仓影响。

{forex_pairs_info}"""