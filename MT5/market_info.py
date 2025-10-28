# 外汇对信息获取相关函数
# 此文件将包含获取市场数据、汇率信息等功能

from typing import List, Optional, Tuple

import MetaTrader5 as mt5
import pandas as pd

from utils.logger import get_trading_logger, get_error_logger, log_exception


def get_rsi(
    symbol: str, timeframe: int, period: int = 14, count: int = 100
) -> Optional[List[float]]:
    """
    获取指定外汇对在指定时间周期内的RSI指标值

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        period (int): RSI计算周期，默认为14
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[List[float]]: RSI值列表，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（多获取200根K线作为预热区）
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 200)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame并计算收盘价变化
        df = pd.DataFrame(rates)
        df["diff"] = df["close"].diff()

        # 3. 计算涨幅和跌幅（使用向量化函数.where()替换.apply()）
        df["gain"] = df["diff"].where(df["diff"] > 0, 0)
        df["loss"] = df["diff"].where(df["diff"] < 0, 0).abs()

        # 4. 计算平均涨幅和平均跌幅（使用指数平滑替换滚动平均）
        # 初始化第一期的平均值
        df.loc[period, "avg_gain"] = df["gain"][1 : period + 1].mean()
        df.loc[period, "avg_loss"] = df["loss"][1 : period + 1].mean()

        # 使用Wilder's Smoothing方法计算后续值
        for i in range(period + 1, len(df)):
            df.loc[i, "avg_gain"] = (
                df.loc[i - 1, "avg_gain"] * (period - 1) + df.loc[i, "gain"]
            ) / period
            df.loc[i, "avg_loss"] = (
                df.loc[i - 1, "avg_loss"] * (period - 1) + df.loc[i, "loss"]
            ) / period

        # 5. 计算RS值和RSI值
        df["rs"] = df["avg_gain"] / df["avg_loss"]
        df["rsi"] = 100 - (100 / (1 + df["rs"]))

        # 6. 提取有效的RSI值（去除NaN，只返回需要的最后count个数据点）
        rsi_values = df["rsi"].dropna().tail(count).tolist()

        logger.info(f"成功计算 {symbol} 的RSI指标，共 {len(rsi_values)} 个数据点")
        return rsi_values

    except Exception:
        log_exception(error_logger, f"计算 {symbol} 的RSI指标时发生异常")
        return None


def get_macd(
    symbol: str,
    timeframe: int,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    count: int = 100,
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """
    获取指定外汇对在指定时间周期内的MACD指标值

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        fast_period (int): 快速EMA周期，默认为12
        slow_period (int): 慢速EMA周期，默认为26
        signal_period (int): 信号线周期，默认为9
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[Tuple[List[float], List[float], List[float]]]: (MACD线, 信号线, 柱状图)元组，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（增加预热区）
        warmup_bars = (
            max(fast_period, slow_period, signal_period) * 3
        )  # 使用3倍最大周期作为预热区
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + warmup_bars)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算快速EMA和慢速EMA
        df["ema_fast"] = df["close"].ewm(span=fast_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow_period, adjust=False).mean()

        # 4. 计算MACD线（快速EMA - 慢速EMA）
        df["macd_line"] = df["ema_fast"] - df["ema_slow"]

        # 5. 计算信号线（MACD线的EMA）
        df["signal_line"] = df["macd_line"].ewm(span=signal_period, adjust=False).mean()

        # 6. 计算柱状图（MACD线 - 信号线）
        df["histogram"] = df["macd_line"] - df["signal_line"]

        # 7. 提取最后 count 个数据点（确保数据对齐）
        # 通过 .tail(count) 确保只返回最后 count 个值，保证三个列表长度相等且数据对齐
        macd_line = df["macd_line"].tail(count).tolist()
        signal_line = df["signal_line"].tail(count).tolist()
        histogram = df["histogram"].tail(count).tolist()

        logger.info(
            f"成功计算 {symbol} 的MACD指标，MACD线{len(macd_line)}个数据点，信号线{len(signal_line)}个数据点，柱状图{len(histogram)}个数据点"
        )
        return (macd_line, signal_line, histogram)

    except Exception:
        log_exception(error_logger, f"计算 {symbol} 的MACD指标时发生异常")
        return None


