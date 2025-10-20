"""
API服务模块
处理与飞书API的交互
"""

import requests
import time
import logging
import json

# 导入配置和模块
from config import config
from core.network import with_network_retry

class LarkAPIError(Exception):
    """飞书API错误"""
    def __init__(self, message, status_code=None, response=None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class APIService:
    """飞书API服务"""
    
    def __init__(self):
        """初始化API服务"""
        self._tenant_token = None
        self._token_expiry = 0
    
    def get_tenant_token(self, force_refresh=False):
        """
        获取tenant_access_token，自动缓存并管理过期
        参数:
          force_refresh: 是否强制刷新token
        """
        # 检查是否已有有效的token
        current_time = time.time()
        if not force_refresh and self._tenant_token and current_time < self._token_expiry:
            return self._tenant_token
            
        # 请求新token
        data = {"app_id": config.APP_ID, "app_secret": config.APP_SECRET}
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8"
        }
        
        try:
            response = requests.post(config.AUTH_URL, headers=headers, json=data)
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("code") == 0:
                    self._tenant_token = response_data.get("tenant_access_token")
                    # 设置过期时间（保守起见，比实际提前5分钟过期）
                    expires_in = response_data.get("expire", 7200)
                    self._token_expiry = current_time + expires_in - 300
                    
                    logging.info("✅ Tenant token acquired")
                    return self._tenant_token
                else:
                    error_msg = f"Failed to get tenant_access_token: {response_data.get('msg', 'Unknown error')}"
                    logging.error(f"❌ {error_msg}")
                    raise LarkAPIError(error_msg, response=response_data)
            else:
                error_msg = f"Request failed: tenant_access_token request returned status code {response.status_code}"
                logging.error(f"❌ {error_msg}")
                raise LarkAPIError(error_msg, status_code=response.status_code)
                
        except requests.RequestException as e:
            error_msg = f"Network exception when getting tenant_access_token: {e}"
            logging.error(f"❌ {error_msg}")
            raise LarkAPIError(error_msg) from e
    
    def get_authorization_header(self, token=None):
        """获取带有认证信息的请求头"""
        if token is None:
            token = self.get_tenant_token()
        return {"Authorization": f"Bearer {token}"}
    
    @with_network_retry
    def get_wiki_data(self):
        """获取Wiki API数据"""
        url = f"{config.WIKI_API_URL}?token={config.TOKEN}"
        headers = self.get_authorization_header()
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                logging.info("✅ Wiki data acquired")
                return response.json()
            else:
                error_msg = f"Wiki API request failed, status code: {response.status_code}"
                logging.error(f"❌ {error_msg}")
                raise LarkAPIError(error_msg, status_code=response.status_code)
                
        except requests.RequestException as e:
            error_msg = f"Network exception when getting Wiki API data: {e}"
            logging.error(f"❌ {error_msg}")
            raise LarkAPIError(error_msg) from e
    
    def extract_obj_token(self, wiki_data):
        """从Wiki数据中提取obj_token"""
        obj_token = wiki_data.get('data', {}).get('node', {}).get('obj_token', None)
        if obj_token:
            logging.info("✅ Object token extracted")
            return obj_token
        else:
            error_msg = "obj_token not found"
            logging.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
    
    @with_network_retry
    def create_export_task(self, obj_token):
        """创建导出任务"""
        headers = self.get_authorization_header()
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = {"file_extension": "xlsx", "token": obj_token, "type": "bitable"}

        try:
            logging.info("🔄 Creating export task...")
            response = requests.post(config.EXPORT_TASK_URL, headers=headers, json=data)

            if response.status_code == 200:
                response_data = response.json()
                ticket = response_data.get("data", {}).get("ticket")

                if ticket and ticket.strip():
                    logging.info("✅ Export task created")
                    return ticket
                else:
                    # 如果第一次POST没有返回有效ticket，说明任务创建失败
                    logging.error("❌ Export task failed - no ticket returned")
                    return None
            else:
                logging.error(f"❌ Export task request failed, status code: {response.status_code}")
                return None

        except requests.RequestException as e:
            logging.error(f"❌ Network exception when creating export task: {e}")
            return None
    
    @with_network_retry
    def get_export_task_status(self, ticket, obj_token):
        """查询导出任务状态并获取file_token"""
        if not ticket:
            logging.error("❌ Invalid ticket, cannot get export task status")
            return None
            
        url = config.get_export_task_status_url(ticket, obj_token)
        headers = self.get_authorization_header()
        
        try:
            for attempt in range(config.MAX_EXPORT_STATUS_CHECKS):
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    response_data = response.json()
                    # API response details removed
                    
                    result = response_data.get('data', {}).get('result', {})
                    job_status = result.get("job_status")
                    file_token = result.get("file_token")
                    
                    # Status details removed
                    
                    # 只以file_token是否存在作为判断条件
                    if file_token and file_token.strip():
                        logging.info("✅ Export ready")
                        return file_token
                    else:
                        # 无论job_status是什么，只要没有file_token就继续轮询
                        if job_status == 2:
                            # 记录详细的状态信息，但不直接失败
                            error_msg = result.get("job_error_msg", "")
                            file_name = result.get("file_name", "")
                            file_size = result.get("file_size", 0)
                            file_extension = result.get("file_extension", "")
                            
                            # Status=2 details removed
                            
                        else:
                            logging.info(f"🔄 Waiting... status={job_status} (attempt {attempt + 1}/{config.MAX_EXPORT_STATUS_CHECKS})")
                else:
                    logging.error(f"❌ Failed to get task status, status code: {response.status_code}")
                
                # 使用可配置的检查间隔
                time.sleep(config.EXPORT_STATUS_CHECK_INTERVAL)
            
            logging.error("❌ Timeout waiting for file_token")
            return None
            
        except requests.RequestException as e:
            logging.error(f"❌ Network exception when getting export task status: {e}")
            return None
    
    @with_network_retry
    def download_file(self, file_token):
        """下载文件并返回内容"""
        if not file_token:
            logging.error("❌ Invalid file_token, cannot download file")
            return None
            
        url = config.get_download_url(file_token)
        headers = self.get_authorization_header()
        
        try:
            logging.info("🔄 Downloading file...")
            
            # 使用非流式下载方法
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # 获取内容
                content = response.content
                
                # 验证获取到的内容
                if not content or len(content) == 0:
                    logging.error("❌ File content is empty")
                    return None
                    
                logging.info(f"✅ Downloaded: {len(content)} bytes")
                return content
            else:
                logging.error(f"❌ File download failed, status code: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logging.error(f"❌ Network exception when downloading file: {e}")
            return None

# 创建API服务全局实例
api_service = APIService() 
