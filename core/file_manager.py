"""
File Management Module
Handles file system operations
"""

import os
import logging
from datetime import datetime

# Import config
from config import config

class FileManager:
    """File manager that handles file system operations"""

    def __init__(self):
        """Initialize the file manager"""
        self.download_dir = config.DOWNLOAD_DIR
        self.ensure_download_dir_exists()

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

    def save_file(self, file_content, date_str):
        """Save a file to the local filesystem (overwrite existing file when possible)"""
        filename = config.BACKUP_FILENAME_TEMPLATE.format(date=date_str)
        file_path = os.path.join(self.download_dir, filename)

        # Attempt a direct overwrite first
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)

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

                with open(original_path, 'wb') as f:
                    f.write(file_content)

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
            with open(timestamped_path, 'wb') as f:
                f.write(file_content)

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

            with open(fallback_path, 'wb') as f:
                f.write(file_content)

            logging.info(f"✅ Saved to backup: {fallback_path}")
            logging.warning(f"⚠️ Saved to backup folder")
            return fallback_path

        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return None

# Global singleton
file_manager = FileManager()

def init_file_manager() -> 'FileManager':
    """Initialize and return the file manager (returns the global singleton)"""
    return file_manager