def get_atr(
    symbol: str, timeframe: int, period: int = 14, count: int = 100
) -> Optional[List[float]]:
    """
    获取指定外汇对在指定时间周期内的ATR（平均真实波幅）指标值

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        period (int): ATR计算周期，默认为14
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[List[float]]: ATR值列表，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（增加预热区）
        warmup_bars = period * 3  # 使用3倍周期作为预热区
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + warmup_bars)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算真实波幅（TR）
        # TR = max(最高价-最低价, 最高价-昨收, 昨收-最低价)
        df["tr0"] = df["high"] - df["low"]
        df["tr1"] = abs(df["high"] - df["close"].shift(1))
        df["tr2"] = abs(df["low"] - df["close"].shift(1))
        df["tr"] = df[["tr0", "tr1", "tr2"]].max(axis=1)

        # 4. 计算ATR（使用Pandas的指数加权移动平均，Wilder's Smoothing方法）
        # 使用tr.ewm(com=period - 1, adjust=False).mean()实现向量化计算，替代for循环
        # com=period - 1是实现Wilder's Smoothing的标准方式
        # adjust=False确保使用平滑公式而不是调整权重
        df["atr"] = df["tr"].ewm(com=period - 1, adjust=False).mean()

        # 5. 提取最后 count 个数据点（确保数据对齐）
        atr_values = df["atr"].tail(count).tolist()

        logger.info(f"成功计算 {symbol} 的ATR指标，共 {len(atr_values)} 个数据点")
        return atr_values

    except Exception:
        log_exception(error_logger, f"计算 {symbol} 的ATR指标时发生异常")
        return None


def get_adx(
    symbol: str, timeframe: int, period: int = 14, count: int = 100
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """
    获取指定外汇对在指定时间周期内的ADX（平均趋向指数）指标值

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        period (int): ADX计算周期，默认为14
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[Tuple[List[float], List[float], List[float]]]: (ADX值列表, +DI值列表, -DI值列表)，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（增加预热区）
        # 增加热区，因为ADX是"平滑的平滑"，需要更长时间稳定
        warmup_bars = period * 4  # 使用4倍周期作为预热区
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + warmup_bars)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算DI+和DI-（方向指标）
        # 计算价格变化
        df["up_move"] = df["high"].diff()
        df["down_move"] = -df["low"].diff()

        # 计算真实范围(TR)
        df["tr0"] = df["high"] - df["low"]
        df["tr1"] = abs(df["high"] - df["close"].shift(1))
        df["tr2"] = abs(df["low"] - df["close"].shift(1))
        df["tr"] = df[["tr0", "tr1", "tr2"]].max(axis=1)

        # 确定DI+和DI-
        df["plus_dm"] = df["up_move"].where(
            (df["up_move"] > df["down_move"]) & (df["up_move"] > 0), 0
        )
        df["minus_dm"] = df["down_move"].where(
            (df["down_move"] > df["up_move"]) & (df["down_move"] > 0), 0
        )

        # 计算平滑的DI+和DI-（使用Wilder's Smoothing）
        df["smoothed_tr"] = df["tr"].ewm(com=period - 1, adjust=False).mean()
        df["smoothed_plus_dm"] = df["plus_dm"].ewm(com=period - 1, adjust=False).mean()
        df["smoothed_minus_dm"] = (
            df["minus_dm"].ewm(com=period - 1, adjust=False).mean()
        )

        # 添加极小值epsilon避免除零错误
        epsilon = 1e-10

        # 计算DI+和DI-
        df["di_plus"] = (df["smoothed_plus_dm"] / (df["smoothed_tr"] + epsilon)) * 100
        df["di_minus"] = (df["smoothed_minus_dm"] / (df["smoothed_tr"] + epsilon)) * 100

        # 4. 计算DX（趋向指数）
        # 添加极小值epsilon避免除零错误
        df["dx"] = (
            abs(df["di_plus"] - df["di_minus"])
            / (df["di_plus"] + df["di_minus"] + epsilon)
        ) * 100

        # 5. 计算ADX（平均趋向指数）
        # 使用指数移动平均计算ADX
        df["adx"] = df["dx"].ewm(com=period - 1, adjust=False).mean()

        # 6. 提取最后 count 个数据点（确保数据对齐）
        adx_values = df["adx"].tail(count).tolist()
        di_plus_values = df["di_plus"].tail(count).tolist()
        di_minus_values = df["di_minus"].tail(count).tolist()

        logger.info(f"成功计算 {symbol} 的ADX指标，共 {len(adx_values)} 个数据点")
        return (adx_values, di_plus_values, di_minus_values)

    except Exception:
        log_exception(error_logger, f"计算 {symbol} 的ADX指标时发生异常")

        return None


