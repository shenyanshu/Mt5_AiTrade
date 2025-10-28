# -*- coding: utf-8 -*-

"""
简化的价格格式定义
使用简单的字典结构，避免过度抽象
"""


def validate_signal_format(signal_data: dict) -> bool:
    """
    验证简化信号格式的有效性

    Args:
        signal_data: 信号数据字典

    Returns:
        bool: 格式是否有效
    """
    try:
        required_fields = ["symbol", "action", "volume"]
        for field in required_fields:
            if field not in signal_data:
                return False

        # 验证action
        valid_actions = ["BUY", "SELL", "CLOSE", "CANCEL", "MODIFY", "HOLD"]
        if signal_data["action"] not in valid_actions:
            return False

        # 验证volume
        if signal_data["volume"] <= 0:
            return False

        return True

    except Exception:
        return False


# 简化的AI响应格式���例
SIMPLE_AI_RESPONSE_EXAMPLE = {
    "recommendations": [
        {
            "symbol": "XAUUSDm",
            "action": "BUY",
            "order_type": "MARKET",
            "volume": 0.01,
            "entry_offset_points": 0,
            "stop_loss_points": 20,
            "take_profit_points": 30,
            "comment": "AI做多黄金",
            "reasoning": "黄金突破关键阻力位"
        }
    ]
}