"""
Lark Backup Configuration File
Contains all configuration parameters required by the program
"""

import os
import sys
from datetime import datetime, timedelta

# API configuration
APP_ID = "cli_a735216a7178d009"  # Lark bot App ID
APP_SECRET = "CVk3xzJcAbhhdtxiR5yNIhsoPT68h3nv"  # Lark bot App Secret
TOKEN = "VewzwjbYbirFTWkrSjyuUvfZs8w"  # Wiki token

# File configuration
DOWNLOAD_DIR = "D:\\Case Management Platform Backup"  # Local directory for backup files
BACKUP_FILENAME_TEMPLATE = "Case Management Platform {date}.xlsx"

# Get the actual program runtime directory (supports exe environment)
def get_program_dir():
    """Get the program directory, compatible with both development and PyInstaller exe environments"""
    if hasattr(sys, '_MEIPASS'):
        # Temporary directory created by PyInstaller after packaging
        return os.path.dirname(sys.executable)
    else:
        # Development environment
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Save the log file in the logs folder under the program directory
LOG_FILE = os.path.join(get_program_dir(), "logs", "LarkBackupLog.log")  # Full path to the log file

# Scheduling configuration
SCHEDULE_TIME = "09:00"  # Daily scheduled task time, format: HH:MM

# Debug configuration
DEBUG_MODE = False  # Set to True to enable debug mode
if DEBUG_MODE:
    # In debug mode, run the task every 5 minutes to facilitate scheduler testing
    now = datetime.now()
    test_time = (now + timedelta(minutes=5)).strftime("%H:%M")
    SCHEDULE_TIME = test_time

# Network configuration
# Both API domains must be reachable for a backup to succeed: auth lives on
# open.feishu.cn, all data APIs on open.larksuite.com. check_connection()
# requires ALL hosts listed here (see core/network.py), so a partial outage
# (e.g. larksuite blocked while feishu is fine) counts as "network down" and
# waits for recovery instead of burning the daily retry quota.
NETWORK_CHECK_HOSTS = [
    ("open.larksuite.com", 443),  # data APIs: wiki / export / download
    ("open.feishu.cn", 443),      # auth API (tenant_access_token)
]
NETWORK_CHECK_TIMEOUT = 3  # Network connection check timeout (seconds)
NETWORK_RETRY_INITIAL_INTERVAL = 30  # Initial retry interval after network loss (seconds)
NETWORK_RETRY_MAX_INTERVAL = 300  # Maximum retry interval after network loss (seconds)
NETWORK_RETRY_MULTIPLIER = 1.5  # Multiplier for exponential backoff of retry interval
ALERT_DELETED_ROW_THRESHOLD = 50  # Fire a data-loss alert when deleted rows exceed this

# API URLs
AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
WIKI_API_URL = "https://open.larksuite.com/open-apis/wiki/v2/spaces/get_node"
EXPORT_TASK_URL = "https://open.larksuite.com/open-apis/drive/v1/export_tasks"
DOWNLOAD_URL_TEMPLATE = "https://open.larksuite.com/open-apis/drive/v1/export_tasks/file/{}/download"
EXPORT_TASK_STATUS_URL_TEMPLATE = "https://open.larksuite.com/open-apis/drive/v1/export_tasks/{}?token={}"

# Advanced configuration
MAX_EXPORT_STATUS_CHECKS = 40  # Poll up to 40 times (10 minutes)
EXPORT_STATUS_CHECK_INTERVAL = 15  # 15-second check interval
SCHEDULE_CHECK_INTERVAL = 30  # Interval for scheduler tick checks (seconds)
ERROR_RETRY_INTERVAL = 60  # Retry interval after an error occurs (seconds)

# Daily retry configuration
MAX_DAILY_ATTEMPTS = 5  # Maximum number of attempts per day
# Save the retry count file in the program directory
RETRY_COUNT_FILE = os.path.join(get_program_dir(), "daily_retry_count.json")  # Daily retry count record file

# Derived configuration helpers
def get_export_task_status_url(ticket, obj_token):
    """Generate the export task status query URL from ticket and obj_token"""
    return EXPORT_TASK_STATUS_URL_TEMPLATE.format(ticket, obj_token)

def get_download_url(file_token):
    """Generate the download URL from file_token"""
    return DOWNLOAD_URL_TEMPLATE.format(file_token)



def get_backup_date():
    """Get the date that should be used for the backup file (yesterday)"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")