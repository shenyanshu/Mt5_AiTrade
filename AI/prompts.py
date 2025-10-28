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


def get_scalping_indicators(symbol):
    """获取剥头皮交易所需的短期技术指标"""
    indicators = {}

    try:
        # M1 时间框架 - 精确入场
        indicators['M1'] = {}

        # RSI (M1)
        rsi_m1 = get_rsi(symbol, mt5.TIMEFRAME_M1, 14, 5)
        if rsi_m1:
            indicators['M1']['rsi'] = rsi_m1[-1] if rsi_m1 else None

        # MACD (M1)
        macd_m1 = get_macd(symbol, mt5.TIMEFRAME_M1, 12, 26, 9, 5)
        if macd_m1 and len(macd_m1) >= 3:
            indicators['M1']['macd'] = macd_m1[0][-1] if macd_m1[0] else None
            indicators['M1']['macd_signal'] = macd_m1[1][-1] if macd_m1[1] else None
            indicators['M1']['macd_histogram'] = macd_m1[2][-1] if macd_m1[2] else None

        # 布林带 (M1)
        bb_m1 = get_bollinger_bands(symbol, mt5.TIMEFRAME_M1, 20, 2.0, 5)
        if bb_m1 and len(bb_m1) >= 3:
            indicators['M1']['bb_upper'] = bb_m1[0][-1] if bb_m1[0] else None
            indicators['M1']['bb_middle'] = bb_m1[1][-1] if bb_m1[1] else None
            indicators['M1']['bb_lower'] = bb_m1[2][-1] if bb_m1[2] else None

        # M5 时间框架 - 短期确认
        indicators['M5'] = {}

        # RSI (M5)
        rsi_m5 = get_rsi(symbol, mt5.TIMEFRAME_M5, 14, 5)
        if rsi_m5:
            indicators['M5']['rsi'] = rsi_m5[-1] if rsi_m5 else None

        # MACD (M5)
        macd_m5 = get_macd(symbol, mt5.TIMEFRAME_M5, 12, 26, 9, 5)
        if macd_m5 and len(macd_m5) >= 3:
            indicators['M5']['macd'] = macd_m5[0][-1] if macd_m5[0] else None
            indicators['M5']['macd_signal'] = macd_m5[1][-1] if macd_m5[1] else None
            indicators['M5']['macd_histogram'] = macd_m5[2][-1] if macd_m5[2] else None

        # 移动平均线 (M5)
        ma_m5 = get_dynamic_support_resistance(symbol, mt5.TIMEFRAME_M5, 5, 10, 5)
        if ma_m5 and len(ma_m5) >= 2:
            indicators['M5']['ma5'] = ma_m5[0][-1] if ma_m5[0] else None  # 5EMA
            indicators['M5']['ma10'] = ma_m5[1][-1] if ma_m5[1] else None  # 10EMA

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
        if atr_m15:
            indicators['M15']['atr'] = atr_m15[-1] if atr_m15 else None

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
        if atr_m30:
            indicators['M30']['atr'] = atr_m30[-1] if atr_m30 else None

    except Exception as e:
        print(f"获取 {symbol} M15/M30指标时出错: {e}")

    return indicators


def format_scalping_indicators(scalping_data, m15_m30_data, current_price):
    """格式化剥头皮指标为易读的文本"""
    formatted = "### 📊 技术指标分析\n"

    # M1/M5 精确入场指标
    formatted += "**M1/M5 (精确入场):**\n"

    # RSI信号
    if 'M1' in scalping_data and 'rsi' in scalping_data['M1']:
        rsi_m1 = scalping_data['M1']['rsi']
        rsi_signal = "🔴超买" if rsi_m1 > 70 else "🟢超卖" if rsi_m1 < 30 else "🟡中性"
        formatted += f"- RSI(M1): {rsi_m1:.1f} {rsi_signal}\n"

    if 'M5' in scalping_data and 'rsi' in scalping_data['M5']:
        rsi_m5 = scalping_data['M5']['rsi']
        rsi_signal = "🔴超买" if rsi_m5 > 70 else "🟢超卖" if rsi_m5 < 30 else "🟡中性"
        formatted += f"- RSI(M5): {rsi_m5:.1f} {rsi_signal}\n"

    # MACD信号
    if 'M1' in scalping_data and all(k in scalping_data['M1'] for k in ['macd', 'macd_signal', 'macd_histogram']):
        macd = scalping_data['M1']['macd']
        signal = scalping_data['M1']['macd_signal']
        hist = scalping_data['M1']['macd_histogram']
        macd_trend = "🟢看涨" if macd > signal and hist > 0 else "🔴看跌" if macd < signal and hist < 0 else "🟡震荡"
        formatted += f"- MACD(M1): {macd_trend} (柱:{hist:.5f})\n"

    # 布林带位置
    if 'M1' in scalping_data and all(k in scalping_data['M1'] for k in ['bb_upper', 'bb_middle', 'bb_lower']):
        upper = scalping_data['M1']['bb_upper']
        lower = scalping_data['M1']['bb_lower']
        if current_price > upper:
            bb_position = "🔴上轨上方 (突破)"
        elif current_price < lower:
            bb_position = "🟢下轨下方 (突破)"
        else:
            bb_position = "🟡通道内"
        formatted += f"- 布林带(M1): {bb_position}\n"

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

    # ATR波动性
    if 'M15' in m15_m30_data and 'atr' in m15_m30_data['M15']:
        atr = m15_m30_data['M15']['atr']
        volatility = "🔴高波动" if atr > current_price * 0.002 else "🟢低波动"
        formatted += f"- ATR(M15): {atr:.5f} {volatility}\n"

    return formatted


