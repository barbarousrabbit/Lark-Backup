# Lark Backup — Project Rules for Claude

## Project Summary
A scheduled daily job that pulls one Bitable sheet from Lark, saves it as Excel, performs data comparison, and generates a daily HTML report. Windows-only background service; supports PyInstaller single-file exe packaging.

---

## Architecture Overview

```
main.py                    # Entry point: logging init → singleton check → scheduler → main loop
├── core/process_manager   # Named Mutex singleton (Windows OS level)
├── core/scheduler         # schedule library wrapper, fires daily at SCHEDULE_TIME
├── core/retry_manager     # Max MAX_DAILY_ATTEMPTS retries per day, JSON persistence
├── core/network           # Network detection + blocking wait for recovery; @with_network_retry decorator
├── core/api_service       # Lark API: token → wiki → export → download
├── core/file_manager      # File saving, path derived from config.BACKUP_FILENAME_TEMPLATE
├── core/data_comparator   # openpyxl reads xlsx, Counter multiset diff comparison
├── core/alert_window      # data loss alerts via windows-toasts (per-day deduplication)
├── core/notification      # Windows 11 native notifications (windows-toasts + AUMID)
└── core/report_generator  # HTML + JSON daily reports
```

---

## Core Invariants (Must Understand Before Modifying)

### 1. Singleton Mechanism — Named Mutex, Not PID File
`core/process_manager.py` uses the `Global\LarkBackupSingleInstance` named mutex. The OS releases it automatically when the process dies — no zombie lock files. **Do not revert to a PID file approach.**

### 2. Backup Concurrency Mutex — `_backup_lock`
`main.py` holds a module-level `threading.Lock()`; `run_backup_with_retry()` acquires it with `blocking=False`. If a backup is already running (startup thread or scheduled thread), the new trigger immediately returns False and logs — **it does not queue**. **Do not call `backup_task()` directly outside the lock.**

### 3. Retry Control — Single Entry Point `run_backup_with_retry()`
- `run_backup_with_retry()` acquires `_backup_lock` then delegates to `_run_backup_loop()` — the while loop and all retry logic lives in `_run_backup_loop()`
- `backup_date` is computed **once** at the top of `_run_backup_loop()` and passed as a parameter to `backup_task(backup_date)` — prevents midnight drift across retries
- Network recovery waiting is serial-blocking via `network_monitor.wait_for_recovery()` — **no background threads**
- The `@with_network_retry` decorator only performs a pre-call network check; returns None if offline — registers no callbacks

### 4. Module-Level Singletons
These objects are instantiated at the bottom of their modules. **Import and use them directly — do not call `init_xxx()` to create a new instance on every call:**
```python
from core.api_service    import api_service
from core.file_manager   import file_manager
from core.data_comparator import data_comparator
from core.report_generator import report_generator
from core.retry_manager  import retry_manager
from core.notification   import show_notification
from core.alert_window   import alert_manager
from core.network        import network_monitor
from core.scheduler      import task_scheduler
```
The `init_xxx()` factory functions still exist for backward compatibility but return the same singleton object.

### 5. Filename Template — Single Source of Truth in config
There is exactly one authoritative source for backup filenames:
```python
config.BACKUP_FILENAME_TEMPLATE = "Case Management Platform {date}.xlsx"
```
Both `file_manager.py` and `data_comparator.py` derive their paths via `.format(date=date_str)`. **Do not hardcode filenames anywhere in the code.**

### 6. Data Comparison — Counter, Not set
`data_comparator.py::get_data_rows_counter()` returns a `collections.Counter` (multiset); comparison uses Counter subtraction. **Do not revert to set** — sets silently drop additions/deletions of duplicate rows.

### 7. API Credentials Stored in Plaintext (Known Risk, Accepted)
APP_ID / APP_SECRET / TOKEN are hardcoded in plaintext in `config.py` to support zero-configuration single-exe distribution. **Do not introduce runtime environment variable reading** — it breaks the exe user experience.

---

## Development Conventions

### Python Version & Platform
- Python 3.8+, **Windows only**
- Packaging: `pyinstaller LarkBackup.spec` (spec excludes tkinter/customtkinter for a smaller exe)

