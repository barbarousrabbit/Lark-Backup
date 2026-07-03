#!/usr/bin/env python3
"""
Lark (Feishu) Bitable Backup Program
Automatically downloads Lark Bitable data on a schedule and saves it as an Excel file
Supports automatic recovery after network disconnection
Prevents duplicate program instances from running
"""

import os
import sys
import logging
import time
import traceback
import ctypes
import winreg
import subprocess
from datetime import datetime
import threading
import psutil

# Set Python path to ensure modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import configuration and custom modules
from config import config
from core.network import network_monitor
from core.api_service import api_service
from core.file_manager import file_manager
from core.scheduler import task_scheduler
from core.notification import show_notification
from core.process_manager import init_single_instance_manager
from core.retry_manager import retry_manager
from core.data_comparator import data_comparator
from core.alert_window import alert_manager
from core.report_generator import report_generator

# ---------------------------------------------------------------------------
# CLI helpers — install / uninstall (single-exe distribution)
# ---------------------------------------------------------------------------
_REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_APP_NAME = "LarkBackup"


def _msgbox(title: str, message: str, icon: int = 0x40) -> None:
    """Native Win32 MessageBox — visible even with console=False in the exe."""
    ctypes.windll.user32.MessageBoxW(None, message, title, icon)


def _cli_install() -> None:
    """Register autostart in HKCU and launch the backup service."""
    if not getattr(sys, "frozen", False):
        _msgbox("Lark Backup", "--install is only available in the packaged exe.", 0x30)
        os._exit(1)

    exe = sys.executable  # path to LarkBackup.exe
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _REG_APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
    except Exception as e:
        _msgbox("Lark Backup — Install Failed", f"Could not register autostart:\n{e}", 0x10)
        os._exit(1)

    # The service must launch as an INDEPENDENT onefile instance that extracts
    # and later cleans up its OWN _MEI temp dir. PyInstaller signals "you are a
    # nested child, reuse the parent's dir" via sentinel env vars; if the child
    # inherits them it shares this installer's dir, then loses it (certifi TLS
    # failure) and blocks its removal ("Failed to remove temporary directory")
    # when the installer exits. The sentinel was _MEIPASS2 on PyInstaller <=5
    # and became the _PYI_* family on 6.x, so strip both to stay version-proof.
    env = {k: v for k, v in os.environ.items()
           if k != "_MEIPASS2" and not k.startswith("_PYI")}

    # Launch the backup service (same exe, no --install flag), fully detached
    subprocess.Popen(
        [exe],
        env=env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    # No success dialog: the detached service shows its own "Backup Service
    # Started" toast once it is up, so a center-screen MessageBox here would be
    # a redundant second popup. Errors above still use MessageBox (they need
    # attention and the service may never start to toast about them).
    os._exit(0)


def _cli_uninstall() -> None:
    """Remove autostart from HKCU and stop any running instance."""
    removed = False

    # Read the registered exe path BEFORE deleting the value, so a service
    # running from a different folder (old install dir) can still be stopped.
    installed_exe = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN_PATH, 0,
                            winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, _REG_APP_NAME)
            installed_exe = value.strip().strip('"')
    except OSError:
        pass  # not registered or unreadable — matching falls back to own exe

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _REG_APP_NAME)
        removed = True
    except FileNotFoundError:
        pass  # was never registered — that's fine
    except Exception as e:
        _msgbox("Lark Backup — Uninstall Failed", f"Could not remove autostart:\n{e}", 0x10)
        os._exit(1)

    # Terminate running instances. Frozen-only: in dev mode sys.executable is
    # python.exe and a path sweep would kill unrelated Python processes.
    still_alive = []
    if getattr(sys, "frozen", False):
        target_paths = {os.path.abspath(sys.executable).lower()}
        if installed_exe:
            target_paths.add(os.path.abspath(installed_exe).lower())

        own_pid = os.getpid()
        own_parent_pid = os.getppid()
        own_name = os.path.basename(os.path.abspath(sys.executable)).lower()
        candidates = []
        for proc in psutil.process_iter(["pid", "ppid", "exe", "cmdline", "name"]):
            # Skip ourselves and our own PyInstaller bootloader parent — killing
            # the parent would leak its _MEI temp dir and abort this dialog.
            if proc.pid in (own_pid, own_parent_pid):
                continue
            try:
                exe = (proc.info.get("exe") or "").lower()
                if exe:
                    if exe not in target_paths:
                        continue
                # exe unreadable (e.g. a service launched elevated) — fall back
                # to the process name so an inaccessible instance is still
                # detected instead of silently dropped (would else falsely
                # report "service stopped").
                elif (proc.info.get("name") or "").lower() != own_name:
                    continue
                cmdline = proc.info.get("cmdline") or []
                if "--install" in cmdline or "--uninstall" in cmdline:
                    continue
                candidates.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Onefile pairs: terminate only app children; a bootloader parent
        # cleans up its _MEI temp dir and exits once its child dies.
        bootloader_pids = {c.info.get("ppid") for c in candidates}
        targets = [c for c in candidates if c.pid not in bootloader_pids]
        for proc in targets:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _, alive = psutil.wait_procs(targets, timeout=5)
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _, still_alive = psutil.wait_procs(alive, timeout=3)

    status = "Autostart removed." if removed else "Autostart was not registered."
    if still_alive:
        _msgbox(
            "Lark Backup — Uninstalled (with warnings)",
            f"{status}\n{len(still_alive)} LarkBackup process(es) could not be stopped — "
            "please end them via Task Manager.",
            0x30,
        )
    else:
        _msgbox(
            "Lark Backup — Uninstalled",
            f"{status}\nThe backup service has been stopped.",
            0x40,
        )
    os._exit(0)


