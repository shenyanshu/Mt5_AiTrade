from typing import Optional, Tuple

import MetaTrader5 as mt5

from utils.logger import get_trading_logger, get_error_logger, log_exception


def initialize_mt5() -> bool:
    """
    初始化MetaTrader 5连接

    Returns:
        bool: 连接是否成功
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        if not mt5.initialize():
            error_code = mt5.last_error()
            error_logger.error(f"MT5初始化失败, 错误代码 = {error_code}")
            return False

        logger.info("MetaTrader 5 连接成功")
        logger.info(f"MT5版本: {mt5.version()}")
        return True
    except Exception as e:
        log_exception(error_logger, "MT5初始化过程中发生异常")
        return False


def login_mt5(login: int, password: str, server: str) -> bool:
    """
    登录到MetaTrader 5交易账户

    Args:
        login (int): 账户号码
        password (str): 账户密码
        server (str): 交易服务器名称

    Returns:
        bool: 登录是否成功
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        if not mt5.login(login, password=password, server=server):
            error_code = mt5.last_error()
            error_logger.error(f"登录账户 {login} 失败, 错误代码 = {error_code}")
            return False

        logger.info(f"成功登录账户 {login}")
        return True
    except Exception as e:
        log_exception(error_logger, f"登录账户 {login} 过程中发生异常")
        return False


def get_account_info() -> Optional[dict]:
    """
    获取账户信息

    Returns:
        dict: 账户信息字典，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        account_info = mt5.account_info()
        if account_info is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取账户信息失败, 错误代码 = {error_code}")
            return None

        account_data = {
            "login": account_info.login,
            "server": account_info.server,
            "currency": account_info.currency,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "margin": account_info.margin,
            "free_margin": account_info.margin_free,
            "margin_level": account_info.margin_level,
        }

        logger.info(
            f"成功获取账户信息: 账户 {account_data['login']}, 余额 {account_data['balance']} {account_data['currency']}"
        )
        return account_data
    except Exception as e:
        log_exception(error_logger, "获取账户信息过程中发生异常")
        return None


def get_terminal_info() -> Optional[dict]:
    """
    获取终端信息

    Returns:
        dict: 终端信息字典，失败时返回None
    """
    logger = get_trading_logger()
    error_logger = get_error_logger()

    try:
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            error_code = mt5.last_error()
            error_logger.error(f"获取终端信息失败, 错误代码 = {error_code}")
            return None

        terminal_data = {
            "name": terminal_info.name,
            "path": terminal_info.path,
            "version": terminal_info.build,  # 使用build属性作为版本信息
            "build": terminal_info.build,
            "company": terminal_info.company,
        }

        logger.info(
            f"成功获取终端信息: {terminal_data['name']} 版本 {terminal_data['build']}"
        )
        return terminal_data
    except Exception as e:
        log_exception(error_logger, "获取终端信息过程中发生异常")
        return None


def shutdown_mt5() -> None:
    """
    关闭MetaTrader 5连接
    """
    logger = get_trading_logger()

    try:
        mt5.shutdown()
        logger.info("MetaTrader 5 连接已关闭")
    except Exception as e:
        log_exception(logger, "关闭MT5连接时发生异常")


def check_connection() -> Tuple[bool, str]:
    """
    检查MT5连接状态

    Returns:
        Tuple[bool, str]: (连接状态, 状态信息)
    """
    logger = get_trading_logger()

    try:
        if not mt5.terminal_info():
            logger.warning("MT5终端未连接")
            return False, "MT5终端未连接"

        account_info = mt5.account_info()
        if not account_info:
            logger.warning("未登录账户")
            return False, "未登录账户"

        logger.debug(f"连接状态检查: 已连接账户 {account_info.login}")
        return True, f"已连接账户 {account_info.login}"
    except Exception as e:
        log_exception(logger, "检查连接状态时发生异常")
        return False, "检查连接状态时发生异常"
