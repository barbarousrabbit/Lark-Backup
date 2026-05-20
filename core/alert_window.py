"""
现代化警告窗口模块
使用customtkinter创建美观的警告界面

UI 依赖延迟加载：若 customtkinter / tkinter 不可用（无 GUI 环境、未安装等），
模块仍可正常导入，AlertManager 降级为仅记录日志。
"""

import os
import sys
import threading
import logging
from typing import List, Dict, Optional

# 延迟导入 UI 依赖，失败时降级为日志模式
try:
    import customtkinter as ctk
    from tkinter import PhotoImage
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    _UI_AVAILABLE = True
except Exception as _ui_err:
    logging.warning(f"⚠️ GUI unavailable ({_ui_err}); alert window disabled, will log only")
    _UI_AVAILABLE = False
    ctk = None

class AlertWindow:
    """现代化的警告窗口"""
    
    def __init__(self, title: str = "数据备份警告", icon_path: Optional[str] = None):
        """
        初始化警告窗口
        
        Args:
            title: 窗口标题
            icon_path: 图标文件路径
        """
        self.title = title
        self.icon_path = icon_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "file_download.ico"
        )
        self.root = None
        self.is_showing = False
        
    def show_data_loss_alert(self, warnings: List[str], differences: Dict[str, Dict]):
        """
        显示数据丢失警告
        
        Args:
            warnings: 警告消息列表
            differences: 数据差异字典
        """
        if self.is_showing:
            return
            
        self.is_showing = True
        
        # 在新线程中显示窗口，避免阻塞主程序
        alert_thread = threading.Thread(
            target=self._create_and_show_window,
            args=(warnings, differences)
        )
        alert_thread.start()
    
    def _create_and_show_window(self, warnings: List[str], differences: Dict[str, Dict]):
        """
        创建并显示窗口（在单独线程中运行）
        """
        try:
            # 创建主窗口
            self.root = ctk.CTk()
            self.root.title(self.title)
            self.root.geometry("600x600")
            
            # 设置窗口最小尺寸
            self.root.minsize(600, 400)
            
            # 设置窗口图标
            self._set_window_icon()
            
            # 窗口居中
            self._center_window()
            
            # 创建主框架
            main_frame = ctk.CTkFrame(self.root, corner_radius=0)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # 标题区域（固定在顶部）
            self._create_header(main_frame)
            
            # 按钮区域（固定在底部）- 先创建以确保可见
            self._create_button_section(main_frame)
            
            # 警告信息区域（可变化区域）- 最后创建以填充剩余空间
            self._create_warning_section(main_frame, warnings)
            
            # 设置窗口关闭事件
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            
            # 将窗口置于最前
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
            
            # 运行主循环
            self.root.mainloop()
            
        except Exception as e:
            logging.error(f"❌ Error creating alert window: {e}")
        finally:
            self.is_showing = False
    
    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            if os.path.exists(self.icon_path):
                # Windows平台设置图标
                if sys.platform.startswith('win'):
                    self.root.iconbitmap(self.icon_path)
                else:
                    # 其他平台使用PhotoImage
                    icon = PhotoImage(file=self.icon_path)
                    self.root.iconphoto(True, icon)
        except Exception as e:
            logging.warning(f"⚠️ Could not set window icon: {e}")
    
    def _center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        # 使用预设的尺寸而不是获取当前尺寸
        width = 600
        height = 600
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_header(self, parent):
        """创建标题区域"""
        # 主标题框架 - 渐变色背景效果，减小高度
        header_frame = ctk.CTkFrame(
            parent, 
            fg_color=("#FF6B6B", "#E74C3C"),
            corner_radius=15,
            height=70
        )
        header_frame.pack(fill="x", pady=(0, 25), padx=5)
        header_frame.pack_propagate(False)
        
        # 内容容器
        content_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=12)
        
        # 标题行 - 图标、标题、副标题和时间在一行
        title_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        title_row.pack(fill="x", expand=True)
        
        # 警告图标
        icon_label = ctk.CTkLabel(
            title_row,
            text="⚠",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        icon_label.pack(side="left", pady=10)
        
        # 主标题和副标题容器
        title_container = ctk.CTkFrame(title_row, fg_color="transparent")
        title_container.pack(side="left", fill="both", expand=True, padx=(10, 0))
        
        # 主标题
        title_label = ctk.CTkLabel(
            title_container,
            text="数据备份警告",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
            anchor="w"
        )
        title_label.pack(fill="x", pady=10)
        
        # 时间戳
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_label = ctk.CTkLabel(
            title_row,
            text=timestamp,
            font=ctk.CTkFont(size=11),
            text_color=("white", "#E0E0E0")
        )
        time_label.pack(side="right", pady=10)
    
    def _create_warning_section(self, parent, warnings: List[str]):
        """创建警告信息区域"""
        # 警告容器 - 卡片风格，可变化区域
        warning_frame = ctk.CTkFrame(
            parent,
            fg_color=("#FFF8E1", "#FFF3C4"),
            corner_radius=12,
            border_width=1,
            border_color=("#FFB74D", "#FFA726")
        )
        warning_frame.pack(fill="both", expand=True, pady=(0, 20), padx=5)
        
        # 警告标题行
        title_frame = ctk.CTkFrame(warning_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        # 警告图标和标题
        warning_icon = ctk.CTkLabel(
            title_frame,
            text="🚨",
            font=ctk.CTkFont(size=18)
        )
        warning_icon.pack(side="left")
        
        warning_title = ctk.CTkLabel(
            title_frame,
            text="检测到以下问题",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("#F57F17", "#FF8F00")
        )
        warning_title.pack(side="left", padx=(8, 0))
        
        # 警告数量徽章
        count_badge = ctk.CTkLabel(
            title_frame,
            text=str(len(warnings)),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white",
            fg_color=("#FF5722", "#E64A19"),
            corner_radius=10,
            width=25,
            height=25
        )
        count_badge.pack(side="right")
        
        # 警告列表滚动容器
        scroll_frame = ctk.CTkScrollableFrame(
            warning_frame,
            fg_color="transparent",
            scrollbar_button_color=("#FFB74D", "#FFA726"),
            scrollbar_button_hover_color=("#FF9800", "#F57C00")
        )
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # 警告列表
        for i, warning in enumerate(warnings, 1):
            # 每个警告项的容器
            item_frame = ctk.CTkFrame(
                scroll_frame,
                fg_color=("white", "#FFFDE7"),
                corner_radius=8,
                height=45
            )
            item_frame.pack(fill="x", pady=3)
            item_frame.pack_propagate(False)
            
            # 序号
            number_label = ctk.CTkLabel(
                item_frame,
                text=str(i),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="white",
                fg_color=("#FF9800", "#F57C00"),
                corner_radius=12,
                width=24,
                height=24
            )
            number_label.pack(side="left", padx=(15, 10), pady=10)
            
            # 警告文本 - 清理和优化表达
            warning_text = warning.replace("⚠️ ", "").replace("工作表", "表格")
            warning_text = warning_text.replace("（超过 50 条阈值）", "")
            warning_text = warning_text.replace("超过 50 条阈值", "")
            warning_text = warning_text.replace("（数据明显减少）", "")
            warning_text = warning_text.replace("阈值", "预期值")
            # 清理多余空格
            warning_text = " ".join(warning_text.split())
            warning_item = ctk.CTkLabel(
                item_frame,
                text=warning_text,
                font=ctk.CTkFont(size=12),
                text_color=("#E65100", "#BF360C"),
                anchor="w",
                justify="left"
            )
            warning_item.pack(side="left", fill="x", expand=True, padx=(0, 15), pady=10)
    
    def _create_button_section(self, parent):
        """创建按钮区域"""
        # 按钮容器 - 简洁设计，固定高度
        button_container = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            height=80
        )
        button_container.pack(side="bottom", fill="x", pady=(10, 10))
        button_container.pack_propagate(False)  # 防止高度被子元素改变
        
        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)
        
        # 帮助文本
        help_label = ctk.CTkLabel(
            button_frame,
            text="💡 建议立即检查备份文件，确认数据变化是否正常",
            font=ctk.CTkFont(size=11),
            text_color=("#6C757D", "#ADB5BD")
        )
        help_label.pack(anchor="w", pady=(0, 12))
        
        # 按钮行
        btn_row = ctk.CTkFrame(button_frame, fg_color="transparent")
        btn_row.pack(fill="x")
        
        # 查看备份文件按钮
        view_btn = ctk.CTkButton(
            btn_row,
            text="📁 查看备份文件",
            command=self._on_view_files,
            width=140,
            height=38,
            font=ctk.CTkFont(size=13),
            fg_color=("#6C757D", "#495057"),
            hover_color=("#5A6268", "#3D4145"),
            corner_radius=10,
            border_width=0
        )
        view_btn.pack(side="left")
        
        # 分隔空间
        spacer = ctk.CTkLabel(btn_row, text="", width=15, fg_color="transparent")
        spacer.pack(side="left")
        
        # 我已了解按钮
        acknowledge_btn = ctk.CTkButton(
            btn_row,
            text="✓ 我已了解",
            command=self._on_acknowledge,
            width=120,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#007BFF", "#0056B3"),
            hover_color=("#0056B3", "#004085"),
            corner_radius=10,
            border_width=0
        )
        acknowledge_btn.pack(side="right")
        
        # 忽略此次按钮（次要选项）
        ignore_btn = ctk.CTkButton(
            btn_row,
            text="忽略此次",
            command=self._on_acknowledge,  # 同样关闭窗口
            width=80,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=("#F8F9FA", "#2D2D2D"),
            text_color=("#6C757D", "#ADB5BD"),
            corner_radius=8,
            border_width=1,
            border_color=("#DEE2E6", "#495057")
        )
        ignore_btn.pack(side="right", padx=(0, 10))
    
    def _on_acknowledge(self):
        """用户点击"我已了解"按钮"""
        logging.info("✅ User acknowledged data warning")
        self._on_close()
    
    def _on_view_files(self):
        """打开备份文件夹"""
        try:
            from config import config
            backup_dir = config.DOWNLOAD_DIR
            if os.path.exists(backup_dir):
                os.startfile(backup_dir)
                logging.info(f"📁 Opened backup directory: {backup_dir}")
        except Exception as e:
            logging.error(f"❌ Error opening backup directory: {e}")
    
    def _on_close(self):
        """关闭窗口"""
        if self.root:
            self.root.quit()
            self.root.destroy()
            self.root = None
        self.is_showing = False

