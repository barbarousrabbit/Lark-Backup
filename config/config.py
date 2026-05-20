"""
Lark Backup 配置文件
包含程序所需的所有配置参数
"""

import os
import sys
from datetime import datetime, timedelta

# API配置
APP_ID = "cli_a735216a7178d009"  # Lark机器人ID
APP_SECRET = "CVk3xzJcAbhhdtxiR5yNIhsoPT68h3nv"  # Lark机器人安全码
TOKEN = "VewzwjbYbirFTWkrSjyuUvfZs8w"  # WIKI的Token

# 文件配置
DOWNLOAD_DIR = "D:\\Case Management Platform Backup"  # 文件保存地址
BACKUP_FILENAME_TEMPLATE = "Case Management Platform {date}.xlsx"

# 获取程序实际运行目录（支持exe环境）
def get_program_dir():
    """获取程序目录，兼容开发环境和exe打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller打包后的临时目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 将日志文件保存在程序目录下的logs文件夹
LOG_FILE = os.path.join(get_program_dir(), "logs", "LarkBackupLog.log")  # 日志文件完整路径

# 调度配置
SCHEDULE_TIME = "09:00"  # 设置每天定时任务的时间，格式：HH:MM

# 调试配置
DEBUG_MODE = False  # 设置为True启用调试模式
if DEBUG_MODE:
    # 调试模式下，每5分钟执行一次任务，方便测试调度
    now = datetime.now()
    test_time = (now + timedelta(minutes=5)).strftime("%H:%M")
    SCHEDULE_TIME = test_time
    
# 网络配置
NETWORK_CHECK_HOSTS = [
    ("open.feishu.cn", 443),  # 主要检测飞书服务器
    ("www.baidu.com", 443)    # 备用检测
]
NETWORK_CHECK_TIMEOUT = 3  # 网络连接检查超时时间（秒）
NETWORK_RETRY_INITIAL_INTERVAL = 30  # 断网后首次检查网络的间隔（秒）
NETWORK_RETRY_MAX_INTERVAL = 300  # 断网后最大检查间隔（秒）
NETWORK_RETRY_MULTIPLIER = 1.5  # 检查间隔递增倍数
MAX_RETRY_TIMES = 3  # 断网恢复后最大重试次数

# API URLs
AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
WIKI_API_URL = "https://open.larksuite.com/open-apis/wiki/v2/spaces/get_node"
EXPORT_TASK_URL = "https://open.larksuite.com/open-apis/drive/v1/export_tasks"
DOWNLOAD_URL_TEMPLATE = "https://open.larksuite.com/open-apis/drive/v1/export_tasks/file/{}/download"
EXPORT_TASK_STATUS_URL_TEMPLATE = "https://open.larksuite.com/open-apis/drive/v1/export_tasks/{}?token={}"

# 高级配置
MAX_EXPORT_STATUS_CHECKS = 40  # 轮询40次检查（10分钟）
EXPORT_STATUS_CHECK_INTERVAL = 15  # 15秒检查间隔
SCHEDULE_CHECK_INTERVAL = 30  # 定时任务检查的间隔（秒）
ERROR_RETRY_INTERVAL = 60  # 发生错误后的重试间隔（秒）

# 每日重试配置
MAX_DAILY_ATTEMPTS = 5  # 每天最多尝试次数
# 将重试记录文件保存在程序目录下
RETRY_COUNT_FILE = os.path.join(get_program_dir(), "daily_retry_count.json")  # 每日重试次数记录文件

# 生成派生配置
def get_export_task_status_url(ticket, obj_token):
    """根据ticket和obj_token生成查询导出任务状态的URL"""
    return EXPORT_TASK_STATUS_URL_TEMPLATE.format(ticket, obj_token)

def get_download_url(file_token):
    """根据file_token生成下载URL"""
    return DOWNLOAD_URL_TEMPLATE.format(file_token)

 

def get_backup_date():
    """获取备份文件应该使用的日期（前一天）"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d") 