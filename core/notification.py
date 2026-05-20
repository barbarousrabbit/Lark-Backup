"""
Notification Module
Handles system notifications
"""

import os
import sys
import logging
import time
import threading

# Global notification settings
_use_notifications = True  # Set to False to disable notifications entirely
_notifier_name = "log_only"
_toast_notifier = None
_notification_lock = threading.Lock()  # Lock to prevent concurrency issues
_win10toast_failed = False  # Tracks whether win10toast has already failed

# Attempt to import win10toast
try:
    from win10toast import ToastNotifier
    # Create notifier instance
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
        # Current directory
        icon_name,
        # assets directory
        os.path.join(assets_dir, icon_name),
        # When packaged with PyInstaller
        os.path.join(getattr(sys, '_MEIPASS', '.'), assets_dir, icon_name) if hasattr(sys, '_MEIPASS') else None,
        # Parent directory
        os.path.join("..", assets_dir, icon_name),
        # Executable directory assets
        os.path.join(os.path.dirname(sys.executable), assets_dir, icon_name) if getattr(sys, 'frozen', False) else None,
    ]

    # Try all possible paths
    for path in possible_paths:
        if path and os.path.exists(path):
            return os.path.abspath(path)

    # Return None if icon cannot be found
    return None

def _notify_win10toast(title, message, icon_path):
    """Send a notification using win10toast"""
    global _win10toast_failed

    try:
        if _toast_notifier:
            # Ensure parameters are not None and perform basic validation
            safe_title = str(title) if title is not None else "Notification"
            safe_message = str(message) if message is not None else ""

            # Validate icon path
            safe_icon_path = icon_path if icon_path and os.path.exists(str(icon_path)) else None

            # Wrap the entire toast call in try-except to catch all possible errors
            try:
                # Keep non-threaded mode and catch all exceptions
                _toast_notifier.show_toast(
                    title=safe_title,
                    msg=safe_message,
                    icon_path=safe_icon_path,
                    duration=3,
                    threaded=False  # Keep non-threaded mode
                )
                return True
            except Exception as toast_error:
                # Catch all win10toast errors, including WPARAM-related errors
                error_msg = str(toast_error)
                if "WPARAM" in error_msg or "LRESULT" in error_msg or "TypeError" in error_msg:
                    logging.warning(f"⚠️ Win10Toast compatibility issue: {error_msg}")
                else:
                    logging.warning(f"⚠️ Win10Toast error: {error_msg}")

                # Mark win10toast as failed; subsequent calls will log only
                _win10toast_failed = True
                return False

    except Exception as e:
        logging.warning(f"⚠️ win10toast initialization error: {str(e)}")
        _win10toast_failed = True
        return False

    return False

def show_notification(title, message, notification_type="info"):
    """Display a system notification — uses win10toast only"""
    global _win10toast_failed

    # If notifications are disabled, log only
    if not _use_notifications:
        logging.info(f"📢 Notification [{notification_type}]: {title} - {message}")
        return

    try:
        # Use lock to prevent concurrency issues
        with _notification_lock:
            # Always log the notification
            logging.info(f"📢 Notification [{notification_type}]: {title} - {message}")

            # Use win10toast only; if it fails, no popup is shown
            if _notifier_name == "win10toast" and not _win10toast_failed:
                icon_path = get_icon_path()

                # Format title with type prefix
                if notification_type == "error":
                    formatted_title = f"❌ {title}"
                elif notification_type == "warning":
                    formatted_title = f"⚠️ {title}"
                elif notification_type == "success":
                    formatted_title = f"✅ {title}"
                else:  # info
                    formatted_title = title

                # Attempt to show win10toast notification
                success = _notify_win10toast(formatted_title, message, icon_path)
                if success:
                    logging.info(f"✅ Notification displayed: {title}")
                else:
                    logging.warning(f"⚠️ Notification failed, logged only: {title}")

            # If win10toast is unavailable or failed, no popup is shown — log only

    except Exception as e:
        logging.error(f"❌ Notification system error: {str(e)}")

# Convenience export functions
def info(title, message):
    """Display an informational notification"""
    show_notification(title, message, "info")

def success(title, message):
    """Display a success notification"""
    show_notification(title, message, "success")

def warning(title, message):
    """Display a warning notification"""
    show_notification(title, message, "warning")

def error(title, message):
    """Display an error notification"""
    show_notification(title, message, "error")