class AlertManager:
    """警告管理器，用于管理警告窗口的显示"""
    
    def __init__(self):
        """初始化警告管理器"""
        self.alert_window = None
        self.last_alert_date = None
        
    def check_and_show_alert(self, comparison_result: Dict, warnings: List[str], date_str: str):
        """
        检查并显示警告
        
        Args:
            comparison_result: 对比结果
            warnings: 警告消息列表
            date_str: 日期字符串
        """
        # 避免同一天重复显示警告
        if self.last_alert_date == date_str:
            return
            
        if warnings and len(warnings) > 0:
            # 筛选出原始删除行数超过阈值的工作表（与 data_comparator 告警口径一致）
            significant_changes = {
                sheet: info for sheet, info in comparison_result.items()
                if info.get('deleted_count', 0) > 50
            }

            if significant_changes:
                logging.warning(f"🚨 Data loss alert for {date_str}: {warnings}")
                self.last_alert_date = date_str

                if not _UI_AVAILABLE:
                    # 无 GUI 环境，降级为日志输出
                    for w in warnings:
                        logging.warning(f"🚨 {w}")
                    return

                if not self.alert_window:
                    self.alert_window = AlertWindow()
                
                self.alert_window.show_data_loss_alert(warnings, significant_changes)

# 创建全局实例
alert_manager = AlertManager()