# ---------------------------------------------------------------------------
# Global instance manager
# ---------------------------------------------------------------------------
_instance_manager = None

# Backup task mutex: ensures the initial thread and scheduler thread do not run backups concurrently
_backup_lock = threading.Lock()

# Configure logging
def setup_logging():
    """Configure logging"""
    # Ensure the log directory exists
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            # If directory creation fails, print to console and continue; log file may not be written
            print(f"Error creating log directory {log_dir}: {e}", file=sys.stderr)

    # Clear all existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Create file handler with immediate flush
    try:
        file_handler = logging.FileHandler(config.LOG_FILE, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - PID:%(process)d - %(levelname)s - %(message)s'))
    except Exception as e:
        print(f"Warning: Cannot create log file handler: {e}", file=sys.stderr)
        file_handler = None

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - PID:%(process)d - %(levelname)s - %(message)s'))

    # Configure root logger
    logging.root.setLevel(logging.INFO)
    if file_handler:
        logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)

    # Ensure logs are written immediately
    logging.info("📝 Logging initialized")
    # Manually flush all handlers
    for handler in logging.root.handlers:
        handler.flush()

    if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Configure console encoding
def setup_console_encoding():
    """Configure console encoding (dev console runs only)."""
    # Windowed exe: there is no console, and os.system() would spawn cmd.exe
    # with a visible window flash at every startup/login. Skip entirely.
    if getattr(sys, 'frozen', False) or sys.stdout is None:
        return
    if sys.platform.startswith('win'):
        try:
            os.system('chcp 65001 > nul')
        except Exception:
            pass


