"""
网络模块
处理网络连接检测和恢复逻辑

设计原则：
  - NetworkMonitor 只负责「检测」和「等待恢复」，不负责「重试业务逻辑」。
  - 重试调度由 run_backup_with_retry() 统一控制，避免并行重试路径冲突。
  - with_network_retry 装饰器仅做调用前的网络前置检查，网络不通时立即返回
    None，由调用方决定下一步。
"""

import socket
import time
import logging
from functools import wraps

from config import config


class NetworkMonitor:
    """网络监控器：检测连通性，阻塞等待恢复。"""

    def check_connection(self) -> bool:
        """尝试连接配置的检测主机，任一成功即返回 True。"""
        for host, port in config.NETWORK_CHECK_HOSTS:
            try:
                socket.create_connection((host, port), timeout=config.NETWORK_CHECK_TIMEOUT)
                return True
            except OSError:
                continue
        return False

    def wait_for_recovery(self) -> bool:
        """
        阻塞直到网络恢复。使用指数退避减少 CPU 占用。
        Returns True when connection is restored.
        """
        if self.check_connection():
            return True

        logging.warning("⚠️ Network disconnected, waiting for recovery…")
        interval = config.NETWORK_RETRY_INITIAL_INTERVAL

        while True:
            time.sleep(interval)
            if self.check_connection():
                logging.info("✅ Network connection restored")
                return True
            interval = min(interval * config.NETWORK_RETRY_MULTIPLIER,
                           config.NETWORK_RETRY_MAX_INTERVAL)
            logging.warning(f"⚠️ Network still down, next check in {interval:.0f}s…")


# 全局单例
network_monitor = NetworkMonitor()


def with_network_retry(func):
    """
    装饰器：调用前检查网络连通性。
    网络不通时立即返回 None，不启动任何后台线程——
    重试调度由外层 run_backup_with_retry() 统一负责。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not network_monitor.check_connection():
            logging.error("❌ Network unavailable — skipping call to %s()", func.__name__)
            return None
        return func(*args, **kwargs)
    return wrapper
