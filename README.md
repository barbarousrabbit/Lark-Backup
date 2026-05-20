# Lark Backup Tool

A Python-based backup tool for Lark (Feishu) Bitable sheets. Automatically backs up Bitable data to local storage on a scheduled basis. Windows only.

## Features

- **Scheduled backup**: Runs a backup task automatically at a configured time each day
- **Immediate backup**: Executes one backup run immediately on program start
- **Data safety**: Local storage prevents data loss
- **Easy configuration**: Customize backup settings by editing a single config file
- **Singleton mode**: Process management ensures only one instance runs; re-launching automatically replaces the old instance
- **Lightweight notification system**: Integrated notification mechanism with no subprocess overhead
- **Auto network recovery**: Automatically resumes downloads after network interruption
- **English notifications**: System tray notifications displayed entirely in English
- **Subprocess management**: Intelligently tracks and cleans up child processes to prevent orphan processes
- **Enhanced logging**: Improved logging system ensures logs are written correctly and are easy to troubleshoot
- **Data comparison**: Automatically compares backup data across different dates to detect changes
- **Data loss warning**: Pops up an alert window when more than 50 rows are deleted
- **Modern UI**: Uses customtkinter to create a polished alert interface
- **Daily reports**: Automatically generates detailed HTML reports for each day's backup and comparison, saved in the Daily_Reports folder inside the backup directory
- **Smart notifications**: Uses win10toast for reliable system notifications with distinct success/failure/warning types

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
│   └── alert_window.py     # Alert window module
│
├── main.py                 # Program entry point
├── requirements.txt        # Dependency list
└── README.md               # Project documentation
```

## Installation & Usage

### Method 1: Use the Pre-built Release

1. Download the latest release package: `LarkBackup_yyyy-mm-dd.zip`
2. Extract to any directory
3. Run `LarkBackup.exe` to start the program; it will execute one backup immediately
4. The program continues running in the background and performs scheduled backups as configured
5. To add the program to Windows startup, run `install_autostart.bat`

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
APP_ID = "cli_a735216a7178d009"  # Lark bot ID
APP_SECRET = "CVk3xzJcAbhhdtxiR5yNIhsoPT68h3nv"  # Lark bot secret key
TOKEN = "VewzwjbYbirFTWkrSjyuUvfZs8w"  # WIKI token

# Schedule configuration
SCHEDULE_TIME = "01:00"  # Daily scheduled task time, format: HH:MM
```

## Building a Distribution Package

Use PyInstaller to create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=assets/file_download.ico main.py
```

## Dependencies

- Python 3.8+
- requests - API requests
- schedule - Task scheduling
- psutil - Process monitoring
- win10toast - System notifications
- openpyxl - Excel file handling
- customtkinter - Modern UI components
- Pillow - Image processing


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
 