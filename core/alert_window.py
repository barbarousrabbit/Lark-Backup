"""
Alert Module
Handles data loss alerts via system notifications with per-day deduplication.

Replaces the previous customtkinter popup window. All alerts are delivered
through the windows-toasts notification system (show_notification),
keeping the distributed exe lean and dependency-free of any GUI toolkit.
"""

import logging
from typing import Dict, List

from config import config
from core.notification import show_notification


class AlertManager:
    """
    Manages data loss alert notifications with per-day deduplication.

    Only fires when at least one sheet NET-shrank by more than
    config.ALERT_DELETED_ROW_THRESHOLD rows (consistent with
    data_comparator's warning rule — Counter-level "deleted" alone is noisy
    because volatile computed columns rewrite rows daily).
    At most one alert is shown per date per process lifetime.
    """

    def __init__(self):
        self.last_alert_date = None

    def check_and_show_alert(
        self,
        comparison_result: Dict,
        warnings: List[str],
        date_str: str,
    ) -> None:
        """
        Show a data loss alert if significant deletions are detected.

        Args:
            comparison_result: Sheet-level comparison data from data_comparator.
            warnings: Human-readable warning strings already produced by comparator.
            date_str: Backup date — used to suppress duplicate alerts on the same day.
        """
        if self.last_alert_date == date_str:
            return

        if not warnings:
            return

        significant_changes = {
            sheet: info for sheet, info in comparison_result.items()
            if (info.get('before', 0) - info.get('after', 0)) > config.ALERT_DELETED_ROW_THRESHOLD
        }

        if not significant_changes:
            return

        self.last_alert_date = date_str

        total_loss = sum(v.get('before', 0) - v.get('after', 0) for v in significant_changes.values())
        n_sheets = len(significant_changes)
        sheet_label = "sheet" if n_sheets == 1 else "sheets"

        logging.warning(f"🚨 Data loss alert for {date_str}: {warnings}")
        show_notification(
            "Data Loss Alert",
            f"{total_loss} rows lost across {n_sheets} {sheet_label}",
            "error",
        )


# Global singleton
alert_manager = AlertManager()
