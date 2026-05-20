"""
每日重试管理器
跟踪和控制每天的备份尝试次数
支持手动启动时智能重置
"""

import os
import json
import logging
from datetime import datetime, date, time

from config import config

class DailyRetryManager:
    """每日重试管理器，跟踪每天的备份尝试次数"""
    
    def __init__(self):
        """初始化重试管理器"""
        self.retry_file = config.RETRY_COUNT_FILE
        self.max_attempts = config.MAX_DAILY_ATTEMPTS
        
    def _load_retry_data(self):
        """加载重试数据"""
        if not os.path.exists(self.retry_file):
            return {}
        
        try:
            with open(self.retry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"⚠️ Cannot read retry file: {e}")
            return {}
    
    def _save_retry_data(self, data):
        """保存重试数据"""
        try:
            with open(self.retry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"❌ Cannot save retry: {e}")
    
    def _is_scheduled_time(self):
        """检查当前时间是否接近预定的执行时间"""
        try:
            # 获取配置的调度时间
            schedule_time_str = getattr(config, 'SCHEDULE_TIME', '09:00')
            schedule_hour, schedule_minute = map(int, schedule_time_str.split(':'))
            
            # 获取当前时间
            now = datetime.now()
            current_time = now.time()
            scheduled_time = time(schedule_hour, schedule_minute)
            
            # 计算时间差（转换为分钟）
            def time_to_minutes(t):
                return t.hour * 60 + t.minute
            
            current_minutes = time_to_minutes(current_time)
            scheduled_minutes = time_to_minutes(scheduled_time)
            
            # 如果在预定时间前后5分钟内，认为是定时执行（循环时钟差，跨午夜安全）
            linear_diff = abs(current_minutes - scheduled_minutes)
            time_diff = min(linear_diff, 1440 - linear_diff)   # circular diff on a 1440-minute clock
            return time_diff <= 5
            
        except Exception as e:
            logging.warning(f"⚠️ Error checking scheduled time: {e}")
            return False
    
    def reset_if_manual_start(self):
        """如果是手动启动，则重置今日计数"""
        if not self._is_scheduled_time():
            # 不在预定时间，认为是手动启动
            today_str = date.today().strftime("%Y-%m-%d")
            data = self._load_retry_data()
            
            if today_str in data and data[today_str] > 0:
                old_count = data[today_str]
                data[today_str] = 0
                self._save_retry_data(data)
                logging.info(f"🔄 Manual start detected, reset today's count from {old_count} to 0")
            else:
                logging.info(f"🔄 Manual start detected, today's count already at 0")
        else:
            logging.info(f"⏰ Scheduled time detected, keeping existing count")
    
    def get_today_attempts(self):
        """获取今天已经尝试的次数"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()
        return data.get(today_str, 0)
    
    def can_attempt_today(self):
        """检查今天是否还可以尝试"""
        attempts = self.get_today_attempts()
        can_attempt = attempts < self.max_attempts
        
        logging.info(f"📊 Today attempts: {attempts}/{self.max_attempts}")
        
        return can_attempt
    
    def record_attempt(self, success=False):
        """记录一次尝试"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()
        
        # 清理旧数据（只保留最近7天）
        self._cleanup_old_data(data)
        
        # 记录今天的尝试
        current_attempts = data.get(today_str, 0)
        new_attempts = current_attempts + 1
        data[today_str] = new_attempts
        
        self._save_retry_data(data)
        
        if success:
            logging.info(f"✅ Success! Attempt {new_attempts} completed")
        else:
            remaining = self.max_attempts - new_attempts
            logging.warning(f"❌ Failed! Attempt {new_attempts}, {remaining} left")
        
        return new_attempts
    
    def _cleanup_old_data(self, data):
        """清理7天前的旧数据"""
        current_date = date.today()
        keys_to_remove = []
        
        for date_str in data.keys():
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (current_date - record_date).days > 7:
                    keys_to_remove.append(date_str)
            except ValueError:
                # 无效日期格式，也删除
                keys_to_remove.append(date_str)
        
        for key in keys_to_remove:
            del data[key]
    
    def get_remaining_attempts(self):
        """获取今天剩余的尝试次数"""
        attempts = self.get_today_attempts()
        return max(0, self.max_attempts - attempts)
    
    def reset_today(self):
        """手动重置今天的计数"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()
        if today_str in data:
            del data[today_str]
            self._save_retry_data(data)
            logging.info(f"🔄 Today's count manually reset")

# 创建全局重试管理器实例
retry_manager = DailyRetryManager() 