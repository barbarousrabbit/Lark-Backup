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
from datetime import datetime
import threading
import psutil

# Set Python path to ensure modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import configuration and custom modules
from config import config
from core.network import with_network_retry, network_monitor
from core.api_service import api_service
from core.file_manager import file_manager
from core.scheduler import task_scheduler
from core.notification import show_notification
from core.process_manager import init_single_instance_manager
from core.retry_manager import retry_manager
from core.data_comparator import data_comparator
from core.alert_window import alert_manager
from core.report_generator import report_generator

# Global instance manager
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
    """Configure console encoding"""
    if sys.platform.startswith('win'):
        try:
            os.system('chcp 65001 > nul')
        except:
            pass


def _download_and_save(backup_date):
    """Runs the full API pipeline and saves the file. Returns (path, details) or (None, details)."""
    details = {'backup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'attempts': 1}
    try:
        file_manager.ensure_download_dir_exists()
        tenant_token = api_service.get_tenant_token()
        if not tenant_token:
            logging.error("❌ API token failed"); details['error'] = 'token failed'; return None, details
        wiki_data = api_service.get_wiki_data()
        if not wiki_data:
            logging.error("❌ Wiki data failed"); details['error'] = 'wiki failed'; return None, details
        obj_token = api_service.extract_obj_token(wiki_data)
        ticket = api_service.create_export_task(obj_token)
        if not ticket:
            logging.error("❌ Export task failed"); details['error'] = 'export failed'; return None, details
        file_token = api_service.get_export_task_status(ticket, obj_token)
        if not file_token:
            logging.error("❌ File token failed"); details['error'] = 'file token failed'; return None, details
        file_content = api_service.download_file(file_token)
        if not file_content:
            logging.error("❌ Download failed"); details['error'] = 'download failed'; return None, details
        saved_path = file_manager.save_file(file_content, backup_date)
        if saved_path:
            details['file_path'] = saved_path
            details['success'] = True
            try: details['file_size'] = os.path.getsize(saved_path)
            except: pass
            return saved_path, details
        details['error'] = 'save failed'; return None, details
    except ValueError as e:
        logging.error(f"❌ {e}"); details['error'] = str(e); return None, details
    except Exception as e:
        logging.error(f"❌ Backup error: {e}"); logging.error(traceback.format_exc())
        details['error'] = str(e); return None, details


def _compare_and_alert(backup_date):
    """Runs data comparison. Returns (differences, warnings)."""
    try:
        differences, warnings = data_comparator.compare_with_previous_date(backup_date)
        if warnings:
            logging.warning(f"⚠️ {len(warnings)} warnings from comparison")
            alert_manager.check_and_show_alert(differences, warnings, backup_date)
        if differences:
            data_comparator.save_comparison_result(backup_date, {'differences': differences, 'warnings': warnings})
        return differences, warnings
    except Exception as e:
        logging.error(f"❌ Comparison failed: {e}")
        return None, []


def _generate_failure_report(backup_date, error_msg, attempts=1):
    """Generates a failure daily report. Swallows exceptions."""
    try:
        report_generator.generate_daily_report(
            backup_date, False, {'error': error_msg, 'attempts': attempts}, None, None
        )
    except Exception:
        pass


@with_network_retry
def backup_task():
    """Orchestrates one full backup cycle. Returns True on success."""
    logging.info("🔄 Starting backup")
    backup_date = config.get_backup_date()

    saved_path, details = _download_and_save(backup_date)

    if not saved_path:
        _generate_failure_report(backup_date, details.get('error', 'unknown'))
        return False

    logging.info(f"✅ Backup saved: {saved_path}")

    differences, warnings = _compare_and_alert(backup_date)

    try:
        report_generator.generate_daily_report(backup_date, True, details, differences, warnings)
    except Exception as e:
        logging.error(f"❌ Report failed: {e}")

    if warnings:
        show_notification("Data Comparison Alert", f"{len(differences)} changes, {len(warnings)} warnings", "warning")
    elif differences:
        show_notification("Data Comparison Complete", f"{len(differences)} changes", "info")

    show_notification("Backup Successful", f"Saved: {os.path.basename(saved_path)}", "success")
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
    backup_date = config.get_backup_date()

    while True:
        if not retry_manager.can_attempt_today():
            logging.warning(f"⚠️ Daily limit reached ({config.MAX_DAILY_ATTEMPTS} attempts)")
            show_notification("Daily Limit Reached", "All backup attempts exhausted for today", "error")
            _generate_failure_report(backup_date, f"All {config.MAX_DAILY_ATTEMPTS} attempts failed")
            return False

        result = backup_task()
        attempt_count = retry_manager.record_attempt(success=result)

        if result:
            return True

        remaining = retry_manager.get_remaining_attempts()
        if remaining <= 0:
            logging.error(f"❌ Daily attempts exhausted ({config.MAX_DAILY_ATTEMPTS} times)")
            show_notification("Backup Failed", f"All {config.MAX_DAILY_ATTEMPTS} attempts failed today", "error")
            _generate_failure_report(backup_date, f"All {config.MAX_DAILY_ATTEMPTS} attempts failed")
            return False

        logging.warning(f"❌ Failed, {remaining} attempts remaining")
        # If network is down, block here until it recovers before the next attempt.
        # This is the single authoritative retry/recovery path — no background threads.
        if not network_monitor.check_connection():
            network_monitor.wait_for_recovery()
        else:
            logging.info(f"⏱️ Waiting {config.ERROR_RETRY_INTERVAL}s before retry")
            time.sleep(config.ERROR_RETRY_INTERVAL)


def _run_initial_backup_task():
    """Run the initial backup task in a separate thread (with retry)"""
    logging.info("🚀 Initial backup started")
    run_backup_with_retry()
    logging.info("✅ Initial backup completed")

def main_logic():
    """Contains the core business logic"""
    logging.info(f"⚙️ Main logic, PID: {os.getpid()}")

    # Smart reset: if started manually, reset today's retry count
    retry_manager.reset_if_manual_start()

    # Set up and start the task scheduler
    task_scheduler.schedule_daily_task(lambda: run_backup_with_retry())

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
    _instance_manager.start()

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
        if 'task_scheduler' in globals() and task_scheduler.scheduler_thread is not None:
            task_scheduler.stop()
        logging.info(f"🧼 Cleanup finished, PID {os.getpid()}.")

    return 0

if __name__ == "__main__":
    logging.info(f"🎬 Script started, PID: {os.getpid()}")
    exit_code = main()
    logging.info(f"👋 Terminated, exit code: {exit_code}. PID: {os.getpid()}")
    sys.exit(exit_code)
