"""
 Notification Module
Handles system notifications
"""

import os
import sys
import logging
import time
import threading

# 全局通知设置
_use_notifications = True  # 可以设为False来完全禁用通知
_notifier_name = "log_only"
_toast_notifier = None
_notification_lock = threading.Lock()  # 添加锁防止并发问题
_win10toast_failed = False  # 标记win10toast是否已经失败过

# 尝试导入win10toast
try:
    from win10toast import ToastNotifier
    # 创建通知器实例
    _toast_notifier = ToastNotifier()
    _notifier_name = "win10toast"
    _has_notification = True
    logging.info("✅ Win10Toast notification")
except ImportError:
    logging.warning("⚠️ win10toast library unavailable, notifications disabled")
    _notifier_name = "log_only"
    _has_notification = False

# Get icon file path
def get_icon_path():
    """Get the correct icon file path"""
    # Try multiple possible paths
    icon_name = "file_download.ico"
    assets_dir = "assets"

    # List of common possible paths
    possible_paths = [
        # 当前目录
        icon_name,
        # assets目录
        os.path.join(assets_dir, icon_name),
        # 若使用PyInstaller打包
        os.path.join(getattr(sys, '_MEIPASS', '.'), assets_dir, icon_name) if hasattr(sys, '_MEIPASS') else None,
        # 上级目录
        os.path.join("..", assets_dir, icon_name),
        # 应用程序目录assets
        os.path.join(os.path.dirname(sys.executable), assets_dir, icon_name) if getattr(sys, 'frozen', False) else None,
    ]

    # 尝试所有可能的路径
    for path in possible_paths:
        if path and os.path.exists(path):
            return os.path.abspath(path)

    # 如果找不到，返回无图标
    return None

def _notify_win10toast(title, message, icon_path):
    """使用win10toast发送通知"""
    global _win10toast_failed

    try:
        if _toast_notifier:
            # 确保参数不为None，并进行基本验证
            safe_title = str(title) if title is not None else "Notification"
            safe_message = str(message) if message is not None else ""

            # 验证图标路径
            safe_icon_path = icon_path if icon_path and os.path.exists(str(icon_path)) else None

            # 使用try-except包裹整个toast调用，捕获所有可能的错误
            try:
                # 完全禁用线程模式并捕获所有异常
                _toast_notifier.show_toast(
                    title=safe_title,
                    msg=safe_message,
                    icon_path=safe_icon_path,
                    duration=3,
                    threaded=False  # 保持非线程模式
                )
                return True
            except Exception as toast_error:
                # 捕获所有win10toast错误，包括WPARAM相关错误
                error_msg = str(toast_error)
                if "WPARAM" in error_msg or "LRESULT" in error_msg or "TypeError" in error_msg:
                    logging.warning(f"⚠️ Win10Toast compatibility issue: {error_msg}")
                else:
                    logging.warning(f"⚠️ Win10Toast error: {error_msg}")

                # 标记win10toast失败，后续只记录日志
                _win10toast_failed = True
                return False

    except Exception as e:
        logging.warning(f"⚠️ win10toast initialization error: {str(e)}")
        _win10toast_failed = True
        return False

    return False

def show_notification(title, message, notification_type="info"):
    """显示系统通知 - 仅使用win10toast"""
    global _win10toast_failed

    # 如果禁用通知，只记录日志
    if not _use_notifications:
        logging.info(f"📢 Notification [{notification_type}]: {title} - {message}")
        return

    try:
        # 使用锁防止并发问题
        with _notification_lock:
            # 始终记录通知到日志
            logging.info(f"📢 Notification [{notification_type}]: {title} - {message}")

            # 只使用win10toast，如果失败就不显示任何弹窗
            if _notifier_name == "win10toast" and not _win10toast_failed:
                icon_path = get_icon_path()

                # 简化标题格式
                if notification_type == "error":
                    formatted_title = f"❌ {title}"
                elif notification_type == "warning":
                    formatted_title = f"⚠️ {title}"
                elif notification_type == "success":
                    formatted_title = f"✅ {title}"
                else:  # info
                    formatted_title = title

                # 尝试显示win10toast通知
                success = _notify_win10toast(formatted_title, message, icon_path)
                if success:
                    logging.info(f"✅ Notification displayed: {title}")
                else:
                    logging.warning(f"⚠️ Notification failed, logged only: {title}")

            # 如果win10toast不可用或失败，不显示任何弹窗，只记录日志

    except Exception as e:
        logging.error(f"❌ Notification system error: {str(e)}")

# 导出便捷函数
def info(title, message):
    """显示一般通知"""
    show_notification(title, message, "info")

def success(title, message):
    """显示成功通知"""
    show_notification(title, message, "success")

def warning(title, message):
    """显示警告通知"""
    show_notification(title, message, "warning")

def error(title, message):
    """显示错误通知"""
    show_notification(title, message, "error")
