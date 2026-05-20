"""
Modern alert window module
Uses customtkinter to create a polished warning interface

UI dependencies are loaded lazily: if customtkinter / tkinter is unavailable
(headless environment, not installed, etc.), the module can still be imported
and AlertManager degrades to log-only mode.
"""

import os
import sys
import threading
import logging
from typing import List, Dict, Optional

# Lazy-load UI dependencies; fall back to log-only mode on failure
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
    """Modern alert window"""

    def __init__(self, title: str = "Data Backup Alert", icon_path: Optional[str] = None):
        """
        Initialize the alert window

        Args:
            title: Window title
            icon_path: Path to the icon file
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
        Display a data loss alert

        Args:
            warnings: List of warning messages
            differences: Dictionary of data differences
        """
        if self.is_showing:
            return

        self.is_showing = True

        # Show window in a new thread to avoid blocking the main program
        alert_thread = threading.Thread(
            target=self._create_and_show_window,
            args=(warnings, differences)
        )
        alert_thread.start()

    def _create_and_show_window(self, warnings: List[str], differences: Dict[str, Dict]):
        """
        Create and display the window (runs in a separate thread)
        """
        try:
            # Create the main window
            self.root = ctk.CTk()
            self.root.title(self.title)
            self.root.geometry("600x600")

            # Set minimum window size
            self.root.minsize(600, 400)

            # Set window icon
            self._set_window_icon()

            # Center the window
            self._center_window()

            # Create main frame
            main_frame = ctk.CTkFrame(self.root, corner_radius=0)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)

            # Header area (pinned to top)
            self._create_header(main_frame)

            # Button area (pinned to bottom) — created first to ensure visibility
            self._create_button_section(main_frame)

            # Warning content area (flexible) — created last to fill remaining space
            self._create_warning_section(main_frame, warnings)

            # Bind window close event
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

            # Bring window to front
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))

            # Run the main loop
            self.root.mainloop()

        except Exception as e:
            logging.error(f"❌ Error creating alert window: {e}")
        finally:
            self.is_showing = False

    def _set_window_icon(self):
        """Set the window icon"""
        try:
            if os.path.exists(self.icon_path):
                # Set icon on Windows
                if sys.platform.startswith('win'):
                    self.root.iconbitmap(self.icon_path)
                else:
                    # Use PhotoImage on other platforms
                    icon = PhotoImage(file=self.icon_path)
                    self.root.iconphoto(True, icon)
        except Exception as e:
            logging.warning(f"⚠️ Could not set window icon: {e}")

    def _center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        # Use preset dimensions rather than querying current size
        width = 600
        height = 600
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _create_header(self, parent):
        """Create the header area"""
        # Main header frame — gradient background effect, reduced height
        header_frame = ctk.CTkFrame(
            parent,
            fg_color=("#FF6B6B", "#E74C3C"),
            corner_radius=15,
            height=70
        )
        header_frame.pack(fill="x", pady=(0, 25), padx=5)
        header_frame.pack_propagate(False)

        # Content container
        content_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=12)

        # Title row — icon, title, subtitle, and timestamp on one line
        title_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        title_row.pack(fill="x", expand=True)

        # Warning icon
        icon_label = ctk.CTkLabel(
            title_row,
            text="⚠",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        icon_label.pack(side="left", pady=10)

        # Main title and subtitle container
        title_container = ctk.CTkFrame(title_row, fg_color="transparent")
        title_container.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # Main title
        title_label = ctk.CTkLabel(
            title_container,
            text="Data Backup Alert",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
            anchor="w"
        )
        title_label.pack(fill="x", pady=10)

        # Timestamp
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
        """Create the warning content area"""
        # Warning container — card style, flexible area
        warning_frame = ctk.CTkFrame(
            parent,
            fg_color=("#FFF8E1", "#FFF3C4"),
            corner_radius=12,
            border_width=1,
            border_color=("#FFB74D", "#FFA726")
        )
        warning_frame.pack(fill="both", expand=True, pady=(0, 20), padx=5)

        # Warning title row
        title_frame = ctk.CTkFrame(warning_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=15, pady=(15, 10))

        # Warning icon and title
        warning_icon = ctk.CTkLabel(
            title_frame,
            text="🚨",
            font=ctk.CTkFont(size=18)
        )
        warning_icon.pack(side="left")

        warning_title = ctk.CTkLabel(
            title_frame,
            text="Issues Detected",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("#F57F17", "#FF8F00")
        )
        warning_title.pack(side="left", padx=(8, 0))

        # Warning count badge
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

        # Scrollable warning list container
        scroll_frame = ctk.CTkScrollableFrame(
            warning_frame,
            fg_color="transparent",
            scrollbar_button_color=("#FFB74D", "#FFA726"),
            scrollbar_button_hover_color=("#FF9800", "#F57C00")
        )
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Warning list
        for i, warning in enumerate(warnings, 1):
            # Container for each warning item
            item_frame = ctk.CTkFrame(
                scroll_frame,
                fg_color=("white", "#FFFDE7"),
                corner_radius=8,
                height=45
            )
            item_frame.pack(fill="x", pady=3)
            item_frame.pack_propagate(False)

            # Item number
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

            # Warning text — clean up and normalize phrasing
            warning_text = warning.replace("⚠️ ", "").replace("worksheet", "sheet")
            warning_text = warning_text.replace("(exceeds threshold of 50)", "")
            warning_text = warning_text.replace("exceeds threshold of 50", "")
            warning_text = warning_text.replace("(significant data reduction)", "")
            warning_text = warning_text.replace("threshold", "expected value")
            # Remove extra whitespace
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
        """Create the button area"""
        # Button container — clean design, fixed height
        button_container = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            height=80
        )
        button_container.pack(side="bottom", fill="x", pady=(10, 10))
        button_container.pack_propagate(False)  # Prevent height from being overridden by children

        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)

        # Help text
        help_label = ctk.CTkLabel(
            button_frame,
            text="💡 Please review the backup file to verify data changes are expected",
            font=ctk.CTkFont(size=11),
            text_color=("#6C757D", "#ADB5BD")
        )
        help_label.pack(anchor="w", pady=(0, 12))

        # Button row
        btn_row = ctk.CTkFrame(button_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        # View Backup Folder button
        view_btn = ctk.CTkButton(
            btn_row,
            text="📁 View Backup Folder",
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

        # Spacer
        spacer = ctk.CTkLabel(btn_row, text="", width=15, fg_color="transparent")
        spacer.pack(side="left")

        # Acknowledged button
        acknowledge_btn = ctk.CTkButton(
            btn_row,
            text="✓ Acknowledged",
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

        # Dismiss button (secondary option)
        ignore_btn = ctk.CTkButton(
            btn_row,
            text="Dismiss",
            command=self._on_acknowledge,  # Also closes the window
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
        """User clicked the 'Acknowledged' button"""
        logging.info("✅ User acknowledged data warning")
        self._on_close()

    def _on_view_files(self):
        """Open the backup folder"""
        try:
            from config import config
            backup_dir = config.DOWNLOAD_DIR
            if os.path.exists(backup_dir):
                os.startfile(backup_dir)
                logging.info(f"📁 Opened backup directory: {backup_dir}")
        except Exception as e:
            logging.error(f"❌ Error opening backup directory: {e}")

    def _on_close(self):
        """Close the window"""
        if self.root:
            self.root.quit()
            self.root.destroy()
            self.root = None
        self.is_showing = False

class AlertManager:
    """Alert manager responsible for controlling alert window display"""

    def __init__(self):
        """Initialize the alert manager"""
        self.alert_window = None
        self.last_alert_date = None

    def check_and_show_alert(self, comparison_result: Dict, warnings: List[str], date_str: str):
        """
        Check conditions and show alert if warranted

        Args:
            comparison_result: Comparison result dictionary
            warnings: List of warning messages
            date_str: Date string
        """
        # Avoid showing duplicate alerts on the same day
        if self.last_alert_date == date_str:
            return

        if warnings and len(warnings) > 0:
            # Filter sheets where deleted row count exceeds the threshold (consistent with data_comparator alert criteria)
            significant_changes = {
                sheet: info for sheet, info in comparison_result.items()
                if info.get('deleted_count', 0) > 50
            }

            if significant_changes:
                logging.warning(f"🚨 Data loss alert for {date_str}: {warnings}")
                self.last_alert_date = date_str

                if not _UI_AVAILABLE:
                    # No GUI environment — degrade to log-only output
                    for w in warnings:
                        logging.warning(f"🚨 {w}")
                    return

                if not self.alert_window:
                    self.alert_window = AlertWindow()

                self.alert_window.show_data_loss_alert(warnings, significant_changes)

# Create global instance
alert_manager = AlertManager()