def _download_and_save(backup_date):
    """Runs the full API pipeline and saves the file. Returns (path, details) or (None, details)."""
    # Real attempt number: get_today_attempts()+1 because record_attempt()
    # only runs after the whole backup_task returns.
    details = {'backup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               'attempts': retry_manager.get_today_attempts() + 1}
    try:
        file_manager.ensure_download_dir_exists()
        tenant_token = api_service.get_tenant_token()
        if not tenant_token:
            logging.error("❌ API token failed")
            details['error'] = 'token failed'
            return None, details
        wiki_data = api_service.get_wiki_data()
        if not wiki_data:
            logging.error("❌ Wiki data failed")
            details['error'] = 'wiki failed'
            return None, details
        obj_token = api_service.extract_obj_token(wiki_data)
        ticket = api_service.create_export_task(obj_token)
        if not ticket:
            logging.error("❌ Export task failed")
            details['error'] = 'export failed'
            return None, details
        file_token = api_service.get_export_task_status(ticket, obj_token)
        if not file_token:
            logging.error("❌ File token failed")
            details['error'] = 'file token failed'
            return None, details
        file_content = api_service.download_file(file_token)
        if not file_content:
            logging.error("❌ Download failed")
            details['error'] = 'download failed'
            return None, details
        # Label the snapshot by its CAPTURE time, not the attempt start: an
        # attempt that resumes after a multi-day system sleep would otherwise
        # file today's data under a days-old name (observed 2026-06: Monday
        # data saved as the Friday file after a weekend sleep).
        effective_date = config.get_backup_date()
        if effective_date != backup_date:
            logging.warning(f"⚠️ Date drifted during backup ({backup_date} → {effective_date}); labeling snapshot as {effective_date}")
            backup_date = effective_date
        details['date'] = backup_date
        saved_path = file_manager.save_file(file_content, backup_date)
        if saved_path:
            details['file_path'] = saved_path
            details['success'] = True
            try:
                details['file_size'] = os.path.getsize(saved_path)
            except OSError:
                pass
            return saved_path, details
        details['error'] = 'save failed'
        return None, details
    except ValueError as e:
        logging.error(f"❌ {e}")
        details['error'] = str(e)
        return None, details
    except Exception as e:
        logging.error(f"❌ Backup error: {e}")
        logging.error(traceback.format_exc())
        details['error'] = str(e)
        return None, details


def _compare_and_alert(backup_date):
    """Runs data comparison. Returns (differences, warnings).
    Alert notifications are fired by the caller AFTER the success toast."""
    try:
        differences, warnings = data_comparator.compare_with_previous_date(backup_date)
        if warnings:
            logging.warning(f"⚠️ {len(warnings)} warnings from comparison")
        if differences:
            data_comparator.save_comparison_result(backup_date, {'differences': differences, 'warnings': warnings})
        return differences, warnings
    except Exception as e:
        logging.error(f"❌ Comparison failed: {e}")
        # Surface the failure in the daily report as a warning instead of
        # letting it render the green "No significant changes" success box.
        return None, [f"Data comparison failed: {e}"]


def _generate_failure_report(backup_date, error_msg, attempts=1):
    """Generates a failure daily report. Swallows exceptions."""
    try:
        report_generator.generate_daily_report(
            backup_date, False, {'error': error_msg, 'attempts': attempts}, None, None
        )
    except Exception:
        pass


def backup_task(backup_date=None):
    """Orchestrates one full backup cycle. Returns True on success."""
    logging.info("🔄 Starting backup")
    if backup_date is None:
        backup_date = config.get_backup_date()

    saved_path, details = _download_and_save(backup_date)

    if not saved_path:
        _generate_failure_report(backup_date, details.get('error', 'unknown'),
                                 details.get('attempts', 1))
        return False

    logging.info(f"✅ Backup saved: {saved_path}")

    # Follow the save-time label so comparison, report, and alert all refer
    # to the file that was actually written.
    backup_date = details.get('date', backup_date)

    differences, warnings = _compare_and_alert(backup_date)

    try:
        report_generator.generate_daily_report(backup_date, True, details, differences, warnings)
    except Exception as e:
        logging.error(f"❌ Report failed: {e}")

    # Show backup success first so the user knows the backup itself succeeded,
    # then follow with the comparison detail as supplementary information.
    # (alert_manager fires HERE, not inside _compare_and_alert, so this order
    # is guaranteed and a data-loss day produces exactly two toasts.)
    show_notification("Backup Successful", f"Saved: {os.path.basename(saved_path)}", "success")

    if warnings and differences:
        # Real data-loss warnings with actual sheet differences — one
        # per-day-deduplicated Data Loss Alert via alert_manager.
        alert_manager.check_and_show_alert(differences, warnings, backup_date)
    elif differences:
        # Changes detected but no warnings (no data loss threshold exceeded)
        n_sheets = len(differences)
        sheet_label = "sheet" if n_sheets == 1 else "sheets"
        show_notification(
            "Data Comparison Complete",
            f"{n_sheets} {sheet_label} changed",
            "info"
        )
    # If warnings but no differences (e.g. previous backup file missing):
    # comparison could not run — already logged, no misleading toast needed

    # Prune old backups only after a fully successful cycle (never raises)
    file_manager.cleanup_old_backups()

    return True


def run_backup_with_retry():
    """Execute the backup task with a daily retry mechanism.
    Non-blocking mutex: if the previous backup is still running, this trigger is skipped to avoid concurrent backups.
    """
    if not _backup_lock.acquire(blocking=False):
        logging.warning("⚠️ Backup already in progress, skipping this trigger")
        return False

    try:
        return _run_backup_loop()
    finally:
        _backup_lock.release()


def _run_backup_loop():
    """Backup retry loop (internal implementation, called under lock by run_backup_with_retry)."""
    # In-memory backstop: if daily_retry_count.json is unwritable, the
    # persisted count never grows and the file-based limit alone would let
    # this loop retry forever (hammering the Lark API every ~60s).
    local_attempts = 0

    while True:
        # Recomputed every attempt: a retry that crosses midnight or resumes
        # after a system sleep must label the NEW snapshot it takes, not the
        # day the loop started. (Drift WITHIN one attempt is handled by the
        # save-time re-check in _download_and_save.)
        backup_date = config.get_backup_date()
        if local_attempts >= config.MAX_DAILY_ATTEMPTS or not retry_manager.can_attempt_today():
            logging.warning(f"⚠️ Daily limit reached ({config.MAX_DAILY_ATTEMPTS} attempts)")
            show_notification("Daily Limit Reached", "All backup attempts exhausted for today", "error")
            # max(): the persisted count may read 0 when the retry file is
            # unwritable — the in-memory counter still knows what happened.
            _generate_failure_report(backup_date, f"All {config.MAX_DAILY_ATTEMPTS} attempts failed",
                                     max(retry_manager.get_today_attempts(), local_attempts))
            return False

        # Pre-check network BEFORE counting an attempt against the daily limit.
        # A network outage should not consume retry quota — only real backup failures do.
        if not network_monitor.check_connection():
            logging.info("⏳ Network unavailable, waiting for recovery before attempt…")
            network_monitor.wait_for_recovery()

        result = backup_task(backup_date)
        local_attempts += 1
        attempt_count = retry_manager.record_attempt(success=result)

        if result:
            return True

        remaining = min(retry_manager.get_remaining_attempts(),
                        config.MAX_DAILY_ATTEMPTS - local_attempts)
        if remaining <= 0:
            logging.error(f"❌ Daily attempts exhausted ({config.MAX_DAILY_ATTEMPTS} times)")
            show_notification("Backup Failed", f"All {config.MAX_DAILY_ATTEMPTS} attempts failed today", "error")
            return False

        logging.warning(f"❌ Failed (attempt {attempt_count}), {remaining} remaining")
        logging.info(f"⏱️ Waiting {config.ERROR_RETRY_INTERVAL}s before retry")
        time.sleep(config.ERROR_RETRY_INTERVAL)


def _run_initial_backup_task():
    """Run the initial backup task in a separate thread (with retry)"""
    logging.info("🚀 Initial backup started")
    try:
        run_backup_with_retry()
    except Exception as e:
        # Windowed exe: an exception escaping this thread would only reach
        # the invisible stderr — log it and surface a failure report so a
        # lost startup backup is never silent.
        logging.error(f"❌ Initial backup thread crashed: {e}", exc_info=True)
        try:
            _generate_failure_report(config.get_backup_date(), f"initial backup crashed: {e}")
            show_notification("Backup Error", "Initial backup crashed — see log for details", "error")
        except Exception:
            pass
        return
    logging.info("✅ Initial backup completed")

def main_logic():
    """Contains the core business logic"""
    logging.info(f"⚙️ Main logic, PID: {os.getpid()}")

    # Smart reset: if started manually, reset today's retry count
    retry_manager.reset_if_manual_start()

    # Set up and start the task scheduler
    task_scheduler.schedule_daily_task(lambda: run_backup_with_retry())

    # Immediate health feedback: confirms the service started and the first run is kicked off.
    show_notification(
        "Backup Service Started",
        f"Initial backup is running now. Daily schedule: {config.SCHEDULE_TIME}",
        "info",
    )

    # Start the initial backup task
    logging.info("🔄 Preparing initial backup")
    initial_backup_thread = threading.Thread(
        target=_run_initial_backup_task,
        daemon=True,
        name="Initial-Backup-Thread"
    )
    initial_backup_thread.start()

    # Start the scheduler
    task_scheduler.start(run_now=False)

    logging.info(f"✅ Main logic completed, PID: {os.getpid()}. Program is now running in background.")

def main():
    """Program entry point"""
    global _instance_manager

    # Ensure logging is configured before any other operations
    setup_logging()
    # Log a clear startup entry early, including the PID
    logging.info(f"🏁 Entry point, PID: {os.getpid()}, Args: {sys.argv}")

    # Initialize the single-instance manager and start it (terminates any old instance)
    _instance_manager = init_single_instance_manager()
    if not _instance_manager.start():
        logging.error("❌ Failed to acquire single-instance mutex; exiting.")
        sys.exit(1)

    try:
        setup_console_encoding()
        logging.info("🚀 Program starting")

        # Core business logic
        main_logic()

        # Main loop to keep the program running
        try:
            _last_heartbeat = time.time()
            while True:
                time.sleep(60)
                now = time.time()
                if now - _last_heartbeat >= 3600:
                    _last_heartbeat = now
                    active_threads = threading.enumerate()
                    logging.info(f"ℹ️ Heartbeat, PID: {os.getpid()}, Active threads: {len(active_threads)}")

                    # Log child process information
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

    except SystemExit as e: # Catch exits raised by sys.exit()
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
        # Ensure logs are flushed to disk
        for handler in logging.root.handlers:
            handler.flush()

        # Stop the scheduler
        if task_scheduler.scheduler_thread is not None:
            task_scheduler.stop()
        logging.info(f"🧼 Cleanup finished, PID {os.getpid()}.")

    return 0

if __name__ == "__main__":
    # Handle install / uninstall before logging or singleton setup.
    # These flags are intended for the packaged exe only.
    _args = sys.argv[1:]
    if "--install" in _args:
        _cli_install()          # shows MessageBox, then sys.exit()
    elif "--uninstall" in _args:
        _cli_uninstall()        # shows MessageBox, then sys.exit()

    exit_code = main()
    logging.info(f"👋 Terminated, exit code: {exit_code}. PID: {os.getpid()}")
    sys.exit(exit_code)
