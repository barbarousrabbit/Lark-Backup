# Lark Backup Tool

A Python-based Windows tool that automatically backs up Lark (Feishu) Bitable sheets to local storage on a daily schedule.

## Features

- **Scheduled backup**: Automatically runs a backup at a configured daily schedule
- **Immediate backup**: Executes one backup run on program start without waiting for the schedule
- **Data safety**: Local storage prevents data loss
- **Easy configuration**: All settings are controlled by a single config file
- **Singleton mode**: Only one instance runs at a time; relaunching automatically replaces the running instance
- **Lightweight notifications**: System tray notifications with no subprocess overhead
- **Network recovery**: Automatically resumes the backup after a network interruption
- **Subprocess management**: Tracks and cleans up child processes to prevent orphans
- **Enhanced logging**: Ensures logs are written correctly and are easy to troubleshoot
- **Data comparison**: Compares backup data across dates to detect changes and deletions
- **Data loss alerts**: Sends an error notification when more than 50 rows are deleted from any sheet
- **Daily reports**: Generates detailed HTML and JSON reports saved in the `Daily_Reports` folder
- **Smart notifications**: Uses windows-toasts (WinRT) with distinct success/warning/error notification types

## File Structure

The project uses a modular design with the following directory layout:

```
LarkBackup/
│
├── assets/                 # Static assets
│   └── file_download.ico   # Application icon
│
├── config/                 # Configuration directory
│   └── config.py           # Configuration parameters
│
├── core/                   # Core functional modules
│   ├── api_service.py      # API service
│   ├── file_manager.py     # File management
│   ├── process_manager.py  # Process manager
│   ├── network.py          # Network requests
│   ├── notification.py     # Notification module
│   ├── scheduler.py        # Task scheduler
│   ├── data_comparator.py  # Data comparison module
│   ├── alert_window.py     # Data loss alert notifications
│   ├── retry_manager.py    # Daily retry counting
│   └── report_generator.py # HTML + JSON daily reports
│
├── main.py                 # Program entry point
├── requirements.txt        # Dependency list
└── README.md               # Project documentation
```

## Installation & Usage

### Method 1: Use the Pre-built Release (single exe)

```
LarkBackup.exe               # start the backup service immediately
LarkBackup.exe --install     # register Windows autostart + start service
LarkBackup.exe --uninstall   # remove autostart + stop service
```

Typical first-time setup:

1. Copy `LarkBackup.exe` to any permanent folder (e.g. `C:\Tools\LarkBackup\`)
2. Run `LarkBackup.exe --install` — registers autostart and starts the service (a "Backup Service Started" notification confirms it is running)
3. Done. The service runs silently in the background and backs up every day at the configured time

### Method 2: Run from Source

1. Clone the repository or download the source code
2. Install dependencies: `pip install -r requirements.txt`
3. Run the program: `python main.py`

## Configuration

Edit `config/config.py` to configure backup parameters:

```python
# File configuration
DOWNLOAD_DIR = "D:\\Case Management Platform Backup"  # File save location
# Log files are automatically saved in the logs folder under the program directory

# API configuration
APP_ID = "your_app_id_here"        # Lark bot App ID
APP_SECRET = "your_app_secret_here"  # Lark bot App Secret
TOKEN = "your_wiki_token_here"     # Lark Wiki node token

# Schedule configuration
SCHEDULE_TIME = "09:00"  # Daily scheduled task time, format: HH:MM
```

## Building a Distribution Package

Use the provided spec file (recommended — excludes unused GUI toolkits for a smaller exe):

```bash
pip install pyinstaller
pyinstaller LarkBackup.spec
```

## Dependencies

- Python 3.8+
- requests - API requests
- schedule - Task scheduling
- psutil - Process monitoring
- windows-toasts - Windows 11 native system notifications (WinRT)
- openpyxl - Excel file handling


## Notes

- Windows operating system only
- Correct API parameters must be configured before first run
- Backup files are saved by default to the configured `DOWNLOAD_DIR`
- Log files are saved in the `logs` folder under the program directory
- Data comparison results are cached in `data_comparison_cache.json`
- Daily reports are saved in the `Daily_Reports` folder inside the backup directory, in both HTML and JSON formats
- Each report includes backup status, data comparison results, warnings, and detailed statistics
- The program is designed to run in the background with no visible window
- The singleton mechanism uses a Windows Named Mutex; the OS releases it automatically on abnormal process exit — no stale lock files
- If the program is launched again while already running, the new instance automatically terminates the old one and takes over — no manual intervention needed
- If log files are empty, check write permissions for the application directory
 