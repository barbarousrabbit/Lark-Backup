#!/usr/bin/env python3
"""
Lark (飞书) 多维表格备份程序
自动定时下载飞书多维表格数据并保存为Excel文件
支持断网自动恢复下载功能
防止程序重复启动机制
"""

import os
import sys
import logging
import time
import traceback
from datetime import datetime
import threading
import psutil

# 设置Python路径，确保能导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导入配置和自定义模块
from config import config
from core.network import with_network_retry
from core.api_service import api_service
from core.file_manager import init_file_manager
from core.scheduler import task_scheduler
from core.notification import show_notification
from core.process_manager import init_single_instance_manager
from core.retry_manager import retry_manager
from core.data_comparator import init_data_comparator
from core.alert_window import alert_manager
from core.report_generator import init_report_generator

# 全局实例管理器
_instance_manager = None

# 设置日志配置
def setup_logging():
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            # 如果创建目录失败，打印到控制台并继续，日志可能无法写入文件
            print(f"Error creating log directory {log_dir}: {e}", file=sys.stderr)
            
    # 清除所有现有处理器
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 创建文件处理器，设置为立即刷新
    try:
        file_handler = logging.FileHandler(config.LOG_FILE, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - PID:%(process)d - %(levelname)s - %(message)s'))
    except Exception as e:
        print(f"Warning: Cannot create log file handler: {e}", file=sys.stderr)
        file_handler = None
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - PID:%(process)d - %(levelname)s - %(message)s'))
    
    # 配置根日志器
    logging.root.setLevel(logging.INFO)
    if file_handler:
        logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)
    
    # 确保日志立即写入
    logging.info("📝 Logging initialized")
    # 手动刷新所有处理器
    for handler in logging.root.handlers:
        handler.flush()
    
    if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# 设置控制台编码
def setup_console_encoding():
    """设置控制台编码"""
    if sys.platform.startswith('win'):
        try:
            os.system('chcp 65001 > nul')
        except:
            pass

@with_network_retry
def backup_task():
    """执行备份任务的主函数"""
    backup_details = {
        'backup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'attempts': 1
    }
    
    try:
        logging.info("🔄 Starting backup")
        file_manager = init_file_manager()
        file_manager.ensure_download_dir_exists()
        
        try:
            tenant_token = api_service.get_tenant_token()
            if not tenant_token:
                logging.error("❌ API token failed")
                return False
            wiki_data = api_service.get_wiki_data()
            if not wiki_data:
                logging.error("❌ Wiki data failed")
                return False
            try:
                obj_token = api_service.extract_obj_token(wiki_data)
            except ValueError as e:
                logging.error(f"❌ {str(e)}")
                return False
            ticket = api_service.create_export_task(obj_token)
            if not ticket:
                logging.error("❌ Export task failed")
                return False
            file_token = api_service.get_export_task_status(ticket, obj_token)
            if not file_token:
                logging.error("❌ File token failed")
                return False
            file_content = api_service.download_file(file_token)
            if not file_content:
                logging.error("❌ Download failed")
                return False
            backup_date = config.get_backup_date()
            saved_path = file_manager.save_file(file_content, backup_date)
            
            if saved_path:
                logging.info(f"✅ Backup completed! File: {saved_path}")
                
                # 更新备份详情
                backup_details['file_path'] = saved_path
                backup_details['success'] = True
                
                # 获取文件大小
                try:
                    backup_details['file_size'] = os.path.getsize(saved_path)
                except:
                    pass
                
                # 执行数据对比
                comparison_result = None
                comparison_warnings = []
                
                try:
                    logging.info("🔍 Starting data comparison")
                    comparator = init_data_comparator(config.DOWNLOAD_DIR)
                    differences, warnings = comparator.compare_with_previous_date(backup_date)
                    
                    comparison_result = differences
                    comparison_warnings = warnings
                    
                    if warnings:
                        logging.warning(f"⚠️ Data comparison found {len(warnings)} warnings")
                        # 显示警告窗口
                        alert_manager.check_and_show_alert(differences, warnings, backup_date)
                        
                    # 保存对比结果
                    if differences:
                        comparator.save_comparison_result(backup_date, {
                            'differences': differences,
                            'warnings': warnings
                        })
                    
                    # 显示对比成功通知
                    if warnings:
                        show_notification("Data Comparison Alert", 
                                        f"Found {len(differences)} changes, {len(warnings)} warnings", "warning")
                    elif differences:
                        show_notification("Data Comparison Complete", 
                                        f"Found {len(differences)} changes, no warnings", "info")
                    else:
                        show_notification("Data Comparison Complete", "No significant changes detected", "info")
                        
                except Exception as e:
                    logging.error(f"❌ Data comparison failed: {e}")
                    # 对比失败不影响备份成功状态
                
                # 生成每日报告
                try:
                    logging.info("📝 Generating daily report")
                    report_gen = init_report_generator(config.DOWNLOAD_DIR)
                    report_path = report_gen.generate_daily_report(
                        backup_date,
                        True,  # 备份成功
                        backup_details,
                        comparison_result,
                        comparison_warnings
                    )
                    if report_path:
                        logging.info(f"✅ Report generated: {report_path}")
                except Exception as e:
                    logging.error(f"❌ Report generation failed: {e}")
                
                # 显示备份成功通知
                show_notification("Backup Successful", f"Data backup completed: {os.path.basename(saved_path)}", "success")
                
                return True
            else:
                logging.error("❌ Save failed")
                backup_details['success'] = False
                backup_details['error'] = "Failed to save file"
                
                # 生成失败报告
                try:
                    backup_date = config.get_backup_date()
                    report_gen = init_report_generator(config.DOWNLOAD_DIR)
                    report_gen.generate_daily_report(
                        backup_date,
                        False,  # 备份失败
                        backup_details,
                        None,
                        None
                    )
                except:
                    pass
                
                # 不在这里发送通知，在重试函数中处理通知
                return False
        except Exception as e:
            logging.error(f"❌ Backup error: {str(e)}")
            logging.error(traceback.format_exc())
            
            backup_details['success'] = False
            backup_details['error'] = str(e)
            
            # 生成失败报告
            try:
                backup_date = config.get_backup_date()
                report_gen = init_report_generator(config.DOWNLOAD_DIR)
                report_gen.generate_daily_report(
                    backup_date,
                    False,  # 备份失败
                    backup_details,
                    None,
                    None
                )
            except:
                pass
            
            # 不在这里发送通知，在重试函数中处理通知
            return False
    finally:
        pass

