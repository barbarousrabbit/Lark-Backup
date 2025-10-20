"""
文件管理模块
处理文件操作
"""

import os
import logging
from datetime import datetime

# 导入配置
from config import config

class FileManager:
    """文件管理器，处理文件系统操作"""
    
    def __init__(self):
        """初始化文件管理器"""
        self.download_dir = config.DOWNLOAD_DIR
        self.ensure_download_dir_exists()
    
    def ensure_download_dir_exists(self):
        """确保下载目录存在"""
        try:
            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir, exist_ok=True)
                logging.info(f"✅ Created dir: {self.download_dir}")
            else:
                logging.info(f"📁 Dir exists: {self.download_dir}")
        except Exception as e:
            logging.error(f"❌ Cannot create dir {self.download_dir}: {e}")
            raise
    
    def save_file(self, file_content, date_str):
        """保存文件到本地（优先覆盖原文件）"""
        filename = f"Case Management Platform {date_str}.xlsx"
        file_path = os.path.join(self.download_dir, filename)
        
        # 优先尝试直接覆盖写入
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logging.info(f"✅ Saved: {file_path}")
            if os.path.exists(file_path):
                # 如果是覆盖了原有文件，特别说明
                logging.info(f"📝 File updated: {filename}")
            return file_path
            
        except PermissionError as e:
            logging.warning(f"⚠️ Cannot overwrite: {file_path}")
            logging.info(f"🔄 Trying alternatives...")
            
            # 尝试备选方案
            return self._try_alternative_save(file_content, date_str, file_path)
            
        except Exception as e:
            logging.error(f"❌ Save failed: {file_path}. Error: {e}")
            return self._try_alternative_save(file_content, date_str, file_path)
    
    def _try_alternative_save(self, file_content, date_str, original_path):
        """尝试备选保存方案"""
        
        # 方案1: 尝试先删除后写入
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
        
        # 方案2: 使用带时间戳的文件名
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"Case Management Platform {date_str}_{timestamp}.xlsx"
        timestamped_path = os.path.join(self.download_dir, filename)
        
        try:
            with open(timestamped_path, 'wb') as f:
                f.write(file_content)
            
            logging.info(f"✅ Timestamp save: {timestamped_path}")
            logging.warning(f"⚠️ Saved as: {filename}")
            return timestamped_path
            
        except Exception as e:
            logging.error(f"❌ Timestamp failed: {e}")
        
        # 方案3: 保存到备用目录
        return self._try_fallback_save(file_content, date_str)
    

    
    def _try_fallback_save(self, file_content, date_str):
        """当原目录权限不足时，尝试保存到程序目录"""
        try:
            # 在程序目录创建backup文件夹
            current_dir = os.getcwd()
            fallback_dir = os.path.join(current_dir, "backup")
            
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)
                logging.info(f"✅ Created backup dir: {fallback_dir}")
            
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"Case Management Platform {date_str}_{timestamp}.xlsx"
            fallback_path = os.path.join(fallback_dir, filename)
            
            with open(fallback_path, 'wb') as f:
                f.write(file_content)
            
            logging.info(f"✅ Saved to backup: {fallback_path}")
            logging.warning(f"⚠️ Saved to backup folder")
            return fallback_path
            
        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            return None
    
    def get_file_path(self, date_str):
        """根据日期字符串生成文件路径"""
        filename = f"Case Management Platform {date_str}.xlsx"
        return os.path.join(self.download_dir, filename)

# 创建全局实例
def init_file_manager():
    """初始化并获取文件管理器"""
    return FileManager() 