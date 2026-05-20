"""
Daily retry manager
Tracks and controls the number of backup attempts per day
Supports intelligent reset when started manually
"""

import os
import json
import logging
from datetime import datetime, date, time

from config import config

class DailyRetryManager:
    """Daily retry manager that tracks the number of backup attempts per day"""

    def __init__(self):
        """Initialize the retry manager"""
        self.retry_file = config.RETRY_COUNT_FILE
        self.max_attempts = config.MAX_DAILY_ATTEMPTS

    def _load_retry_data(self):
        """Load retry data"""
        if not os.path.exists(self.retry_file):
            return {}

        try:
            with open(self.retry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"⚠️ Cannot read retry file: {e}")
            return {}

    def _save_retry_data(self, data):
        """Save retry data"""
        try:
            with open(self.retry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"❌ Cannot save retry: {e}")

    def _is_scheduled_time(self):
        """Check whether the current time is close to the configured scheduled execution time"""
        try:
            # Get the configured schedule time
            schedule_time_str = getattr(config, 'SCHEDULE_TIME', '09:00')
            schedule_hour, schedule_minute = map(int, schedule_time_str.split(':'))

            # Get the current time
            now = datetime.now()
            current_time = now.time()
            scheduled_time = time(schedule_hour, schedule_minute)

            # Convert time to minutes
            def time_to_minutes(t):
                return t.hour * 60 + t.minute

            current_minutes = time_to_minutes(current_time)
            scheduled_minutes = time_to_minutes(scheduled_time)

            # If within 5 minutes before or after the scheduled time, treat as a scheduled execution (circular clock diff, safe across midnight)
            linear_diff = abs(current_minutes - scheduled_minutes)
            time_diff = min(linear_diff, 1440 - linear_diff)   # circular diff on a 1440-minute clock
            return time_diff <= 5

        except Exception as e:
            logging.warning(f"⚠️ Error checking scheduled time: {e}")
            return False

    def reset_if_manual_start(self):
        """Reset today's count if this is a manual start"""
        if not self._is_scheduled_time():
            # Not at the scheduled time — treat as manual start
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
        """Get the number of attempts made today"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()
        return data.get(today_str, 0)

    def can_attempt_today(self):
        """Check whether another attempt is allowed today"""
        attempts = self.get_today_attempts()
        can_attempt = attempts < self.max_attempts

        logging.info(f"📊 Today attempts: {attempts}/{self.max_attempts}")

        return can_attempt

    def record_attempt(self, success=False):
        """Record one attempt"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()

        # Clean up old data (keep only the last 7 days)
        self._cleanup_old_data(data)

        # Record today's attempt
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
        """Remove data older than 7 days"""
        current_date = date.today()
        keys_to_remove = []

        for date_str in data.keys():
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (current_date - record_date).days > 7:
                    keys_to_remove.append(date_str)
            except ValueError:
                # Invalid date format — remove as well
                keys_to_remove.append(date_str)

        for key in keys_to_remove:
            del data[key]

    def get_remaining_attempts(self):
        """Get the number of remaining attempts for today"""
        attempts = self.get_today_attempts()
        return max(0, self.max_attempts - attempts)

    def reset_today(self):
        """Manually reset today's count"""
        today_str = date.today().strftime("%Y-%m-%d")
        data = self._load_retry_data()
        if today_str in data:
            del data[today_str]
            self._save_retry_data(data)
            logging.info(f"🔄 Today's count manually reset")

# Create the global retry manager instance
retry_manager = DailyRetryManager()
