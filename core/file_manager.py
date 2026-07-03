"""
File Management Module
Handles file system operations
"""

import os
import re
import logging
from datetime import datetime, date

# Import config
from config import config

class FileManager:
    """File manager that handles file system operations"""

    def __init__(self):
        """Initialize the file manager"""
        self.download_dir = config.DOWNLOAD_DIR
        # Non-fatal here: this runs at import time (module-level singleton),
        # before logging is configured — raising would kill the windowed exe
        # before any log/report exists. _download_and_save() re-checks at
        # backup time and routes failures into the normal error report.
        try:
            self.ensure_download_dir_exists()
        except Exception as e:
            logging.warning(f"⚠️ Download dir unavailable at startup ({e}); will retry at backup time")

    def ensure_download_dir_exists(self):
        """Ensure the download directory exists"""
        try:
            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir, exist_ok=True)
                logging.info(f"✅ Created dir: {self.download_dir}")
            else:
                logging.debug(f"📁 Dir exists: {self.download_dir}")
        except Exception as e:
            logging.error(f"❌ Cannot create dir {self.download_dir}: {e}")
            raise

    def _write_atomic(self, file_path, file_content):
        """Write via a temp file + os.replace so a mid-write kill can never
        leave a truncated xlsx at the final name."""
        tmp_path = file_path + '.tmp'
        try:
            with open(tmp_path, 'wb') as f:
                f.write(file_content)
            os.replace(tmp_path, file_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise

    def save_file(self, file_content, date_str):
        """Save a file to the local filesystem (overwrite existing file when possible)"""
        filename = config.BACKUP_FILENAME_TEMPLATE.format(date=date_str)
        file_path = os.path.join(self.download_dir, filename)

        # Attempt a direct overwrite first
        try:
            self._write_atomic(file_path, file_content)

            logging.info(f"✅ Saved: {file_path}")
            logging.info(f"📝 File updated: {filename}")
            return file_path

        except PermissionError as e:
            logging.warning(f"⚠️ Cannot overwrite: {file_path}")
            logging.info(f"🔄 Trying alternatives...")

            # Fall back to alternative save strategies
            return self._try_alternative_save(file_content, date_str, file_path)

        except Exception as e:
            logging.error(f"❌ Save failed: {file_path}. Error: {e}")
            return self._try_alternative_save(file_content, date_str, file_path)

    def _try_alternative_save(self, file_content, date_str, original_path):
        """Try alternative save strategies"""

        # Strategy 1: delete the existing file then write a new one
        if os.path.exists(original_path):
            try:
                os.remove(original_path)
                logging.info(f"🗑️ Deleted, writing new")

                self._write_atomic(original_path, file_content)

                logging.info(f"✅ Overwrite success: {original_path}")
                return original_path

            except PermissionError:
                logging.warning(f"⚠️ File locked")
            except Exception as e:
                logging.error(f"❌ Write failed: {e}")

        # Strategy 2: use a timestamped filename derived from the standard template
        timestamp = datetime.now().strftime("%H%M%S")
        base, ext = os.path.splitext(config.BACKUP_FILENAME_TEMPLATE.format(date=date_str))
        filename = f"{base}_{timestamp}{ext}"
        timestamped_path = os.path.join(self.download_dir, filename)

        try:
            self._write_atomic(timestamped_path, file_content)

            logging.info(f"✅ Timestamp save: {timestamped_path}")
            logging.warning(f"⚠️ Saved as: {filename}")
            return timestamped_path

        except Exception as e:
            logging.error(f"❌ Timestamp failed: {e}")

        # Strategy 3: save to a fallback directory
        return self._try_fallback_save(file_content, date_str)

    def _try_fallback_save(self, file_content, date_str):
        """Save to the program directory when the target directory lacks write permission"""
        try:
            fallback_dir = os.path.join(config.get_program_dir(), "backup")

            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)
                logging.info(f"✅ Created backup dir: {fallback_dir}")

            timestamp = datetime.now().strftime("%H%M%S")
            base, ext = os.path.splitext(config.BACKUP_FILENAME_TEMPLATE.format(date=date_str))
            filename = f"{base}_{timestamp}{ext}"
            fallback_path = os.path.join(fallback_dir, filename)

            self._write_atomic(fallback_path, file_content)

            logging.info(f"✅ Saved to backup: {fallback_path}")
            logging.warning(f"⚠️ Saved to backup folder")
            return fallback_path

        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def cleanup_old_backups(self):
        """Apply the tiered retention policy to the download directory.

        A file's age is its {date} token, not filesystem mtime. Tiers:
          <= RETENTION_DAILY_DAYS    keep every backup
          <= RETENTION_WEEKLY_DAYS   keep the earliest backup date of each ISO
                                     week (Monday when present — earliest also
                                     covers weeks whose Monday backup is missing)
          <= RETENTION_MONTHLY_DAYS  keep the earliest backup date of each month
          older                      delete

        Only files matching BACKUP_FILENAME_TEMPLATE (canonical or the
        "_HHMMSS" fallback variant) are considered; anything else in the
        directory is left untouched. Never raises — a cleanup problem must
        not fail the backup that triggered it.
        """
        try:
            deleted_count, freed_bytes = self._apply_retention()
            if deleted_count:
                logging.info(f"🧹 Retention: deleted {deleted_count} old backup file(s), "
                             f"freed {freed_bytes / (1024 ** 3):.1f} GB")
        except Exception as e:
            logging.error(f"❌ Retention cleanup failed: {e}")

    @staticmethod
    def _backup_file_regex():
        """Regex matching canonical and fallback backup filenames, derived
        from the single BACKUP_FILENAME_TEMPLATE source of truth."""
        base, ext = os.path.splitext(config.BACKUP_FILENAME_TEMPLATE)
        pattern = (re.escape(base).replace(re.escape('{date}'), r'(\d{4}-\d{2}-\d{2})')
                   + r'(?:_\d{6})?' + re.escape(ext) + '$')
        return re.compile('^' + pattern)

    def _apply_retention(self):
        """Delete backup files not covered by the retention tiers.
        Returns (deleted_count, freed_bytes)."""
        regex = self._backup_file_regex()
        today = date.today()

        # Group backup files by their date token (a date may have a
        # canonical file plus timestamped fallback saves — kept or deleted
        # together)
        files_by_date = {}
        for name in os.listdir(self.download_dir):
            path = os.path.join(self.download_dir, name)
            if not os.path.isfile(path):
                continue
            match = regex.match(name)
            if not match:
                continue
            try:
                file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            files_by_date.setdefault(file_date, []).append(path)

        # Decide which DATES survive; a kept date keeps all its files
        keep_dates = set()
        earliest_in_period = {}
        for file_date in files_by_date:
            age = (today - file_date).days
            if age <= config.RETENTION_DAILY_DAYS:
                keep_dates.add(file_date)
                continue
            if age <= config.RETENTION_WEEKLY_DAYS:
                iso = file_date.isocalendar()
                period = ('week', iso[0], iso[1])
            elif age <= config.RETENTION_MONTHLY_DAYS:
                period = ('month', file_date.year, file_date.month)
            else:
                continue  # beyond all tiers — never kept
            if period not in earliest_in_period or file_date < earliest_in_period[period]:
                earliest_in_period[period] = file_date
        keep_dates.update(earliest_in_period.values())

        deleted_count = 0
        freed_bytes = 0
        for file_date, paths in sorted(files_by_date.items()):
            if file_date in keep_dates:
                continue
            for path in paths:
                try:
                    size = os.path.getsize(path)
                    os.remove(path)
                    deleted_count += 1
                    freed_bytes += size
                    logging.info(f"🗑️ Retention: deleted {os.path.basename(path)}")
                except OSError as e:
                    logging.warning(f"⚠️ Retention: could not delete {path}: {e}")
        return deleted_count, freed_bytes

# Global singleton
file_manager = FileManager()

def init_file_manager() -> 'FileManager':
    """Initialize and return the file manager (returns the global singleton)"""
    return file_manager