def run_backup_task():
    """执行备份任务（无重试）"""
    logging.info("🔄 Single backup execution")
    result = backup_task()
    if result:
        logging.info("✅ Backup completed")
    else:
        logging.error("❌ Backup failed")
    return result

def run_backup_with_retry():
    """执行备份任务（带每日重试机制）"""
    
    # 检查今天是否还可以尝试
    if not retry_manager.can_attempt_today():
        remaining = retry_manager.get_remaining_attempts()
        logging.warning(f"⚠️ Daily limit reached ({config.MAX_DAILY_ATTEMPTS} attempts), cannot attempt again")
        show_notification("Daily Limit Reached", "All backup attempts exhausted for today", "error")
        
        # 生成失败报告（所有尝试都失败）
        try:
            backup_date = config.get_backup_date()
            report_gen = init_report_generator(config.DOWNLOAD_DIR)
            report_gen.generate_daily_report(
                backup_date,
                False,  # 备份失败
                {'error': f'All {config.MAX_DAILY_ATTEMPTS} attempts failed', 'attempts': config.MAX_DAILY_ATTEMPTS},
                None,
                None
            )
        except:
            pass
            
        return False
    
    # 执行备份任务
    logging.info("🔄 Starting backup with retry mechanism")
    result = backup_task()
    
    # 记录尝试结果
    attempt_count = retry_manager.record_attempt(success=result)
    
    if result:
        logging.info("✅ Backup completed")
        # 不在这里发送通知，在backup_task函数中已经发送了
        return True
    else:
        # 备份失败，检查是否还可以重试
        remaining = retry_manager.get_remaining_attempts()
        
        if remaining > 0:
            logging.warning(f"❌ Failed, remaining {remaining} attempts left")
            # 不显示重试通知，避免过多弹窗
            
            # Waiting一段时间后重试
            retry_delay = config.ERROR_RETRY_INTERVAL
            logging.info(f"⏱️ Waiting {retry_delay} s before retry")
            time.sleep(retry_delay)
            
            # 递归重试
            return run_backup_with_retry()
        else:
            logging.error(f"❌ Daily attempts exhausted ({config.MAX_DAILY_ATTEMPTS} times)")
            show_notification("Backup Failed", f"All {config.MAX_DAILY_ATTEMPTS} attempts failed today", "error")
            
            # 生成最终失败报告
            try:
                backup_date = config.get_backup_date()
                report_gen = init_report_generator(config.DOWNLOAD_DIR)
                report_gen.generate_daily_report(
                    backup_date,
                    False,  # 备份失败
                    {'error': f'All {config.MAX_DAILY_ATTEMPTS} attempts failed', 'attempts': config.MAX_DAILY_ATTEMPTS},
                    None,
                    None
                )
            except:
                pass
                
            return False

