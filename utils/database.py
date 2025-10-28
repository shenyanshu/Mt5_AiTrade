"""
数据库模块
提供SQLite数据库操作功能，用于存储和管理订单注释等信息
"""

import os
import sqlite3
import threading
from typing import Optional

from utils.logger import get_app_logger, get_error_logger, log_exception

# 数据库文件路径
DB_PATH = "data/comments.db"

# 线程锁，确保数据库操作的线程安全
_db_lock = threading.Lock()

# 全局连接对象
_db_connection = None


def get_db_connection() -> sqlite3.Connection:
    """
    获取数据库连接（单例模式）

    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    global _db_connection

    if _db_connection is None:
        # 确保数据目录存在
        data_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # 创建数据库连接
        _db_connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row  # 使结果可以通过列名访问

    return _db_connection


def init_database() -> bool:
    """
    初始化数据库和表结构

    Returns:
        bool: 初始化是否成功
    """
    logger = get_app_logger()
    error_logger = get_error_logger()

    try:
        with _db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 创建订单注释表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_comments (
                    ticket INTEGER PRIMARY KEY,
                    full_comment TEXT NOT NULL,
                    created_time INTEGER NOT NULL,
                    updated_time INTEGER NOT NULL
                )
            """
            )

            # 提交更改
            conn.commit()

            logger.info("数据库初始化成功")
            return True

    except Exception as e:
        log_exception(error_logger, "数据库初始化失败")
        return False


def save_order_comment(ticket: int, comment: str) -> bool:
    """
    保存订单注释到数据库

    Args:
        ticket (int): 订单号
        comment (str): 完整注释内容

    Returns:
        bool: 保存是否成功
    """
    logger = get_app_logger()
    error_logger = get_error_logger()

    try:
        with _db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()

            import time

            current_time = int(time.time())

            # 使用INSERT OR REPLACE确保可以更新已存在的记录
            cursor.execute(
                """
                INSERT OR REPLACE INTO order_comments 
                (ticket, full_comment, created_time, updated_time)
                VALUES (?, ?, ?, ?)
            """,
                (ticket, comment, current_time, current_time),
            )

            conn.commit()

            logger.debug(f"订单 {ticket} 的注释已保存到数据库")
            return True

    except Exception as e:
        log_exception(error_logger, f"保存订单 {ticket} 注释失败")
        return False


def get_order_comment(ticket: int) -> Optional[str]:
    """
    从数据库获取订单注释

    Args:
        ticket (int): 订单号

    Returns:
        Optional[str]: 完整注释内容，如果未找到则返回None
    """
    logger = get_app_logger()
    error_logger = get_error_logger()

    try:
        with _db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT full_comment FROM order_comments WHERE ticket = ?
            """,
                (ticket,),
            )

            result = cursor.fetchone()

            if result:
                logger.debug(f"从数据库获取订单 {ticket} 的注释成功")
                return result[0]
            else:
                logger.debug(f"数据库中未找到订单 {ticket} 的注释")
                return None

    except Exception as e:
        log_exception(error_logger, f"获取订单 {ticket} 注释失败")
        return None


def update_order_comment(ticket: int, comment: str) -> bool:
    """
    更新订单注释

    Args:
        ticket (int): 订单号
        comment (str): 新的注释内容

    Returns:
        bool: 更新是否成功
    """
    logger = get_app_logger()
    error_logger = get_error_logger()

    try:
        with _db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()

            import time

            current_time = int(time.time())

            cursor.execute(
                """
                UPDATE order_comments 
                SET full_comment = ?, updated_time = ?
                WHERE ticket = ?
            """,
                (comment, current_time, ticket),
            )

            conn.commit()

            if cursor.rowcount > 0:
                logger.debug(f"订单 {ticket} 的注释已更新")
                return True
            else:
                logger.warning(f"未找到订单 {ticket} 进行注释更新")
                return False

    except Exception as e:
        log_exception(error_logger, f"更新订单 {ticket} 注释失败")
        return False


def delete_order_comment(ticket: int) -> bool:
    """
    删除订单注释

    Args:
        ticket (int): 订单号

    Returns:
        bool: 删除是否成功
    """
    logger = get_app_logger()
    error_logger = get_error_logger()

    try:
        with _db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM order_comments WHERE ticket = ?
            """,
                (ticket,),
            )

            conn.commit()

            if cursor.rowcount > 0:
                logger.debug(f"订单 {ticket} 的注释已删除")
                return True
            else:
                logger.warning(f"未找到订单 {ticket} 进行注释删除")
                return False

    except Exception as e:
        log_exception(error_logger, f"删除订单 {ticket} 注释失败")
        return False


def close_database():
    """
    关闭数据库连接
    """
    global _db_connection

    if _db_connection:
        _db_connection.close()
        _db_connection = None


# 初始化数据库
init_database()
