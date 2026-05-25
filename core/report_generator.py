"""
Daily report generation module.
Generates detailed reports for backup and data comparison results.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import html

from config import config

class ReportGenerator:
    """Report generator"""

    def __init__(self, backup_dir: str):
        """
        Initialize the report generator.

        Args:
            backup_dir: Directory where backup files are stored
        """
        self.backup_dir = backup_dir
        self.report_dir = os.path.join(backup_dir, "Daily_Reports")
        self._ensure_report_dir()

    def _ensure_report_dir(self):
        """Ensure the report directory exists."""
        try:
            if not os.path.exists(self.report_dir):
                os.makedirs(self.report_dir, exist_ok=True)
                logging.info(f"✅ Created report directory: {self.report_dir}")
        except Exception as e:
            logging.error(f"❌ Failed to create report directory: {e}")

    def generate_daily_report(
        self,
        date_str: str,
        backup_success: bool,
        backup_details: Dict[str, Any],
        comparison_result: Optional[Dict] = None,
        warnings: Optional[List[str]] = None
    ) -> str:
        """
        Generate a daily report.

        Args:
            date_str: Date string
            backup_success: Whether the backup succeeded
            backup_details: Backup details
            comparison_result: Comparison result
            warnings: Warning messages

        Returns:
            Path to the report file
        """
        try:
            report_filename = f"Report_{date_str}.html"
            report_path = os.path.join(self.report_dir, report_filename)

            # Generate HTML report
            html_content = self._generate_html_report(
                date_str,
                backup_success,
                backup_details,
                comparison_result,
                warnings
            )

            # Save report
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logging.info(f"📝 Report saved: {report_path}")

            # Also generate a JSON report for programmatic access
            json_filename = f"Report_{date_str}.json"
            json_path = os.path.join(self.report_dir, json_filename)

            json_data = {
                "date": date_str,
                "timestamp": datetime.now().isoformat(),
                "backup": {
                    "success": backup_success,
                    "details": backup_details
                },
                "comparison": comparison_result,
                "warnings": warnings
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            return report_path

        except Exception as e:
            logging.error(f"❌ Failed to generate report: {e}")
            return None

    def _generate_html_report(
        self,
        date_str: str,
        backup_success: bool,
        backup_details: Dict[str, Any],
        comparison_result: Optional[Dict],
        warnings: Optional[List[str]]
    ) -> str:
        """Generate an HTML-format report."""

        # Backup status
        backup_status = "✅ Success" if backup_success else "❌ Failed"
        backup_status_color = "#4CAF50" if backup_success else "#f44336"

        # Generate comparison result HTML
        comparison_html = self._generate_comparison_html(comparison_result, warnings)

        # Backup details
        backup_details_html = self._generate_backup_details_html(backup_details)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backup Report - {date_str}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header .date {{
            font-size: 16px;
            opacity: 0.9;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 15px;
            background: {backup_status_color};
            color: white;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 20px;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .info-box {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .info-row:last-child {{
            border-bottom: none;
        }}
        .info-label {{
            color: #666;
            font-weight: 500;
        }}
        .info-value {{
            color: #333;
            font-weight: bold;
        }}
        .warning-box {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }}
        .warning-box ul {{
            list-style: none;
            padding-left: 0;
        }}
        .warning-box li {{
            padding: 5px 0;
            color: #856404;
        }}
        .warning-box li:before {{
            content: "⚠️ ";
            margin-right: 5px;
        }}
        .success-box {{
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            color: #155724;
        }}
        .error-box {{
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            color: #721c24;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .data-table th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        .data-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .data-table tr:hover {{
            background: #f5f5f5;
        }}
        .decrease {{
            color: #dc3545;
            font-weight: bold;
        }}
        .increase {{
            color: #28a745;
            font-weight: bold;
        }}
        .unchanged {{
            color: #6c757d;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .timestamp {{
            color: #999;
            font-size: 12px;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Lark Backup Daily Report</h1>
            <div class="date">{date_str}</div>
            <div class="status-badge">Backup Status: {backup_status}</div>
        </div>

        <div class="content">
            <!-- Backup Details -->
            <div class="section">
                <h2 class="section-title">📁 Backup Details</h2>
                {backup_details_html}
            </div>

            <!-- Data Comparison Results -->
            <div class="section">
                <h2 class="section-title">🔍 Data Comparison</h2>
                {comparison_html}
            </div>
        </div>

        <div class="footer">
            <div>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="timestamp">Lark Backup System © {datetime.now().year}</div>
        </div>
    </div>
</body>
</html>"""

        return html_template

    def _generate_backup_details_html(self, backup_details: Dict[str, Any]) -> str:
        """Generate backup details HTML."""
        if not backup_details:
            return '<div class="info-box">No backup details available</div>'

        content = '<div class="info-box">'

        # Add backup file path
        if 'file_path' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">Backup File:</span>
                    <span class="info-value">{html.escape(os.path.basename(backup_details['file_path']))}</span>
                </div>'''

        # Add backup time
        if 'backup_time' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">Backup Time:</span>
                    <span class="info-value">{html.escape(backup_details['backup_time'])}</span>
                </div>'''

        # Add file size
        if 'file_size' in backup_details:
            size_mb = backup_details['file_size'] / (1024 * 1024)
            content += f'''
                <div class="info-row">
                    <span class="info-label">File Size:</span>
                    <span class="info-value">{size_mb:.2f} MB</span>
                </div>'''

        # Add attempt count
        if 'attempts' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">Attempts:</span>
                    <span class="info-value">{backup_details['attempts']}</span>
                </div>'''

        content += '</div>'

        # If there is an error message
        if 'error' in backup_details:
            content += f'<div class="error-box">Error: {html.escape(backup_details["error"])}</div>'

        return content

    def _generate_comparison_html(self, comparison_result: Optional[Dict], warnings: Optional[List[str]]) -> str:
        """Generate comparison result HTML."""
        content = ""

        # Display warnings
        if warnings and len(warnings) > 0:
            content += '<div class="warning-box"><ul>'
            for warning in warnings:
                content += f'<li>{html.escape(warning)}</li>'
            content += '</ul></div>'

        # Display comparison result table
        if comparison_result:
            content += '''
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Sheet</th>
                        <th>Previous</th>
                        <th>Current</th>
                        <th>Net Change</th>
                        <th>Deleted</th>
                        <th>Added</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>'''

            for sheet_name, diff_info in comparison_result.items():
                before = diff_info.get('before', 0)
                after = diff_info.get('after', 0)
                difference = diff_info.get('difference', 0)
                deleted_count = diff_info.get('deleted_count', 0)
                added_count = diff_info.get('added_count', 0)

                if difference < 0:
                    change_class = "decrease"
                    change_symbol = "↓"
                    status = "Decreased"
                elif difference > 0:
                    change_class = "increase"
                    change_symbol = "↑"
                    status = "Increased"
                else:
                    change_class = "unchanged"
                    change_symbol = "→"
                    status = "Unchanged"

                deleted_class = "decrease" if deleted_count > 0 else "unchanged"
                added_class = "increase" if added_count > 0 else "unchanged"

                content += f'''
                    <tr>
                        <td>{html.escape(sheet_name)}</td>
                        <td>{before}</td>
                        <td>{after}</td>
                        <td class="{change_class}">{change_symbol} {abs(difference)}</td>
                        <td class="{deleted_class}">{deleted_count}</td>
                        <td class="{added_class}">{added_count}</td>
                        <td>{status}</td>
                    </tr>'''

            content += '</tbody></table>'
        elif not warnings:
            # Only show success message when there are neither differences nor warnings.
            # If warnings are present but comparison_result is empty (e.g. previous file missing),
            # the warning box above already describes the situation — a "no changes" success
            # message here would contradict it.
            content += '<div class="success-box">✅ No significant changes detected</div>'

        return content

    def get_recent_reports(self, days: int = 7) -> List[Dict]:
        """
        Get reports from the last N days.

        Args:
            days: Number of days

        Returns:
            List of reports
        """
        reports = []
        today = datetime.now()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            json_path = os.path.join(self.report_dir, f"Report_{date_str}.json")

            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                        reports.append(report_data)
                except Exception as e:
                    logging.error(f"❌ Failed to load report {json_path}: {e}")

        return reports

# Global singleton
report_generator = ReportGenerator(config.DOWNLOAD_DIR)

def init_report_generator(backup_dir: str) -> ReportGenerator:
    """Initialize and return the report generator (returns global singleton)."""
    return report_generator
