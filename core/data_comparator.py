"""
数据对比模块
用于对比不同日期的备份数据，检测数据变化
"""

import os
import json
import logging
from datetime import datetime, timedelta
import openpyxl
from typing import Dict, List, Tuple, Optional

class DataComparator:
    """数据对比器，用于对比不同日期的备份文件"""
    
    def __init__(self, backup_dir: str):
        """
        初始化数据对比器
        
        Args:
            backup_dir: 备份文件所在目录
        """
        self.backup_dir = backup_dir
        self.comparison_cache_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data_comparison_cache.json"
        )
        
    def get_backup_file_path(self, date_str: str) -> str:
        """
        获取指定日期的备份文件路径
        
        Args:
            date_str: 日期字符串，格式 YYYY-MM-DD
            
        Returns:
            文件路径
        """
        filename = f"Case Management Platform {date_str}.xlsx"
        return os.path.join(self.backup_dir, filename)
    
    def file_exists(self, date_str: str) -> bool:
        """
        检查指定日期的备份文件是否存在
        
        Args:
            date_str: 日期字符串
            
        Returns:
            文件是否存在
        """
        file_path = self.get_backup_file_path(date_str)
        return os.path.exists(file_path)
    
    def count_data_rows(self, file_path: str) -> Dict[str, int]:
        """
        统计Excel文件中每个工作表的数据行数
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            工作表名称到行数的映射
        """
        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet_counts = {}
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                # 统计非空行数（跳过标题行）
                row_count = 0
                for row in sheet.iter_rows(min_row=2):  # 从第2行开始，跳过标题
                    # 检查行是否为空（至少有一个单元格有值）
                    if any(cell.value is not None for cell in row):
                        row_count += 1
                    else:
                        # 遇到完全空行，停止计数
                        break
                        
                sheet_counts[sheet_name] = row_count
                logging.info(f"📊 Sheet '{sheet_name}': {row_count} rows")
            
            workbook.close()
            return sheet_counts
            
        except Exception as e:
            logging.error(f"❌ Error counting rows in {file_path}: {e}")
            return {}

    def get_data_rows_set(self, file_path: str, sheet_name: str) -> set:
        """
        获取指定工作表中的所有数据行（作为字符串集合）
        用于精确比较数据变化
        
        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称
            
        Returns:
            数据行的字符串集合
        """
        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            if sheet_name not in workbook.sheetnames:
                workbook.close()
                return set()
            
            sheet = workbook[sheet_name]
            data_rows = set()
            
            for row in sheet.iter_rows(min_row=2):  # 从第2行开始，跳过标题
                # 检查行是否为空
                if any(cell.value is not None for cell in row):
                    # 将行数据转换为字符串，用于比较
                    row_data = []
                    for cell in row:
                        if cell.value is not None:
                            row_data.append(str(cell.value).strip())
                        else:
                            row_data.append('')
                    # 去掉末尾的空字符串
                    while row_data and row_data[-1] == '':
                        row_data.pop()
                    if row_data:  # 如果行有数据
                        data_rows.add('|'.join(row_data))
                else:
                    # 遇到完全空行，停止读取
                    break
            
            workbook.close()
            return data_rows
            
        except Exception as e:
            logging.error(f"❌ Error reading data rows from {file_path}, sheet '{sheet_name}': {e}")
            return set()
    
    def compare_two_dates(self, date1_str: str, date2_str: str) -> Tuple[Dict[str, int], List[str]]:
        """
        对比两个日期的备份数据
        重点检测数据丢失情况（而非净变化）
        
        Args:
            date1_str: 第一个日期（较早）
            date2_str: 第二个日期（较晚）
            
        Returns:
            (差异字典, 警告消息列表)
        """
        warnings = []
        differences = {}
        
        # 检查文件是否存在
        if not self.file_exists(date1_str):
            logging.warning(f"⚠️ File for {date1_str} does not exist")
            warnings.append(f"备份文件 {date1_str} 不存在")
            return {}, warnings
            
        if not self.file_exists(date2_str):
            logging.warning(f"⚠️ File for {date2_str} does not exist")
            warnings.append(f"备份文件 {date2_str} 不存在")
            return {}, warnings
        
        # 获取两个文件的路径
        file1_path = self.get_backup_file_path(date1_str)
        file2_path = self.get_backup_file_path(date2_str)
        
        # 统计基本行数
        counts1 = self.count_data_rows(file1_path)
        counts2 = self.count_data_rows(file2_path)
        
        # 对比每个工作表的数据内容
        all_sheets = set(counts1.keys()) | set(counts2.keys())
        
        for sheet_name in all_sheets:
            count1 = counts1.get(sheet_name, 0)
            count2 = counts2.get(sheet_name, 0)
            
            if count1 == 0 and count2 == 0:
                continue  # 两个文件都没有这个表格的数据
            
            # 获取实际的数据行集合
            data1 = self.get_data_rows_set(file1_path, sheet_name)
            data2 = self.get_data_rows_set(file2_path, sheet_name)
            
            # 计算数据变化
            deleted_rows = data1 - data2  # 在date1中存在但在date2中不存在的数据
            added_rows = data2 - data1    # 在date2中存在但在date1中不存在的数据
            
            deleted_count = len(deleted_rows)
            added_count = len(added_rows)
            net_change = count2 - count1
            
            # 记录详细的变化信息
            if deleted_count > 0 or added_count > 0:
                differences[sheet_name] = {
                    'before': count1,
                    'after': count2,
                    'difference': net_change,
                    'deleted_count': deleted_count,
                    'added_count': added_count
                }
                
                logging.info(f"📊 Sheet '{sheet_name}': {count1} → {count2} (删除: {deleted_count}, 新增: {added_count})")
                
                # 重点关注数据丢失：如果删除的数据超过50条，生成警告
                if deleted_count > 50:
                    warning_msg = f"⚠️ 工作表 '{sheet_name}' 数据减少了 {deleted_count} 条记录"
                    warnings.append(warning_msg)
                    logging.warning(warning_msg)
        
        return differences, warnings
    
    def compare_with_previous_date(self, current_date_str: str) -> Tuple[Dict[str, int], List[str]]:
        """
        将当前日期的备份与前一天对比
        
        Args:
            current_date_str: 当前日期字符串
            
        Returns:
            (差异字典, 警告消息列表)
        """
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        previous_date = current_date - timedelta(days=1)
        previous_date_str = previous_date.strftime("%Y-%m-%d")
        
        logging.info(f"🔍 Comparing {previous_date_str} with {current_date_str}")
        return self.compare_two_dates(previous_date_str, current_date_str)
    
    def check_historical_data(self, reference_date_str: str, days_back: int = 7) -> Dict[str, List[int]]:
        """
        检查历史数据趋势
        
        Args:
            reference_date_str: 参考日期
            days_back: 往前检查的天数
            
        Returns:
            每个工作表的历史数据行数列表
        """
        reference_date = datetime.strptime(reference_date_str, "%Y-%m-%d")
        historical_data = {}
        
        for i in range(days_back):
            check_date = reference_date - timedelta(days=i)
            check_date_str = check_date.strftime("%Y-%m-%d")
            
            if self.file_exists(check_date_str):
                file_path = self.get_backup_file_path(check_date_str)
                counts = self.count_data_rows(file_path)
                
                for sheet_name, count in counts.items():
                    if sheet_name not in historical_data:
                        historical_data[sheet_name] = []
                    historical_data[sheet_name].append((check_date_str, count))
        
        return historical_data
    
    def save_comparison_result(self, date_str: str, comparison_result: Dict):
        """
        保存对比结果到缓存文件
        
        Args:
            date_str: 日期字符串
            comparison_result: 对比结果
        """
        try:
            # 读取现有缓存
            if os.path.exists(self.comparison_cache_file):
                with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            else:
                cache = {}
            
            # 更新缓存
            cache[date_str] = {
                'timestamp': datetime.now().isoformat(),
                'result': comparison_result
            }
            
            # 只保留最近30天的记录
            cutoff_date = datetime.now() - timedelta(days=30)
            cache = {
                k: v for k, v in cache.items()
                if datetime.fromisoformat(v['timestamp']) > cutoff_date
            }
            
            # 保存缓存
            with open(self.comparison_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logging.error(f"❌ Error saving comparison cache: {e}")
    
    def load_comparison_result(self, date_str: str) -> Optional[Dict]:
        """
        从缓存加载对比结果
        
        Args:
            date_str: 日期字符串
            
        Returns:
            对比结果，如果不存在返回None
        """
        try:
            if os.path.exists(self.comparison_cache_file):
                with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    if date_str in cache:
                        return cache[date_str]['result']
        except Exception as e:
            logging.error(f"❌ Error loading comparison cache: {e}")
        
        return None

# 创建全局实例
def init_data_comparator(backup_dir: str) -> DataComparator:
    """初始化并获取数据对比器"""
    return DataComparator(backup_dir)