def get_bollinger_bands(
    symbol: str,
    timeframe: int,
    period: int = 20,
    std_dev: float = 2.0,
    count: int = 100,
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """
    获取指定外汇对在指定时间周期内的布林带 (Bollinger Bands) 指标值

    Args:

        symbol (str): 外汇对符号，例如 "EURUSD"

        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量

        period (int): 移动平均周期，默认为20

        std_dev (float): 标准差倍数，默认为2.0

        count (int): 获取的数据点数量，默认为100



    Returns:

        Optional[Tuple[List[float], List[float], List[float]]]:

        (上轨列表, 中轨列表, 下轨列表)元组，失败时返回None

    """

    logger = get_trading_logger()

    error_logger = get_error_logger()

    # 参数验证
    if not isinstance(symbol, str) or not symbol:
        error_logger.error("外汇对符号必须是非空字符串")
        return None

    if not isinstance(timeframe, int) or timeframe <= 0:
        error_logger.error("时间周期必须是正整数")
        return None

    if not isinstance(period, int) or period <= 0:
        error_logger.error("移动平均周期必须是正整数")
        return None

    if not isinstance(std_dev, (int, float)) or std_dev <= 0:
        error_logger.error("标准差倍数必须是正数")
        return None

    if not isinstance(count, int) or count <= 0:
        error_logger.error("数据点数量必须是正整数")
        return None

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（增加预热区）
        warmup_bars = period * 2  # 使用2倍周期作为预热区
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + warmup_bars)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算中轨（移动平均线）
        df["middle_band"] = df["close"].rolling(window=period).mean()

        # 4. 计算标准差
        df["std_dev"] = df["close"].rolling(window=period).std()

        # 5. 计算上轨和下轨
        df["upper_band"] = df["middle_band"] + (df["std_dev"] * std_dev)
        df["lower_band"] = df["middle_band"] - (df["std_dev"] * std_dev)

        # 6. 提取最后 count 个数据点（确保数据对齐）
        upper_band = df["upper_band"].tail(count).tolist()
        middle_band = df["middle_band"].tail(count).tolist()
        lower_band = df["lower_band"].tail(count).tolist()

        # 7. 验证计算结果
        if len(upper_band) == 0 or len(middle_band) == 0 or len(lower_band) == 0:
            error_logger.error(f"计算 {symbol} 的布林带指标失败，返回空数据")
            return None

        logger.info(f"成功计算 {symbol} 的布林带指标，共 {len(upper_band)} 个数据点")
        return (upper_band, middle_band, lower_band)

    except Exception as e:
        log_exception(error_logger, f"计算 {symbol} 的布林带指标时发生异常")
        return None


def get_dynamic_support_resistance(
    symbol: str,
    timeframe: int,
    ma_period_1: int = 50,
    ma_period_2: int = 200,
    count: int = 100,
) -> Optional[Tuple[List[float], List[float]]]:
    """
    获取指定外汇对在指定时间周期内的动态支撑/阻力线 (MA50 和 MA200)

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        ma_period_1 (int): 第一条移动平均线周期，默认为50 (MA50)
        ma_period_2 (int): 第二条移动平均线周期，默认为200 (MA200)
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[Tuple[List[float], List[float]]]: (MA50列表, MA200列表)元组，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    # 参数验证
    if not isinstance(symbol, str) or not symbol:
        error_logger.error("外汇对符号必须是非空字符串")
        return None

    if not isinstance(timeframe, int) or timeframe <= 0:
        error_logger.error("时间周期必须是正整数")
        return None

    if not isinstance(ma_period_1, int) or ma_period_1 <= 0:
        error_logger.error("第一条移动平均线周期必须是正整数")
        return None

    if not isinstance(ma_period_2, int) or ma_period_2 <= 0:
        error_logger.error("第二条移动平均线周期必须是正整数")
        return None

    if not isinstance(count, int) or count <= 0:
        error_logger.error("数据点数量必须是正整数")
        return None

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据（增加预热区）
        # 使用最大的周期作为预热区，确保数据准确性
        max_period = max(ma_period_1, ma_period_2)
        warmup_bars = max_period * 2  # 使用2倍最大周期作为预热区
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + warmup_bars)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算MA50和MA200移动平均线
        # MA50: 50周期简单移动平均线，反映中期趋势和动态支撑/阻力
        df["ma_1"] = df["close"].rolling(window=ma_period_1).mean()

        # MA200: 200周期简单移动平均线，反映长期趋势，是牛熊分界线
        df["ma_2"] = df["close"].rolling(window=ma_period_2).mean()

        # 4. 提取最后 count 个数据点（确保数据对齐）
        ma_1_values = df["ma_1"].tail(count).tolist()
        ma_2_values = df["ma_2"].tail(count).tolist()

        # 5. 验证计算结果
        if len(ma_1_values) == 0 or len(ma_2_values) == 0:
            error_logger.error(f"计算 {symbol} 的动态支撑/阻力线指标失败，返回空数据")
            return None

        logger.info(
            f"成功获取 {symbol} 的动态支撑/阻力线指标，共 {len(ma_1_values)} 个数据点"
        )
        return (ma_1_values, ma_2_values)

    except Exception as e:
        log_exception(error_logger, f"计算 {symbol} 的动态支撑/阻力线指标时发生异常")
        return None


def get_recent_high_low(
    symbol: str, timeframe: int, count: int = 100
) -> Optional[Tuple[float, float]]:
    """
    获取指定外汇对在指定时间周期内的近期高低点

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"
        timeframe (int): 时间周期，使用MT5.TIMEFRAME_* 常量
        count (int): 获取的数据点数量，默认为100

    Returns:
        Optional[Tuple[float, float]]: (近期高点, 近期低点)元组，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    # 参数验证
    if not isinstance(symbol, str) or not symbol:
        error_logger.error("外汇对符号必须是非空字符串")
        return None

    if not isinstance(timeframe, int) or timeframe <= 0:
        error_logger.error("时间周期必须是正整数")
        return None

    if not isinstance(count, int) or count <= 0:
        error_logger.error("数据点数量必须是正整数")
        return None

    try:
        # 1. 使用mt5.copy_rates_from_pos获取价格数据
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取 {symbol} 价格数据失败, 错误代码 = {error_code}")
            return None

        # 2. 转换为DataFrame
        df = pd.DataFrame(rates)

        # 3. 计算近期高点和低点
        recent_high = df["high"].max()
        recent_low = df["low"].min()

        logger.info(
            f"成功获取 {symbol} 的近期高低点: 高点={recent_high:.5f}, 低点={recent_low:.5f}"
        )
        return (recent_high, recent_low)

    except Exception as e:
        log_exception(error_logger, f"计算 {symbol} 的近期高低点时发生异常")
        return None


