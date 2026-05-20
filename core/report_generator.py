"""
每日报告生成模块
生成备份和数据对比的详细报告
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import html

from config import config

class ReportGenerator:
    """报告生成器"""

    def __init__(self, backup_dir: str):
        """
        初始化报告生成器

        Args:
            backup_dir: 备份文件目录
        """
        self.backup_dir = backup_dir
        self.report_dir = os.path.join(backup_dir, "Daily_Reports")
        self._ensure_report_dir()

    def _ensure_report_dir(self):
        """确保报告目录存在"""
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
        生成每日报告

        Args:
            date_str: 日期字符串
            backup_success: 备份是否成功
            backup_details: 备份详情
            comparison_result: 对比结果
            warnings: 警告信息

        Returns:
            报告文件路径
        """
        try:
            report_filename = f"Report_{date_str}.html"
            report_path = os.path.join(self.report_dir, report_filename)

            # 生成HTML报告
            html_content = self._generate_html_report(
                date_str,
                backup_success,
                backup_details,
                comparison_result,
                warnings
            )

            # 保存报告
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logging.info(f"📝 Report saved: {report_path}")

            # 同时生成JSON格式的报告用于程序化访问
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
        """生成HTML格式的报告"""

        # 备份状态
        backup_status = "✅ 成功" if backup_success else "❌ 失败"
        backup_status_color = "#4CAF50" if backup_success else "#f44336"

        # 生成对比结果HTML
        comparison_html = self._generate_comparison_html(comparison_result, warnings)

        # 备份详情
        backup_details_html = self._generate_backup_details_html(backup_details)

        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>备份报告 - {date_str}</title>
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
            <h1>📊 飞书备份每日报告</h1>
            <div class="date">{date_str}</div>
            <div class="status-badge">备份状态: {backup_status}</div>
        </div>

        <div class="content">
            <!-- 备份详情 -->
            <div class="section">
                <h2 class="section-title">📁 备份详情</h2>
                {backup_details_html}
            </div>

            <!-- 数据对比结果 -->
            <div class="section">
                <h2 class="section-title">🔍 数据对比分析</h2>
                {comparison_html}
            </div>
        </div>

        <div class="footer">
            <div>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="timestamp">Lark Backup System © 2025</div>
        </div>
    </div>
</body>
</html>"""

        return html_template

    def _generate_backup_details_html(self, backup_details: Dict[str, Any]) -> str:
        """生成备份详情HTML"""
        if not backup_details:
            return '<div class="info-box">无备份详情信息</div>'

        content = '<div class="info-box">'

        # 添加备份文件路径
        if 'file_path' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">备份文件:</span>
                    <span class="info-value">{os.path.basename(backup_details['file_path'])}</span>
                </div>'''

        # 添加备份时间
        if 'backup_time' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">备份时间:</span>
                    <span class="info-value">{backup_details['backup_time']}</span>
                </div>'''

        # 添加文件大小
        if 'file_size' in backup_details:
            size_mb = backup_details['file_size'] / (1024 * 1024)
            content += f'''
                <div class="info-row">
                    <span class="info-label">文件大小:</span>
                    <span class="info-value">{size_mb:.2f} MB</span>
                </div>'''

        # 添加尝试次数
        if 'attempts' in backup_details:
            content += f'''
                <div class="info-row">
                    <span class="info-label">尝试次数:</span>
                    <span class="info-value">{backup_details['attempts']} 次</span>
                </div>'''

        content += '</div>'

        # 如果有错误信息
        if 'error' in backup_details:
            content += f'<div class="error-box">错误: {html.escape(backup_details["error"])}</div>'

        return content

    def _generate_comparison_html(self, comparison_result: Optional[Dict], warnings: Optional[List[str]]) -> str:
        """生成对比结果HTML"""
        content = ""

        # 显示警告信息
        if warnings and len(warnings) > 0:
            content += '<div class="warning-box"><ul>'
            for warning in warnings:
                content += f'<li>{html.escape(warning)}</li>'
            content += '</ul></div>'

        # 显示对比结果表格
        if comparison_result:
            content += '''
            <table class="data-table">
                <thead>
                    <tr>
                        <th>工作表</th>
                        <th>昨天数据量</th>
                        <th>今天数据量</th>
                        <th>变化</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>'''

            for sheet_name, diff_info in comparison_result.items():
                before = diff_info.get('before', 0)
                after = diff_info.get('after', 0)
                difference = diff_info.get('difference', 0)

                if difference < 0:
                    change_class = "decrease"
                    change_symbol = "↓"
                    status = "数据减少"
                elif difference > 0:
                    change_class = "increase"
                    change_symbol = "↑"
                    status = "数据增加"
                else:
                    change_class = "unchanged"
                    change_symbol = "→"
                    status = "无变化"

                content += f'''
                    <tr>
                        <td>{html.escape(sheet_name)}</td>
                        <td>{before}</td>
                        <td>{after}</td>
                        <td class="{change_class}">{change_symbol} {abs(difference)}</td>
                        <td>{status}</td>
                    </tr>'''

            content += '</tbody></table>'
        else:
            content += '<div class="success-box">✅ 数据对比正常，未发现异常变化</div>'

        return content

    def get_recent_reports(self, days: int = 7) -> List[Dict]:
        """
        获取最近几天的报告

        Args:
            days: 天数

        Returns:
            报告列表
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

    def generate_weekly_summary(self) -> str:
        """生成周报摘要"""
        reports = self.get_recent_reports(7)

        if not reports:
            return None

        # 统计信息
        total_backups = len(reports)
        successful_backups = sum(1 for r in reports if r['backup']['success'])
        failed_backups = total_backups - successful_backups
        total_warnings = sum(len(r.get('warnings', [])) for r in reports)

        summary = {
            "period": f"{(datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}",
            "total_backups": total_backups,
            "successful_backups": successful_backups,
            "failed_backups": failed_backups,
            "total_warnings": total_warnings,
            "success_rate": f"{(successful_backups/total_backups*100):.1f}%" if total_backups > 0 else "0%"
        }

        summary_path = os.path.join(self.report_dir, f"Weekly_Summary_{datetime.now().strftime('%Y-%m-%d')}.json")

        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary_path

# 全局单例
report_generator = ReportGenerator(config.DOWNLOAD_DIR)

def init_report_generator(backup_dir: str) -> ReportGenerator:
    """初始化并获取报告生成器（返回全局单例）"""
    return report_generator
