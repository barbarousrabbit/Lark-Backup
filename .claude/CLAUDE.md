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
- `backup_date` is recomputed at the top of **each** retry iteration in `_run_backup_loop()`, and `_download_and_save()` re-derives it once more right before saving — a snapshot is always labeled by its capture date. Rationale: an attempt that resumed after a multi-day system sleep used to file Monday's data under the Friday name (observed 2026-06); per-attempt recomputation fixes between-attempt drift, the save-time check fixes mid-attempt drift. **Do not revert to computing it once per loop**
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

### 6. Data Comparison — Counter + reset_dimensions, Not set
`data_comparator.py::get_all_sheet_counters()` builds one `collections.Counter` (multiset) per sheet in a single streaming pass; comparison uses Counter subtraction. **Do not revert to set** — sets silently drop additions/deletions of duplicate rows.

Two hard rules learned from a silent total failure (comparison was dead from inception until fixed on 2026-07-03):
- **`sheet.reset_dimensions()` is mandatory** before iterating a read-only sheet — Lark's exporter writes a bogus `<dimension ref="A1"/>` on every sheet, and openpyxl read-only mode trusts it, yielding ZERO rows.
- **Never break early on a blank row** — real exports contain interior blank rows (e.g. a sheet whose row 2 is empty with 265 data rows below); every row must be scanned.
- If a backup file cannot be read, the comparison must ABORT with a warning — degrading to an empty Counter would count every row of the other file as deleted and fire a false data-loss alert.

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

### Changing the Alert Threshold (Net Row Loss Before Alert Notification)
`config.py::ALERT_DELETED_ROW_THRESHOLD = 50` — single source; referenced by both `data_comparator.py` (warnings) and `alert_window.py` (toast filter). The alert fires when a sheet's row count NET-declines by more than this vs the previous day. **Do not alert on Counter-level `deleted_count`** — volatile computed columns (e.g. day counters) rewrite thousands of rows daily, so Counter-deleted ≈ "rows modified" and alerting on it fires every day (observed 2026-07-03: 26k "deleted" rows that were all modifications).

### Changing Backup Retention
Three constants in `config.py`, applied by `file_manager.cleanup_old_backups()` after each successful backup (age = the filename `{date}` token, not mtime):
- `RETENTION_DAILY_DAYS = 30` — newer than this: keep every backup
- `RETENTION_WEEKLY_DAYS = 180` — keep the earliest backup of each ISO week (Monday when present)
- `RETENTION_MONTHLY_DAYS = 730` — keep the earliest backup of each month; older files are deleted
Only files matching `BACKUP_FILENAME_TEMPLATE` (canonical or `_HHMMSS` fallback) are ever touched.

### Changing the Daily Schedule Time
`config.py::SCHEDULE_TIME = "09:00"` (requires restart after change)

### Building a Release Package

**Before every build — mandatory cleanup (in this order):**
1. Stop the running service: run `disable_autostart.vbs` (or kill via Task Manager)
2. Remove autostart registry entry: `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v LarkBackup /f` (ignore "not found" error)
3. Delete the installed directory on D: drive (e.g. `D:\LarkBackup\`) — ensures the next install test is clean

```bash
pip install pyinstaller
pyinstaller LarkBackup.spec
# Output: dist/LarkBackup.exe — this is the only file to distribute
```

**Distribution zip name is always `LarkBackup.zip` — no date suffix, no version suffix.** Overwrite the existing file each time.
The zip must contain exactly: `LarkBackup.exe`, `enable_autostart.vbs`, `disable_autostart.vbs`, `UserGuide.txt`.

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
- **Do not** include a date or version in the distribution zip filename — it is always `LarkBackup.zip`
- **Do not** treat `job_status=2` as a terminal error in `api_service.py::get_export_task_status()` — the Lark export API returns `status=2` transiently on first polls before the file is ready; **`file_token` presence is the sole success condition**; break only on timeout or HTTP error (regression history: commit `dfb9829` introduced this bug, `aba248e` fixed it)
- **Do not** remove `sheet.reset_dimensions()` or reintroduce break-on-first-blank-row scanning in `data_comparator.py` — Lark xlsx declares a bogus `<dimension ref="A1"/>` and contains interior blank rows; either change silently kills the entire comparison/alert feature again (regression history: dead from inception until 2026-07-03 because of exactly this)

---

## Technical Debt / Known Issues

| Item | Status | Notes |
|---|---|---|
| No automated tests | Pending | Key scenarios: network interruption recovery, duplicate-row comparison, dual-instance contention |
| `_is_scheduled_time()` time-window check | Acceptable | 5-minute window distinguishes manual vs. scheduled start; cross-midnight bug already fixed |
| No cleanup for Daily_Reports/ | Acceptable | ~10 KB/day, negligible; backup xlsx retention IS implemented (see Common Tasks → Changing Backup Retention) |
| `AUTH_URL` uses `open.feishu.cn`, all other API URLs use `open.larksuite.com` | Acceptable | Cross-domain token works in practice (Feishu/Lark share backend); verified end-to-end. Make consistent if API failures appear |
| Comparison takes ~7 min on 200+ MB exports | Acceptable | One full streaming pass per file (~3.5 min each, measured 2026-07-03); runs in the backup thread after the file is saved, nothing blocks on it |

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