### Logging
- All logging goes through the standard `logging` module — **do not use print**
- Log format is configured centrally by `main.py::setup_logging()`; other modules **must not call `logging.basicConfig()`**

### HTTP Requests
- All `requests.get/post` calls must include `timeout=30`
- Exceptions should uniformly raise `LarkAPIError` or return None (follow the existing style in `api_service.py`)

### openpyxl
- Always open xlsx files with `read_only=True, data_only=True`
- Workbook operations must use `try-finally: workbook.close()` to guarantee handle release

### Configuration Changes
- Schedule time: `config.SCHEDULE_TIME` (format `HH:MM`)
- Backup directory: `config.DOWNLOAD_DIR`
- Maximum retry attempts: `config.MAX_DAILY_ATTEMPTS`

---

## Common Tasks

### Adding a New Backup Target (Multiple Sheets)
1. Add the new TOKEN to `config.py`
2. Extend parameters in `api_service.py::get_wiki_data()`
3. Call it in a loop inside `main.py::_download_and_save()`

### Changing Notification Content
Edit the callers of `core/notification.py::show_notification(title, message, type)`. Valid types: `"success"` / `"warning"` / `"error"` / `"info"`

### Changing the Alert Threshold (How Many Rows Deleted Before Alert Notification)
`config.py::ALERT_DELETED_ROW_THRESHOLD = 50` — single source; referenced by both `data_comparator.py` and `alert_window.py`

### Changing the Daily Schedule Time
`config.py::SCHEDULE_TIME = "09:00"` (requires restart after change)

### Building a Release Package
```bash
pip install pyinstaller
pyinstaller LarkBackup.spec
# Output: dist/LarkBackup.exe — this is the only file to distribute
```

### Installing / Uninstalling (end-user, packaged exe)
```
LarkBackup.exe --install     # registers HKCU autostart + launches service
LarkBackup.exe --uninstall   # removes autostart + stops service
LarkBackup.exe               # runs backup service directly (no install)
```
CLI is handled in `main.py::_cli_install()` / `_cli_uninstall()` before logging or singleton setup.

---

## Prohibited Actions

- **Do not** call `sleep()` inside `backup_task()` to wait for retries — all retry timing is controlled in `run_backup_with_retry()`
- **Do not** spawn background threads inside the `@with_network_retry` decorator
- **Do not** call `logging.basicConfig()` at the top level of any `core/` module
- **Do not** use a local variable named `html` inside functions — it conflicts with the stdlib `import html` (historical bug, already fixed)
- **Do not** add new `init_xxx()` factory functions that return new instances — all core objects must be module-level singletons
- **Do not** treat `job_status=2` as a terminal error in `api_service.py::get_export_task_status()` — the Lark export API returns `status=2` transiently on first polls before the file is ready; **`file_token` presence is the sole success condition**; break only on timeout or HTTP error (regression history: commit `dfb9829` introduced this bug, `aba248e` fixed it)

---

## Technical Debt / Known Issues

| Item | Status | Notes |
|---|---|---|
| No automated tests | Pending | Key scenarios: network interruption recovery, duplicate-row comparison, dual-instance contention |
| `_is_scheduled_time()` time-window check | Acceptable | 5-minute window distinguishes manual vs. scheduled start; cross-midnight bug already fixed |
| No cleanup mechanism for report directory | Pending | Daily_Reports/ and JSON reports have no automatic expiration/deletion |
| `AUTH_URL` uses `open.feishu.cn`, all other API URLs use `open.larksuite.com` | Acceptable | Cross-domain token works in practice (Feishu/Lark share backend); verified end-to-end. Make consistent if API failures appear |
| `count_data_rows()` breaks on first empty row | Acceptable | Assumes contiguous data (valid for Lark-exported xlsx); sparse sheets would under-count rows |

---

## Language Policy

**All project content must be in English** — this includes:
- Source code comments and docstrings
- Log messages and exception strings
- UI labels and button text
- HTML report content
- Documentation files (README.md, UserGuide.txt, CLAUDE.md)
- Shell/batch scripts (echo messages, REM comments)

**Conversation language** follows the user's input language (Chinese input → Chinese reply).

Do not write Chinese in any file committed to the repository. If you find Chinese in existing code while making other changes, translate it in the same commit.
