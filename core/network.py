"""
网络模块
处理网络连接检测和恢复逻辑
"""

import socket
import time
import threading
import logging
from functools import wraps

# 导入配置
from config import config

class NetworkMonitor:
    """网络监控器，管理网络状态检测和重试机制"""
    
    def __init__(self):
        """初始化网络监控器"""
        self._retry_callback = None
        self._recovery_event = threading.Event()
        self._should_retry = False
        self._retry_thread = None
        self._stop_event = threading.Event()
    
    def check_connection(self):
        """
        检查是否能连接到外网，返回布尔值
        使用指数退避算法尝试不同的主机
        """
        for host, port in config.NETWORK_CHECK_HOSTS:
            try:
                socket.create_connection((host, port), timeout=config.NETWORK_CHECK_TIMEOUT)
                return True
            except OSError:
                continue
        return False
    
    def wait_for_recovery(self):
        """
        等待网络恢复连接
        使用递增间隔策略减少CPU使用
        """
        if self.check_connection():
            return True
            
        logging.warning("⚠️ Network disconnected, waiting for recovery...")
        
        # 使用递增间隔检测网络
        interval = config.NETWORK_RETRY_INITIAL_INTERVAL
        recovery_detected = False
        
        while not recovery_detected and not self._stop_event.is_set():
            time.sleep(interval)
            
            if self.check_connection():
                recovery_detected = True
                self._recovery_event.set()
                logging.info(f"✅ Network connection restored")
                break
                
            # 增加等待间隔，但不超过最大值
            interval = min(interval * config.NETWORK_RETRY_MULTIPLIER, 
                           config.NETWORK_RETRY_MAX_INTERVAL)
            logging.warning(f"⚠️ Network still down, next check in {interval:.1f} seconds...")
        
        return recovery_detected
    
    def register_retry_callback(self, callback):
        """注册网络恢复后的重试回调函数"""
        self._retry_callback = callback
    
    def start_recovery_monitor(self):
        """启动网络恢复监控线程"""
        if self._retry_thread is not None and self._retry_thread.is_alive():
            return  # 已经在运行
            
        self._should_retry = True
        self._stop_event.clear()
        self._recovery_event.clear()
        
        self._retry_thread = threading.Thread(
            target=self._recovery_monitor_task,
            daemon=True
        )
        self._retry_thread.start()
        
        return self._retry_thread
    
    def stop_recovery_monitor(self):
        """停止网络恢复监控"""
        self._should_retry = False
        self._stop_event.set()
        self._recovery_event.set()  # 唤醒任何等待的线程
        
        if self._retry_thread and self._retry_thread.is_alive():
            self._retry_thread.join(timeout=1.0)
    
    def _recovery_monitor_task(self):
        """网络恢复监控任务"""
        # 等待网络恢复
        if not self.wait_for_recovery():
            logging.error("❌ Network recovery wait interrupted or timed out")
            self._should_retry = False
            return
        
        if not self._should_retry:
            return
            
        # 等待网络稳定
        time.sleep(5)
        
        # 执行重试
        if self._retry_callback and self._should_retry:
            self._execute_retry()
    
    def _execute_retry(self):
        """执行重试逻辑"""
        retry_count = 0
        
        while retry_count < config.MAX_RETRY_TIMES and self._should_retry:
            retry_count += 1
            logging.info(f"🔄 Starting retry {retry_count}/{config.MAX_RETRY_TIMES}")
            
            success = False
            try:
                if self._retry_callback:
                    success = self._retry_callback()
            except Exception as e:
                logging.error(f"❌ Error during retry: {e}")
            
            if success:
                logging.info("✅ Retry successful")
                self._should_retry = False
                break
                
            if retry_count < config.MAX_RETRY_TIMES and self._should_retry:
                waiting_time = 30 * (retry_count + 1)  # 递增等待时间
                logging.info(f"⏳ Waiting {waiting_time} seconds before next retry...")
                
                # 可中断的等待
                if self._stop_event.wait(timeout=waiting_time):
                    break
        
        if self._should_retry:
            logging.error(f"❌ Tried {config.MAX_RETRY_TIMES} retries but still failed")
            self._should_retry = False

# 创建全局网络监控器实例
network_monitor = NetworkMonitor()

def with_network_retry(func):
    """
    装饰器：为函数添加网络重试能力
    如果函数因网络错误失败，将自动在网络恢复后重试
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        is_retry = kwargs.pop('is_retry', False)
        
        # 如果是重试调用但不需要重试，直接返回
        if is_retry and not network_monitor._should_retry:
            return None
            
        try:
            # 检查网络连接
            if not network_monitor.check_connection():
                logging.error("❌ Network connection unavailable, cannot execute task")
                
                if not is_retry:  # 只在首次尝试时启动监控
                    # 注册当前函数作为重试回调
                    network_monitor.register_retry_callback(
                        lambda: func(*args, is_retry=True, **kwargs)
                    )
                    network_monitor.start_recovery_monitor()
                
                return None
                
            # 执行原函数
            result = func(*args, **kwargs)
            
            # 如果成功且是重试，停止监控
            if is_retry:
                network_monitor._should_retry = False
                
            return result
            
        except (socket.error, ConnectionError, TimeoutError) as e:
            # 网络相关错误
            logging.error(f"❌ Network error: {e}")
            
            if not is_retry:  # 只在首次尝试时启动监控
                # 注册当前函数作为重试回调
                network_monitor.register_retry_callback(
                    lambda: func(*args, is_retry=True, **kwargs)
                )
                network_monitor.start_recovery_monitor()
            
            return None
            
    return wrapper 