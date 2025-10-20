"""
调度模块
处理定时任务调度和进程监控
"""

import threading
import time
import logging
import schedule
import psutil
import os
from datetime import datetime, timedelta

# 导入配置
from config import config

class TaskScheduler:
    """任务调度器，管理定时任务执行"""
    
    def __init__(self, schedule_time=config.SCHEDULE_TIME):
        """初始化调度器"""
        self.schedule_time = schedule_time
        self.stop_event = threading.Event()
        self.scheduler_thread = None
        self.process_monitor_thread = None
        self._scheduled_task = None  # 存储注册的任务函数
    
    def schedule_daily_task(self, task_func):
        """设置每日定时任务"""
        logging.info(f"📅 Daily task scheduled at {self.schedule_time}")
        schedule.every().day.at(self.schedule_time).do(task_func)
        self._scheduled_task = task_func  # 保存任务函数引用
        
        # 返回任务，便于测试
        return schedule.jobs[-1]
    
    def run_immediately(self, task_func):
        """立即执行一次任务"""
        logging.info("🔄 Executing task immediately")
        try:
            return task_func()
        except Exception as e:
            logging.error(f"❌ Error executing immediate task: {e}")
            return None
    
    def start(self, run_now=True):
        """
        启动调度器
        参数:
            run_now: 是否立即执行一次任务
        """
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logging.warning("⚠️ Scheduler is already running")
            return
            
        self.stop_event.clear()
        
        # 如果设置了run_now=True且有注册的任务，则立即执行一次
        if run_now and self._scheduled_task:
            logging.info("🔄 Running backup task on startup as requested")
            # 在新线程中执行，避免阻塞启动过程
            immediate_thread = threading.Thread(
                target=self.run_immediately,
                args=(self._scheduled_task,),
                daemon=True
            )
            immediate_thread.start()
        
        # 启动调度线程 - 设置为非守护线程确保程序不会在主线程结束时退出
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=False  # 改为非守护线程
        )
        self.scheduler_thread.start()
        
        # 记录下一次计划执行的时间
        next_job = None
        for job in schedule.jobs:
            if not next_job or (job.next_run and job.next_run < next_job.next_run):
                next_job = job
                
        if next_job and next_job.next_run:
            logging.info(f"⏰ Next scheduled execution time: {next_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return self.scheduler_thread
    
    def stop(self):
        """停止调度器"""
        self.stop_event.set()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=1.0)
            
        if self.process_monitor_thread and self.process_monitor_thread.is_alive():
            self.process_monitor_thread.join(timeout=1.0)
            
        logging.info("✅ Scheduler stopped")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        # 记录上次记录日志的时间
        last_log_time = datetime.now()
        
        # 使用动态休眠时间优化CPU使用
        while not self.stop_event.is_set():
            # 运行待执行的任务
            schedule.run_pending()
            
            # 计算到下一个任务的时间
            next_run = self._calculate_next_run_seconds()
            
            # 每小时记录一次日志，确认调度器仍在运行
            now = datetime.now()
            if (now - last_log_time).total_seconds() >= 3600:  # 1小时
                next_job = None
                for job in schedule.jobs:
                    if not next_job or (job.next_run and job.next_run < next_job.next_run):
                        next_job = job
                
                if next_job and next_job.next_run:
                    logging.info(f"🔄 Scheduler running, next execution time: {next_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logging.info("🔄 Scheduler running, but no tasks scheduled")
                    
                last_log_time = now
            
            # 动态设置休眠时间
            sleep_time = min(next_run, config.SCHEDULE_CHECK_INTERVAL)
            
            # 可中断的休眠
            self.stop_event.wait(timeout=sleep_time)
    
    def _calculate_next_run_seconds(self):
        """计算到下一个调度任务的秒数"""
        # 默认检查间隔
        default_interval = config.SCHEDULE_CHECK_INTERVAL
        
        # 找出下一个要运行的任务
        next_job = None
        for job in schedule.jobs:
            next_run = job.next_run
            if next_run and (next_job is None or next_run < next_job.next_run):
                next_job = job
        
        if next_job is None:
            return default_interval
        
        # 计算到下一次运行的秒数
        if next_job.next_run:
            now = datetime.now()
            time_delta = (next_job.next_run - now).total_seconds()
            return max(1, min(time_delta, default_interval))
        
        return default_interval
    
    def _start_process_monitor(self):
        """启动进程监控线程 - 在进程替换模式下不做任何操作"""
        logging.info("ℹ️ Process monitoring disabled (using PID file for process management)")
        return
    
    def _process_monitor_loop(self):
        """进程监控循环 - 在多实例模式下不做任何操作"""
        pass

# 创建全局调度器实例
task_scheduler = TaskScheduler() 