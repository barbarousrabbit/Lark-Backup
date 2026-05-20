# Lark Backup — Project Rules for Claude

## 项目一句话描述
每天定时从飞书（Lark）拉取一张多维表格（Bitable）并保存为 Excel，同时做数据对比和每日 HTML 报告。Windows 专用后台服务，支持 PyInstaller 打包为单文件 exe。

---

## 架构速览

```
main.py                    # 入口：日志初始化 → 单例检查 → 调度 → 主循环
├── core/process_manager   # Named Mutex 单例（Windows OS 级）
├── core/scheduler         # schedule 库封装，每天 SCHEDULE_TIME 触发
├── core/retry_manager     # 每日最多 MAX_DAILY_ATTEMPTS 次重试，JSON 持久化
├── core/network           # 网络检测 + 阻塞等待恢复；@with_network_retry 装饰器
├── core/api_service       # 飞书 API：token → wiki → export → download
├── core/file_manager      # 文件保存，路径派生自 config.BACKUP_FILENAME_TEMPLATE
├── core/data_comparator   # openpyxl 读取 xlsx，Counter 多重集差异对比
├── core/alert_window      # customtkinter 弹窗（无 GUI 时降级为日志）
├── core/notification      # win10toast 系统通知
└── core/report_generator  # HTML + JSON 每日报告
```

---

## 核心不变量（修改前必须理解）

### 1. 单例机制 — Named Mutex，不是 PID 文件
`core/process_manager.py` 使用 `Global\LarkBackupSingleInstance` 命名互斥量。OS 在进程死亡时自动释放，不存在僵尸锁。**不要改回 PID 文件方案**。

### 2. 备份并发互斥 — `_backup_lock`
`main.py` 中有一个模块级 `threading.Lock()`，`run_backup_with_retry()` 以 `blocking=False` 方式尝试获取。若已有备份在运行（初始线程或定时线程），新触发直接返回 False 并记录日志，**不排队等待**。**不要在锁外直接调用 `backup_task()`**。

### 3. 重试控制 — 唯一入口 `run_backup_with_retry()`
- 重试调度只在 `main.py::run_backup_with_retry()` 的 while 循环中进行
- 网络恢复等待通过 `network_monitor.wait_for_recovery()` 串行阻塞，**不起后台线程**
- `@with_network_retry` 装饰器仅做调用前网络前置检查，网络不通返回 None，不注册任何回调

### 3. 模块级单例
这些对象在模块底部实例化，**直接 import 使用，不要在每次调用时 `init_xxx()` 新建实例**：
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
`init_xxx()` 工厂函数仍存在以保持向后兼容，但它们返回的是同一个单例对象。

### 4. 文件命名模板 — 集中在 config
备份文件名只有一个权威来源：
```python
config.BACKUP_FILENAME_TEMPLATE = "Case Management Platform {date}.xlsx"
```
`file_manager.py` 和 `data_comparator.py` 都通过 `.format(date=date_str)` 派生路径，**不要在代码中硬编码文件名**。

### 5. 数据对比 — Counter，不是 set
`data_comparator.py::get_data_rows_counter()` 返回 `collections.Counter`（多重集），对比使用 Counter 减法。**不要改回 set**，set 会吞掉重复行的增删。

### 6. UI 依赖降级
`alert_window.py` 用 `try/except` 延迟导入 customtkinter。`_UI_AVAILABLE = False` 时静默降级为日志输出。**不要在模块顶层直接 `import customtkinter`**。

### 7. API 凭据明文存放（已知风险，接受现状）
`config.py` 中 APP_ID / APP_SECRET / TOKEN 明文硬编码，这是为了支持无配置的 exe 一键分发。**不要引入运行时环境变量读取**，会破坏 exe 用户体验。

---

## 开发约定

### Python 版本 & 平台
- Python 3.8+，**仅 Windows**
- 打包：`pyinstaller --onefile --noconsole --icon=assets/file_download.ico main.py`

### 日志
- 所有日志通过标准 `logging` 模块，**不要用 print**
- 日志格式由 `main.py::setup_logging()` 统一配置，其他模块**不要调用 `logging.basicConfig()`**

### HTTP 请求
- 所有 `requests.get/post` 必须带 `timeout=30`
- 异常统一 raise `LarkAPIError` 或返回 None（参照 `api_service.py` 现有风格）

### openpyxl
- 始终用 `read_only=True, data_only=True` 打开 xlsx
- workbook 操作必须用 `try-finally: workbook.close()` 确保句柄释放

### 配置修改
- 调度时间：`config.SCHEDULE_TIME`（格式 `HH:MM`）
- 备份目录：`config.DOWNLOAD_DIR`
- 最大重试次数：`config.MAX_DAILY_ATTEMPTS`

---

## 常见任务

### 添加新的备份目标（多张表）
1. 在 `config.py` 增加新 TOKEN
2. 在 `api_service.py::get_wiki_data()` 扩展参数
3. 在 `main.py::_download_and_save()` 循环调用

### 修改通知内容
编辑 `core/notification.py::show_notification(title, message, type)` 的调用方，类型：`"success"` / `"warning"` / `"error"` / `"info"`

### 修改报警阈值（数据减少多少条触发弹窗）
`core/data_comparator.py::compare_two_dates()` 中 `if deleted_count > 50`

### 修改每日定时时间
`config.py::SCHEDULE_TIME = "09:00"`（修改后需重启）

### 打包发布
```bash
pip install pyinstaller
pyinstaller LarkBackup.spec   # 使用已有 spec 文件
```

---

## 禁止事项

- **不要** 在 `backup_task()` 里直接 `sleep()` 等待重试 — 统一在 `run_backup_with_retry()` 里控制
- **不要** 在 `@with_network_retry` 装饰器里 spawn 后台线程
- **不要** 在 `core/` 模块的顶层调用 `logging.basicConfig()`
- **不要** 在函数里用局部变量 `html` — 与 stdlib `import html` 冲突（历史 bug，已修复）
- **不要** 新增 `init_xxx()` 工厂函数返回新实例 — 所有核心对象应为模块级单例

---

## 技术债 / 已知缺陷

| 项目 | 状态 | 说明 |
|---|---|---|
| 无自动化测试 | 待补充 | 重点场景：网络中断恢复、重复行对比、双实例争抢 |
| `_is_scheduled_time()` 时间窗口判断 | 可接受 | 5 分钟窗口检测手动 vs 定时启动，已修复跨午夜 bug |
| 报告目录无清理机制 | 待补充 | Daily_Reports/ 和 JSON 报告无自动过期删除 |
