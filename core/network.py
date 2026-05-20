"""
Network Module
Handles network connectivity detection and recovery logic

Design principles:
  - NetworkMonitor is solely responsible for "detection" and "waiting for recovery",
    not for "retrying business logic".
  - Retry scheduling is controlled uniformly by run_backup_with_retry() to avoid
    conflicting parallel retry paths.
  - The with_network_retry decorator only performs a pre-call network check; it
    returns None immediately when the network is unavailable, leaving the next
    step to the caller.
"""

import socket
import time
import logging
from functools import wraps

from config import config


class NetworkMonitor:
    """Network monitor: detects connectivity and blocks until recovery."""

    def check_connection(self) -> bool:
        """Attempt to connect to configured check hosts; return True if any succeeds."""
        for host, port in config.NETWORK_CHECK_HOSTS:
            try:
                with socket.create_connection((host, port), timeout=config.NETWORK_CHECK_TIMEOUT):
                    return True
            except OSError:
                continue
        return False

    def wait_for_recovery(self) -> bool:
        """
        Block until network connectivity is restored. Uses exponential back-off
        to reduce CPU usage.
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


# Global singleton
network_monitor = NetworkMonitor()


def with_network_retry(func):
    """
    Decorator: checks network connectivity before invoking the wrapped function.
    Returns None immediately when the network is unavailable without starting any
    background threads — retry scheduling is handled exclusively by the outer
    run_backup_with_retry().
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not network_monitor.check_connection():
            logging.error("❌ Network unavailable — skipping call to %s()", func.__name__)
            return None
        return func(*args, **kwargs)
    return wrapper