def _run_initial_backup_task():
    """在独立线程中运行初始备份任务（带重试）"""
    logging.info("🚀 Initial backup started")
    run_backup_with_retry()
    logging.info("✅ Initial backup completed")

def main_logic():
    """包含核心业务逻辑"""
    logging.info(f"⚙️ Main logic, PID: {os.getpid()}")

    # 智能重置：如果是手动启动，重置今日重试次数
    retry_manager.reset_if_manual_start()

    # 设置并启动任务调度器
    task_scheduler.schedule_daily_task(lambda: run_backup_with_retry())
    
    # 启动初始备份任务
    logging.info("🔄 Preparing initial backup")
    initial_backup_thread = threading.Thread(
        target=_run_initial_backup_task,
        daemon=True,
        name="Initial-Backup-Thread"
    )
    initial_backup_thread.start()

    # 启动调度器
    task_scheduler.start(run_now=False)
    
    logging.info(f"✅ Main logic completed, PID: {os.getpid()}. Program is now running in background.")

def main():
    """程序入口点"""
    global _instance_manager
    
    # 确保在任何操作前设置好日志
    setup_logging()
    # 在启动初期记录一个明确的日志，包含PID
    logging.info(f"🏁 Entry point, PID: {os.getpid()}, Args: {sys.argv}")
    
    # 初始化单例管理器并启动(如有旧实例会终止它)
    _instance_manager = init_single_instance_manager()
    _instance_manager.start()
    
    try:
        setup_console_encoding()
        logging.info("🚀 Program starting")
        
        # 核心业务逻辑
        main_logic()
        
        # 保持程序运行的主循环
        try:
            while True:
                time.sleep(60)  # 优化：改为60秒检查一次，进一步降低资源消耗
                if time.time() % 3600 < 60: # 大约每小时记录一次（容差60秒）
                    active_threads = threading.enumerate()
                    thread_names = [t.name for t in active_threads]
                    logging.info(f"ℹ️ Heartbeat, PID: {os.getpid()}, Active threads: {len(active_threads)}")
                    
                    # 记录子进程信息
                    try:
                        current_process = psutil.Process(os.getpid())
                        children = current_process.children(recursive=True)
                        if children:
                            child_info = [f"{c.name()}(PID:{c.pid})" for c in children]
                            logging.info(f"ℹ️ Current child processes: {child_info}")
                    except Exception as e:
                        logging.error(f"❌ Error getting child process info: {str(e)}")
        except KeyboardInterrupt:
            logging.info("🛑 Interrupted by user")
            show_notification("Program Stopped", "Backup service stopped")
            
    except SystemExit as e: # 捕获由 sys.exit() 引发的退出
        logging.info(f"ℹ️ Program exiting with SystemExit code: {e.code}")
        return e.code
    except Exception as e:
        logging.error(f"❌ Critical error in main: {str(e)}", exc_info=True)
        try:
            show_notification("Critical Error", "Program error occurred")
        except Exception as notify_err:
            logging.error(f"❌ Failed to show critical error notification: {notify_err}")
        return 1
    finally:
        logging.info(f"🚪 Main function ending, PID {os.getpid()} cleaning up...")
        # 确保日志刷新到磁盘
        for handler in logging.root.handlers:
            handler.flush()
            
        # 停止调度器
        if 'task_scheduler' in globals() and task_scheduler.scheduler_thread is not None:
            task_scheduler.stop()
        logging.info(f"🧼 Cleanup finished, PID {os.getpid()}.")
            
    return 0

if __name__ == "__main__":
    # 确保日志在最开始就被设置，即使在 __main__ 块中
    setup_logging() 
    logging.info(f"🎬 Script started, PID: {os.getpid()}")
    exit_code = main()
    logging.info(f"👋 Terminated, exit code: {exit_code}. PID: {os.getpid()}")
    sys.exit(exit_code)