def get_ai_system_prompt():
    """剥头皮交易AI系统提示词"""
    return """你是一个专业的剥头皮交易员，专注于短期快速盈利机会。

## 🎯 交易策略核心
**剥头皮交易原则**：
- 持仓时间：通常1-5分钟，最长不超过15分钟
- 寻找快速盈利机会
- 设置合理的止损控制风险
- 高频交易：寻找多个短期机会
- **多货币对交易**：即使已有持仓，也要观察所有监控货币对，寻找更多机会
- **收益最大化**：通过分散投资降低风险，提升整体收益比率

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
**M1/M5时间框架（主要）**：
- RSI < 30 🟢 超卖买入机会 | RSI > 70 🔴 超买卖出机会
- MACD金叉 🟢 买入信号 | MACD死叉 🔴 卖出信号
- 布林带突破：价格突破上轨🔴追涨 | 跌破下轨🟢追跌
- EMA趋势：价格 > 5EMA > 10EMA 🟢强势 | 价格 < 5EMA < 10EMA 🔴弱势

**M15/M30时间框架（确认）**：
- ADX > 25 🟢强趋势适合剥头皮 | ADX < 20 🔴弱趋势避免交易
- ATR波动性：高波动🔴增加风险 | 低波动🟢稳定盈利

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

## ⚡ 剥头皮响应格式

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
      "reasoning": "RSI超卖，MACD金叉形成，布林带下轨支撑，适合快速剥头皮"
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

## ⚠️ 剥头皮交易纪律
1. **严格止损**：单笔亏损不超过账户1%
2. **快速止盈**：达到目标盈利立即平仓
3. **避免逆势**：顺着M15/M30趋势方向剥头皮
4. **控制频率**：避免过度交易，等待高概率机会
5. **关注点差成本**：确保点差成本合理
6. **多元化交易**：即使已有持仓，也要分析所有监控货币对，寻找最佳交易机会
7. **资金管理**：同时持仓多个订单时，总风险控制在账户可承受范围内
8. **机会识别**：不同货币对可能同时出现交易机会，要敏锐捕捉

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
根据剥头皮交易特点，以下参数范围可供参考：
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
**开仓条件（必须满足2个以上）**：
- RSI极端信号（<30或>70）
- MACD明确交叉信号
- 布林带突破或反弹
- EMA趋势方向一致
- ADX显示足够趋势强度

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
                positions_text += f"""订单号: {pos['ticket']} | {pos['symbol']} | {pos['position_type']} | 手数:{pos['volume']} | 盈亏:{pos['profit']:.2f}\n"""
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
                orders_text += f"""订单号: {order['ticket']} | {order['symbol']} | {order['order_type']} | 手数:{order['volume']} | 价格:{order['price_open']:.5f}\n"""
        else:
            orders_text = "- 当前无挂单"
    except:
        orders_text = "挂单信息获取失败"

    # 获取剥头皮外汇对信息
    forex_pairs_info = ""
    try:
        monitored_pairs = config.get('forex_pairs', {}).get('monitored_pairs', [])
        if monitored_pairs:
            forex_pairs_info = "## 📈 监控外汇对 (剥头皮模式)\n"
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
                        scalping_data = get_scalping_indicators(symbol)

                        # 获取M15/M30指标
                        trend_data = get_m15_m30_indicators(symbol)

                        # 格式化技术指标
                        indicators_text = format_scalping_indicators(scalping_data, trend_data, current_price)
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