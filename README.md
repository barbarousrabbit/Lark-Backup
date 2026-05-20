# Lark 备份工具

基于Python开发的飞书多维表格数据备份工具，可自动定期备份飞书多维表格数据到本地，支持Windows系统。

## 项目特点

- **自动备份**：设定计划任务，定时执行备份
- **即时备份**：程序启动时立即执行一次备份任务
- **数据安全**：本地存储，防止数据丢失
- **易于配置**：简单的配置文件修改即可自定义备份
- **单例模式**：使用进程管理机制确保程序单例运行，重复启动会自动替换旧实例
- **轻量通知系统**：直接集成的通知机制，无需子进程，减少资源占用
- **断网自动恢复**：支持断网后自动恢复下载功能
- **英语通知**：系统托盘全英文通知提醒
- **子进程管理**：智能跟踪和清理子进程，避免进程残留
- **增强日志**：改进的日志系统，确保日志正确写入并便于故障排查
- **数据对比功能**：自动对比不同日期的备份数据，检测数据变化
- **数据丢失警告**：当数据减少超过50条时自动弹出警告窗口
- **现代化UI**：使用customtkinter创建美观的警告界面
- **每日报告**：自动生成每日备份和对比的详细HTML报告，保存在备份目录的Daily_Reports文件夹中
- **智能通知**：使用win10toast提供稳定的系统通知，区分成功/失败/警告类型

## 文件结构

项目采用模块化设计，目录结构如下：

```
LarkBackup/
│
├── assets/                 # 资源文件
│   └── file_download.ico   # 程序图标
│
├── config/                 # 配置文件目录
│   └── config.py           # 配置参数
│
├── core/                   # 核心功能模块
│   ├── api_service.py      # API服务
│   ├── file_manager.py     # 文件管理
│   ├── process_manager.py  # 进程管理器
│   ├── network.py          # 网络请求
│   ├── notification.py     # 通知模块
│   ├── scheduler.py        # 任务调度器
│   ├── data_comparator.py  # 数据对比模块
│   └── alert_window.py     # 警告窗口模块
│
├── main.py                 # 程序入口
├── requirements.txt        # 依赖列表
└── README.md               # 项目说明
```

## 安装与使用

### 方法1：使用预编译版本

1. 下载最新的发布包：`LarkBackup_yyyy-mm-dd.zip`
2. 解压到任意目录
3. 运行`LarkBackup.exe`启动程序，程序将立即执行一次备份任务
4. 程序启动后会在后台持续运行，并按照配置执行定时备份任务
5. 需要添加到Windows启动项，请运行`install_autostart.bat`

### 方法2：从源码运行

1. 克隆仓库或下载源码
2. 安装依赖：`pip install -r requirements.txt`
3. 运行程序：`python main.py`

## 配置说明

编辑`config/config.py`文件配置备份参数：

```python
# 文件配置
DOWNLOAD_DIR = "D:\\Case Management Platform Backup"  # 文件保存地址
# 日志文件会自动保存在程序目录下的logs文件夹中

# API配置
APP_ID = "cli_a735216a7178d009"  # Lark机器人ID
APP_SECRET = "CVk3xzJcAbhhdtxiR5yNIhsoPT68h3nv"  # Lark机器人安全码
TOKEN = "VewzwjbYbirFTWkrSjyuUvfZs8w"  # WIKI的Token

# 调度配置
SCHEDULE_TIME = "01:00"  # 设置每天定时任务的时间，格式：HH:MM
```

## 构建分发包

使用PyInstaller创建独立可执行文件：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=assets/file_download.ico main.py
```

## 依赖项

- Python 3.8+
- requests - API请求
- schedule - 任务调度
- psutil - 进程监控
- win10toast - 系统通知
- openpyxl - Excel文件处理
- customtkinter - 现代化UI组件
- Pillow - 图像处理


## 注意事项

- 仅支持Windows操作系统
- 首次运行需要配置正确的API参数
- 备份文件默认保存在配置的DOWNLOAD_DIR目录
- 日志文件保存在程序目录下的logs文件夹中
- 数据对比结果缓存在data_comparison_cache.json文件中
- 每日报告保存在备份目录下的Daily_Reports文件夹中，包含HTML和JSON格式
- 每个报告包含备份状态、数据对比结果、警告信息和详细统计
- 程序设计为在后台运行，无窗口界面
- PID文件`LarkBackup.pid`保存在可执行文件所在目录，需要确保该目录有写入权限
- 当重复启动程序时，新实例会自动替换旧实例，无需手动终止旧实例
- 每次启动程序都会自动清理之前的旧PID文件
- 当移动可执行文件到新位置时，PID文件会自动在新位置创建，无需额外操作
- 如果日志文件为空，请检查应用程序所在目录的写入权限
 