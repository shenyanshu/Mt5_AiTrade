from MT5.init import (
    initialize_mt5,
    get_account_info,
    get_terminal_info,
    shutdown_mt5,
    check_connection,
)
from config.config_manager import get_config_manager
from utils.logger import get_app_logger, get_trading_logger, log_exception
from AI.prompts import get_user_prompt
import MetaTrader5 as mt5
from datetime import datetime
import time
from datetime import timedelta
import pytz


def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)


def format_next_call_time(interval_seconds):
    """计算并格式化下次调用时间（北京时间）"""
    now = get_beijing_time()
    next_time = now + timedelta(seconds=interval_seconds)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")


def main():
    # 初始化日志系统（必须在导入完成后调用）
    from utils.logger import initialize_logging
    initialize_logging()

    # 获取日志记录器
    app_logger = get_app_logger()
    trading_logger = get_trading_logger()

    # 加载配置文件
    config_manager = get_config_manager()
    magic_number = config_manager.get("trading.magic_number", 100001)
    ai_analysis_interval = config_manager.get("ai.analysis_interval", 60)
    ai_retry_interval = config_manager.get("ai.retry_interval", 5)
    app_logger.info(f"加载配置: 魔数 = {magic_number}, AI分析间隔 = {ai_analysis_interval}秒, 重试间隔 = {ai_retry_interval}秒")

    app_logger.info("=== AITrade_MT5 程序启动 ===")

    try:
        # 初始化MT5连接
        if not initialize_mt5():
            app_logger.error("MT5初始化失败，程序退出")
            return

        # 检查连接状态
        connected, status = check_connection()
        app_logger.info(f"连接状态: {status}")

        if connected:
            # 获取终端信息
            terminal_info = get_terminal_info()
            if terminal_info:
                app_logger.info("=== 终端信息 ===")
                for key, value in terminal_info.items():
                    app_logger.info(f"{key}: {value}")

            # 获取账户信息
            account_info = get_account_info()
            if account_info:
                app_logger.info("=== 账户信息 ===")
                for key, value in account_info.items():
                    app_logger.info(f"{key}: {value}")

            # 初始化AI交易系统
            app_logger.info("=== 初始化AI交易系统 ===")

            # 导入AI交易相关模块
            from AI.trading import analyze_market, execute_trading_plan
            from AI.prompts import get_ai_system_prompt

            # 初始化止盈监控系统
            app_logger.info("=== 初始化止盈监控系统 ===")
            from AI.position_monitor import start_take_profit_monitoring, stop_take_profit_monitoring, get_monitoring_status

            # 启动止盈监控
            monitor_started = start_take_profit_monitoring()
            if monitor_started:
                app_logger.info("✅ 止盈监控系统启动成功")
                print("🔍 止盈实时监控已启用 (1秒检测间隔)")
            else:
                app_logger.warning("⚠️ 止盈监控系统启动失败或已禁用")
                print("⚠️ 止盈监控未启用")

            # 显示启动时间（北京时间）
            beijing_time = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")

            print("\n" + "="*60)
            print("🚀 AI趋势跟踪交易系统已启动")
            print(f"🕐 启动时间: {beijing_time} (北京时间)")
            print(f"⚡ 每{ai_analysis_interval}秒分析市场，捕捉5-30分钟趋势机会")
            print("💰 策略：精选高质量信号，耐心持仓")
            if monitor_started:
                print("🔍 止盈实时监控：已启用 (1秒检测间隔)")
            print("="*60 + "\n")

            # 主循环：每分钟执行一次AI分析
            loop_count = 0
            next_interval = ai_analysis_interval  # 初始化间隔
            while True:
                try:
                    loop_count += 1
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    app_logger.info(f"=== 第{loop_count}轮AI分析开始 [{current_time}] ===")

                    # 获取系统提示词
                    system_prompt = get_ai_system_prompt()

                    # 调用AI分析（带重试机制）
                    analysis_result = None
                    max_retries = 3
                    retry_count = 0

                    while retry_count < max_retries and analysis_result is None:
                        try:
                            retry_count += 1
                            data_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            app_logger.info(f"正在进行AI分析尝试 {retry_count}/{max_retries}...")
                            app_logger.info(f"正在获取最新市场数据 [{data_refresh_time}]...")

                            # 获取用户提示词（包含最新市场数据）- 每次重试都刷新
                            user_prompt = get_user_prompt()

                            if not user_prompt:
                                app_logger.error(f"获取市场数据失败 (尝试 {retry_count}/{max_retries})")
                                if retry_count < max_retries:
                                    app_logger.info(f"等待{ai_retry_interval}秒后重试...")
                                    time.sleep(ai_retry_interval)
                                continue

                            app_logger.info(f"市场数据获取成功 [{data_refresh_time}]")

                            # 调用AI分析
                            analysis_result = analyze_market(system_prompt, user_prompt)

                            if analysis_result:
                                app_logger.info("✅ AI分析成功完成")

                                # 记录分析结果
                                recommendations = analysis_result.get('recommendations', [])
                                app_logger.info(f"AI生成了 {len(recommendations)} 个交易建议")

                                # 显示交易建议
                                if recommendations:
                                    print(f"\n📊 AI交易建议 [{current_time}]:")
                                    print("-" * 40)
                                    for i, rec in enumerate(recommendations, 1):
                                        symbol = rec.get('symbol')
                                        action = rec.get('action')
                                        volume = rec.get('volume')
                                        comment = rec.get('comment', '')
                                        reasoning = rec.get('reasoning', '')

                                        print(f"{i}. {symbol} {action} {volume} - {comment}")
                                        print(f"   理由: {reasoning[:80]}...")
                                        print("-" * 40)
                                else:
                                    print(f"\n⚠️ AI建议: 暂时观望，等待更好的机会 [{current_time}]")

                                # 获取AI建议的下次调用间隔
                                next_interval = analysis_result.get('next_call_interval')
                                interval_reason = analysis_result.get('interval_reason', 'AI建议')

                                # 处理动态间隔逻辑
                                if next_interval is not None and isinstance(next_interval, (int, float)):
                                    # 确保间隔不超过配置的最大值
                                    if next_interval < 0:
                                        next_interval = ai_analysis_interval
                                        app_logger.warning(f"AI返回了负数间隔，使用配置间隔: {ai_analysis_interval}秒")
                                    elif next_interval > ai_analysis_interval:
                                        app_logger.info(f"AI建议间隔{next_interval}秒超过配置值{ai_analysis_interval}秒，使��配置间隔")
                                        next_interval = ai_analysis_interval
                                    else:
                                        app_logger.info(f"AI动态调整分析间隔为: {next_interval}秒 - {interval_reason}")
                                else:
                                    next_interval = ai_analysis_interval
                                    app_logger.info(f"AI未返回间隔建议，使用默认配置间隔: {ai_analysis_interval}秒")

                                # 显示AI的间隔建议（如果有）
                                if next_interval != ai_analysis_interval:
                                    next_call_time_beijing = format_next_call_time(next_interval)
                                    print(f"\n🤖 AI智能调整: 下次分析将在{next_interval}秒后进行 ({interval_reason})")
                                    print(f"🕐 下次调用时间: {next_call_time_beijing} (北京时间)")

                                # 执行交易计划
                                if recommendations:
                                    app_logger.info("开始执行AI交易建议...")
                                    execution_results = execute_trading_plan(analysis_result)

                                    # 统计执行结果
                                    successful_trades = sum(1 for result in execution_results if result.get('success'))
                                    total_trades = len(execution_results)

                                    print(f"\n💼 交易执行结果: 成功 {successful_trades}/{total_trades} 笔")

                                    if successful_trades > 0:
                                        print("✅ 成功执行的交易:")
                                        for result in execution_results:
                                            if result.get('success'):
                                                symbol = result.get('symbol')
                                                action = result.get('action')
                                                ticket = result.get('order_ticket')
                                                print(f"   - {symbol} {action} (订单号: {ticket})")

                                break  # 分析成功，跳出重试循环
                            else:
                                app_logger.warning("AI分析返回空结果")

                        except Exception as analyze_error:
                            app_logger.error(f"AI分析失败 (尝试 {retry_count}/{max_retries}): {analyze_error}")
                            if retry_count < max_retries:
                                progressive_wait = retry_count * ai_retry_interval
                                app_logger.info(f"等待 {progressive_wait} 秒后重试...")
                                time.sleep(progressive_wait)  # 递增等待时间

                    if analysis_result is None:
                        app_logger.error(f"AI分析在 {max_retries} 次尝试后仍然失败")
                        next_call_time_beijing = format_next_call_time(ai_analysis_interval)
                        print(f"\n❌ AI分析失败，将在{ai_analysis_interval}秒后继续尝试 [{current_time}]")
                        print(f"🕐 下次调用时间: {next_call_time_beijing} (北京时间)")
                        next_interval = ai_analysis_interval  # 分析失败时使用默认间隔
                    else:
                        # AI分析成功，已经获取了next_interval
                        pass

                    app_logger.info(f"=== 第{loop_count}轮AI分析完成 ===")

                    # 计算下次调用时间（北京时间）
                    next_call_time_beijing = format_next_call_time(next_interval)

                    print(f"\n⏰ 等待{next_interval}秒后进行下次分析... (当前轮次: {loop_count})")
                    print(f"🕐 下次调用时间: {next_call_time_beijing} (北京时间)")
                    print("=" * 60 + "\n")

                    # 等待动态间隔时间
                    time.sleep(next_interval)

                except KeyboardInterrupt:
                    app_logger.info("检测到用户中断，正在停止AI交易系统...")

                    # 停止止盈监控
                    app_logger.info("正在停止止盈监控系统...")
                    if stop_take_profit_monitoring():
                        app_logger.info("✅ 止盈监控系统已停止")
                        print("🔍 止盈实时监控已停止")
                    else:
                        app_logger.warning("⚠️ 止盈监控系统停止失败")

                    print("\n🛑 AI交易系统已停止")
                    break
                except Exception as loop_error:
                    app_logger.error(f"主循环发生异常: {loop_error}")
                    import traceback
                    app_logger.error(f"详细错误: {traceback.format_exc()}")
                    next_call_time_beijing = format_next_call_time(ai_analysis_interval)
                    print(f"\n⚠️ 系统异常，但将在{ai_analysis_interval}秒后继续运行...")
                    print(f"🕐 下次调用时间: {next_call_time_beijing} (北京时间)")
                    next_interval = ai_analysis_interval  # 异常时重置为默认间隔
                    time.sleep(next_interval)  # 出错后等待间隔时间继续


        else:
            app_logger.error("MT5连接失败，程序退出")
            return

    except Exception as e:
        log_exception(app_logger, "程序运行过程中发生未处理的异常")
        print(f"\n❌ 程序发生异常: {e}")
        # 尝试优雅关闭
        try:
            shutdown_mt5()
            print("🔌 MT5连接已关闭")
        except:
            pass
        print("=== 程序结束 ===")


if __name__ == "__main__":
    main()
