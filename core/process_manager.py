"""
Process Manager Module
Named Mutex-based single instance guard (Windows).

Why Named Mutex instead of PID file:
- OS automatically releases the mutex when the process dies (crash, taskkill, normal exit)
- No stale lock file possible
- No PID-reuse false positives
- Acquisition is atomic at the OS level
"""

import os
import sys
import time
import ctypes
import logging
import psutil
import atexit

MUTEX_NAME = "Global\\LarkBackupSingleInstance"

# Win32 constants
ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080   # owner died without releasing — we still get ownership
WAIT_TIMEOUT = 0x00000102


class SingleInstanceManager:
    """
    Windows Named Mutex-based single-instance manager.

    On start():
      - No existing mutex  → create + own it immediately.
      - Mutex exists       → another instance is live; kill it, wait for mutex
                             to be abandoned/released, then take ownership.

    On process death (any cause): OS releases the mutex automatically.
    atexit handler does a clean release for graceful shutdowns.
    """

    def __init__(self):
        self._mutex_handle = None
        self.own_pid = os.getpid()
        logging.info(f"🆔 Current process ID: {self.own_pid}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Acquire the single-instance mutex, killing any existing instance first."""
        # bInitialOwner=True: if we create a new mutex, we own it immediately.
        # If one already exists, CreateMutexW returns a handle to it but
        # GetLastError() == ERROR_ALREADY_EXISTS and we do NOT own it.
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
        err = ctypes.windll.kernel32.GetLastError()

        if err == 0:
            # Brand-new mutex — we own it.
            self._mutex_handle = handle
            atexit.register(self.cleanup)
            logging.info(f"✅ Single instance acquired (PID: {self.own_pid})")
            return True

        if err == ERROR_ALREADY_EXISTS:
            logging.info("🔄 Another instance is running — terminating it…")
            self._kill_existing_instance()

            # Wait up to 5 s for the old process to die and abandon the mutex.
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, 5000)

            if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
                # We now own the mutex.
                self._mutex_handle = handle
                atexit.register(self.cleanup)
                logging.info(f"✅ Took over from old instance (PID: {self.own_pid})")
                return True

            # 5 s timeout — old process is still alive.
            # Try once more; if still contested, refuse to start (avoid dual instances).
            logging.warning("⚠️ Mutex wait timed out; making final acquisition attempt")
            ctypes.windll.kernel32.CloseHandle(handle)
            handle2 = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
            final_err = ctypes.windll.kernel32.GetLastError()
            if final_err == ERROR_ALREADY_EXISTS:
                ctypes.windll.kernel32.CloseHandle(handle2)
                logging.error("❌ Cannot acquire single-instance mutex — old process still running. Exiting.")
                sys.exit(1)
            self._mutex_handle = handle2
            atexit.register(self.cleanup)
            logging.info(f"✅ Single instance acquired after timeout retry (PID: {self.own_pid})")
            return True

        logging.error(f"❌ CreateMutexW failed (error {err})")
        return False

    def cleanup(self):
        """Release the mutex on graceful exit. Also called automatically by atexit."""
        if self._mutex_handle:
            ctypes.windll.kernel32.ReleaseMutex(self._mutex_handle)
            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None
            logging.info("🧹 Released single-instance mutex")
        for handler in logging.root.handlers:
            try:
                handler.flush()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _kill_existing_instance(self):
        """Find and terminate the existing instance by exe path or script path."""
        if getattr(sys, 'frozen', False):
            own_exe = os.path.abspath(sys.executable).lower()

            def is_target(proc):
                exe = (proc.info.get('exe') or '').lower()
                return exe == own_exe
        else:
            own_script = os.path.abspath(sys.argv[0]).lower()

            def is_target(proc):
                cmdline = proc.info.get('cmdline') or []
                return (
                    len(cmdline) >= 2
                    and 'python' in (cmdline[0] or '').lower()
                    and os.path.abspath(cmdline[-1]).lower() == own_script
                )

        for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
            if proc.pid == self.own_pid:
                continue
            try:
                if is_target(proc):
                    self._terminate(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def _terminate(self, proc):
        """Terminate a process tree: children first, then parent."""
        try:
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            proc.terminate()
            proc.wait(timeout=3)
            logging.info(f"✅ Terminated old instance (PID: {proc.pid})")
        except psutil.TimeoutExpired:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def init_single_instance_manager(pid_file=None):
    """Factory function. pid_file parameter kept for backward compatibility."""
    return SingleInstanceManager()