def get_pivot_points(
    symbol: str,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    """
    获取指定外汇对的日内枢轴点 (Daily Pivots)
    基于前一天的 D1 (日线) K线的 H, L, C 计算

    Args:
        symbol (str): 外汇对符号，例如 "EURUSD"

    Returns:
        Optional[Tuple[float, float, float, float, float, float, float]]:
        (P, R1, S1, R2, S2, R3, S3)元组，失败时返回None
        P: 枢轴点本身
        R1, R2, R3: 阻力位1, 2, 3
        S1, S2, S3: 支撑位1, 2, 3
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    # 参数验证
    if not isinstance(symbol, str) or not symbol:
        error_logger.error("外汇对符号必须是非空字符串")
        return None

    try:
        # 1. 获取前一天的 D1 (日线) K线
        # 注意 1, 1：从第1根K线开始，获取1根，即"昨天"那根
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 1)
        if rates is None or len(rates) == 0:
            error_code = mt5.last_error()
            error_logger.error(
                f"获取 {symbol} 前一天日线数据失败, 错误代码 = {error_code}"
            )
            return None

        # 2. 从这根K线中提取 Prev_High, Prev_Low, Prev_Close
        prev_high = rates[0]["high"]
        prev_low = rates[0]["low"]
        prev_close = rates[0]["close"]

        # 3. 计算 P (Pivot Point - 枢轴点本身)
        pivot_point = (prev_high + prev_low + prev_close) / 3

        # 4. 计算 S/R (支撑/阻力)
        # R1 = (2 * P) - Prev_Low
        r1 = (2 * pivot_point) - prev_low

        # S1 = (2 * P) - Prev_High
        s1 = (2 * pivot_point) - prev_high

        # R2 = P + (Prev_High - Prev_Low)
        r2 = pivot_point + (prev_high - prev_low)

        # S2 = P - (Prev_High - Prev_Low)
        s2 = pivot_point - (prev_high - prev_low)

        # R3 = Prev_High + 2 * (P - Prev_Low)
        r3 = prev_high + 2 * (pivot_point - prev_low)

        # S3 = Prev_Low - 2 * (Prev_High - P)
        s3 = prev_low - 2 * (prev_high - pivot_point)

        logger.info(f"成功计算 {symbol} 的日内枢轴点")
        logger.info(f"  枢轴点(P): {pivot_point:.5f}")
        logger.info(f"  阻力位: R1={r1:.5f}, R2={r2:.5f}, R3={r3:.5f}")
        logger.info(f"  支撑位: S1={s1:.5f}, S2={s2:.5f}, S3={s3:.5f}")

        return (pivot_point, r1, s1, r2, s2, r3, s3)

    except Exception as e:
        log_exception(error_logger, f"计算 {symbol} 的日内枢轴点时发生异常")
        return None
