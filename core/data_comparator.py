"""
Data comparison module
Used to compare backup data from different dates and detect data changes
"""

import os
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
import openpyxl
from typing import Dict, List, Tuple, Optional

from config import config

class DataComparator:
    """Data comparator for comparing backup files from different dates"""

    def __init__(self, backup_dir: str):
        """
        Initialize the data comparator

        Args:
            backup_dir: Directory where backup files are stored
        """
        self.backup_dir = backup_dir
        self.comparison_cache_file = os.path.join(
            config.get_program_dir(), "data_comparison_cache.json"
        )

    def get_backup_file_path(self, date_str: str) -> str:
        """
        Get the backup file path for a given date

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            File path
        """
        filename = config.BACKUP_FILENAME_TEMPLATE.format(date=date_str)
        return os.path.join(self.backup_dir, filename)

    def file_exists(self, date_str: str) -> bool:
        """
        Check whether the backup file for a given date exists

        Args:
            date_str: Date string

        Returns:
            Whether the file exists
        """
        file_path = self.get_backup_file_path(date_str)
        return os.path.exists(file_path)

    def count_data_rows(self, file_path: str) -> Dict[str, int]:
        """
        Count the number of data rows in each worksheet of an Excel file

        Args:
            file_path: Path to the Excel file

        Returns:
            Mapping from worksheet name to row count
        """
        workbook = None
        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet_counts = {}

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                row_count = 0
                for row in sheet.iter_rows(min_row=2):
                    if any(cell.value is not None for cell in row):
                        row_count += 1
                    else:
                        break

                sheet_counts[sheet_name] = row_count
                logging.info(f"Sheet '{sheet_name}': {row_count} rows")

            return sheet_counts

        except Exception as e:
            logging.error(f"Error counting rows in {file_path}: {e}")
            return {}
        finally:
            if workbook:
                workbook.close()

    def get_data_rows_counter(self, file_path: str, sheet_name: str) -> Counter:
        """
        Get all data rows in the specified worksheet (as a string Counter)
        Used for precise comparison of data changes, correctly handles duplicate rows

        Args:
            file_path: Path to the Excel file
            sheet_name: Worksheet name

        Returns:
            String Counter of data rows
        """
        workbook = None
        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            if sheet_name not in workbook.sheetnames:
                return Counter()

            sheet = workbook[sheet_name]
            data_rows: Counter = Counter()

            for row in sheet.iter_rows(min_row=2):
                if any(cell.value is not None for cell in row):
                    row_data = []
                    for cell in row:
                        row_data.append(str(cell.value).strip() if cell.value is not None else '')
                    while row_data and row_data[-1] == '':
                        row_data.pop()
                    if row_data:
                        data_rows['|'.join(row_data)] += 1
                else:
                    break

            return data_rows

        except Exception as e:
            logging.error(f"Error reading data rows from {file_path}, sheet '{sheet_name}': {e}")
            return Counter()
        finally:
            if workbook:
                workbook.close()

    def compare_two_dates(self, date1_str: str, date2_str: str) -> Tuple[Dict[str, int], List[str]]:
        """
        Compare backup data from two dates
        Focuses on detecting data loss (rather than net change)

        Args:
            date1_str: First date (earlier)
            date2_str: Second date (later)

        Returns:
            (differences dict, list of warning messages)
        """
        warnings = []
        differences = {}

        # Check whether files exist
        if not self.file_exists(date1_str):
            logging.warning(f"⚠️ File for {date1_str} does not exist")
            warnings.append(f"Backup file for {date1_str} does not exist")
            return {}, warnings

        if not self.file_exists(date2_str):
            logging.warning(f"⚠️ File for {date2_str} does not exist")
            warnings.append(f"Backup file for {date2_str} does not exist")
            return {}, warnings

        # Get paths for both files
        file1_path = self.get_backup_file_path(date1_str)
        file2_path = self.get_backup_file_path(date2_str)

        # Count basic row numbers
        counts1 = self.count_data_rows(file1_path)
        counts2 = self.count_data_rows(file2_path)

        # Compare data content for each worksheet
        all_sheets = set(counts1.keys()) | set(counts2.keys())

        for sheet_name in all_sheets:
            count1 = counts1.get(sheet_name, 0)
            count2 = counts2.get(sheet_name, 0)

            if count1 == 0 and count2 == 0:
                continue  # Neither file has data for this sheet

            # Get actual data row Counters
            data1 = self.get_data_rows_counter(file1_path, sheet_name)
            data2 = self.get_data_rows_counter(file2_path, sheet_name)

            # Calculate data changes (Counter subtraction discards zeros/negatives, keeping only surplus)
            deleted_counter = data1 - data2   # rows in data1 not fully covered by data2
            added_counter = data2 - data1     # rows in data2 not fully covered by data1

            deleted_count = sum(deleted_counter.values())
            added_count = sum(added_counter.values())
            net_change = count2 - count1

            # Record detailed change information
            if deleted_count > 0 or added_count > 0:
                differences[sheet_name] = {
                    'before': count1,
                    'after': count2,
                    'difference': net_change,
                    'deleted_count': deleted_count,
                    'added_count': added_count
                }

                logging.info(f"📊 Sheet '{sheet_name}': {count1} → {count2} (deleted: {deleted_count}, added: {added_count})")

                # Focus on data loss: generate a warning if deleted rows exceed the threshold
                if deleted_count > config.ALERT_DELETED_ROW_THRESHOLD:
                    warning_msg = f"⚠️ Sheet '{sheet_name}' lost {deleted_count} records"
                    warnings.append(warning_msg)
                    logging.warning(warning_msg)

        return differences, warnings

    def compare_with_previous_date(self, current_date_str: str) -> Tuple[Dict[str, int], List[str]]:
        """
        Compare the current date's backup with the previous day

        Args:
            current_date_str: Current date string

        Returns:
            (differences dict, list of warning messages)
        """
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        previous_date = current_date - timedelta(days=1)
        previous_date_str = previous_date.strftime("%Y-%m-%d")

        logging.info(f"🔍 Comparing {previous_date_str} with {current_date_str}")
        return self.compare_two_dates(previous_date_str, current_date_str)

    def check_historical_data(self, reference_date_str: str, days_back: int = 7) -> Dict[str, List[int]]:
        """
        Check historical data trends

        Args:
            reference_date_str: Reference date
            days_back: Number of days to look back

        Returns:
            List of historical data row counts per worksheet
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
        Save comparison result to the cache file

        Args:
            date_str: Date string
            comparison_result: Comparison result
        """
        try:
            # Load existing cache
            if os.path.exists(self.comparison_cache_file):
                with open(self.comparison_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            else:
                cache = {}

            # Update cache
            cache[date_str] = {
                'timestamp': datetime.now().isoformat(),
                'result': comparison_result
            }

            # Keep only the last 30 days of records
            cutoff_date = datetime.now() - timedelta(days=30)
            cache = {
                k: v for k, v in cache.items()
                if datetime.fromisoformat(v['timestamp']) > cutoff_date
            }

            # Save cache
            with open(self.comparison_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.error(f"❌ Error saving comparison cache: {e}")

    def load_comparison_result(self, date_str: str) -> Optional[Dict]:
        """
        Load comparison result from cache

        Args:
            date_str: Date string

        Returns:
            Comparison result, or None if not found
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

# Global singleton
data_comparator = DataComparator(config.DOWNLOAD_DIR)

def init_data_comparator(backup_dir: str) -> DataComparator:
    """Initialize and return the data comparator (returns the global singleton, backup_dir parameter is ignored)"""
    return data_comparator
