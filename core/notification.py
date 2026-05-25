"""
Notification Module
Windows 11-native system notifications via windows-toasts (WinRT).

A custom AUMID is registered in HKCU on first import so Windows shows
the Lark Backup icon — not the Python/cmd icon — in every notification.
No admin rights required (HKCU only, built-in winreg module).
"""

import os
import sys
import shutil
import logging
import winreg
import ctypes
import threading
from typing import Optional

# ---------------------------------------------------------------------------
# Lazy-import windows-toasts; fall back to log-only on failure
# ---------------------------------------------------------------------------
_TOAST_AVAILABLE = False
_toaster = None

try:
    from windows_toasts import (
        InteractableWindowsToaster,
        Toast,
        ToastButton,
        ToastActivatedEventArgs,
    )
    _TOAST_AVAILABLE = True
except Exception as _import_err:
    logging.warning(f"⚠️ windows-toasts unavailable ({_import_err}); notifications will be log-only")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_APP_NAME = "Lark Backup"
_AUMID    = "LarkBackup.App"

_PREFIXES = {
    "success": "✅ ",
    "warning": "⚠️ ",
    "error":   "❌ ",
    "info":    "",
}

_MB_OK = 0x00000000
_MB_ICONINFORMATION = 0x00000040
_MB_ICONWARNING = 0x00000030
_MB_ICONERROR = 0x00000010
_MB_TOPMOST = 0x00040000
_MB_SETFOREGROUND = 0x00010000


def _message_box_flags(notification_type: str) -> int:
    """Map notification type to MessageBox style flags."""
    icon = _MB_ICONINFORMATION
    if notification_type == "warning":
        icon = _MB_ICONWARNING
    elif notification_type == "error":
        icon = _MB_ICONERROR
    return _MB_OK | icon | _MB_TOPMOST | _MB_SETFOREGROUND


def _show_message_box_async(title: str, message: str, notification_type: str) -> None:
    """
    Show a native Win32 MessageBox as a non-blocking fallback.
    Runs in a dedicated daemon thread so backup flow is not blocked.
    """
    def _worker() -> None:
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                message,
                f"{_APP_NAME} - {title}",
                _message_box_flags(notification_type),
            )
        except Exception as e:
            logging.warning(f"⚠️ MessageBox fallback failed: {e}")

    threading.Thread(
        target=_worker,
        daemon=True,
        name="LarkBackup-NotificationPopup",
    ).start()

# ---------------------------------------------------------------------------
# Icon path — must be a persistent file path suitable for the AUMID registry
# ---------------------------------------------------------------------------

def _get_icon_path() -> Optional[str]:
    """
    Return a stable on-disk path to file_download.ico.

    - Development: assets/file_download.ico relative to project root.
    - PyInstaller exe: copies the bundled icon to %APPDATA%\\LarkBackup\\icon.ico
      once, then reuses it. The _MEIPASS temp dir changes every run, so a
      persistent copy is required for the AUMID IconUri registry value.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return None
        dest_dir = os.path.join(appdata, "LarkBackup")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "icon.ico")
        if not os.path.exists(dest):
            src = os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "file_download.ico")
            if os.path.exists(src):
                shutil.copy2(src, dest)
        return dest if os.path.exists(dest) else None
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = os.path.join(project_root, "assets", "file_download.ico")
        return src if os.path.exists(src) else None


# ---------------------------------------------------------------------------
# AUMID registration
# ---------------------------------------------------------------------------

def _register_aumid(icon_path: str) -> None:
    """
    Write DisplayName and IconUri under HKCU\\SOFTWARE\\Classes\\AppUserModelId.
    Windows reads this when displaying the notification to choose the app icon.
    Idempotent — safe to call on every startup.
    """
    key_path = rf"SOFTWARE\Classes\AppUserModelId\{_AUMID}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, _APP_NAME)
        winreg.SetValueEx(key, "IconUri",     0, winreg.REG_SZ, icon_path)


# ---------------------------------------------------------------------------
# Toaster initialisation — runs once at module import
# ---------------------------------------------------------------------------

def _init_toaster() -> None:
    global _toaster
    if not _TOAST_AVAILABLE:
        return
    icon_path = _get_icon_path()
    if icon_path:
        try:
            _register_aumid(icon_path)
            logging.info(f"✅ Notification AUMID registered (icon: {icon_path})")
        except Exception as e:
            logging.warning(f"⚠️ AUMID registration failed: {e}")
    try:
        _toaster = InteractableWindowsToaster(_APP_NAME, notifierAUMID=_AUMID)
    except Exception as e:
        logging.warning(f"⚠️ Toaster init failed: {e}")


_init_toaster()


# ---------------------------------------------------------------------------
# Backup directory helper (lazy import to avoid circular dependency)
# ---------------------------------------------------------------------------

def _backup_dir() -> str:
    try:
        from config import config
        return config.DOWNLOAD_DIR
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def show_notification(title: str, message: str, notification_type: str = "info") -> None:
    """
    Display a Windows system notification.

    Falls back to Win32 MessageBox when windows-toasts is unavailable
    or toast delivery fails.

    :param title:             Notification heading (bold first line).
    :param message:           Notification body (second line).
    :param notification_type: ``"success"`` | ``"warning"`` | ``"error"`` | ``"info"``
    """
    logging.info(f"📢 Notification [{notification_type}]: {title} - {message}")

    if not _TOAST_AVAILABLE or _toaster is None:
        logging.warning("⚠️ Toast unavailable, falling back to MessageBox")
        _show_message_box_async(title, message, notification_type)
        return

    toast = Toast()
    toast.text_fields = [_PREFIXES.get(notification_type, "") + title, message]

    # "View Folder" button on success and error notifications
    if notification_type in ("success", "error"):
        bdir = _backup_dir()
        if bdir:
            toast.AddAction(ToastButton("View Folder", "open_folder"))
            def _on_click(args: ToastActivatedEventArgs, d=bdir):
                try:
                    if os.path.exists(d):
                        os.startfile(d)
                except Exception as exc:
                    logging.warning(f"⚠️ Could not open folder {d}: {exc}")
            toast.on_activated = _on_click

    try:
        _toaster.show_toast(toast)
    except Exception as e:
        logging.warning(f"⚠️ Notification failed: {e}")
        _show_message_box_async(title, message, notification_type)
