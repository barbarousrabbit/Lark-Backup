"""
API Service Module
Handles interactions with the Lark API
"""

import requests
import time
import logging

# Import config and modules
from config import config
from core.network import with_network_retry

class LarkAPIError(Exception):
    """Lark API error"""
    def __init__(self, message, status_code=None, response=None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class APIService:
    """Lark API service"""

    def __init__(self):
        """Initialize the API service"""
        self._tenant_token = None
        self._token_expiry = 0

    def get_tenant_token(self, force_refresh=False):
        """
        Retrieve tenant_access_token with automatic caching and expiry management.
        Args:
          force_refresh: Whether to force a token refresh
        """
        # Check whether a valid token already exists
        current_time = time.time()
        if not force_refresh and self._tenant_token and current_time < self._token_expiry:
            return self._tenant_token

        # Request a new token
        data = {"app_id": config.APP_ID, "app_secret": config.APP_SECRET}
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8"
        }

        try:
            response = requests.post(config.AUTH_URL, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("code") == 0:
                    token = response_data.get("tenant_access_token")
                    if not token:
                        raise LarkAPIError("tenant_access_token missing in auth response", response=response_data)
                    self._tenant_token = token
                    # Set expiry time (conservatively, 5 minutes before actual expiry)
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
        """Return request headers containing authentication information"""
        if token is None:
            token = self.get_tenant_token()
        return {"Authorization": f"Bearer {token}"}

    @with_network_retry
    def get_wiki_data(self):
        """Fetch Wiki API data"""
        url = f"{config.WIKI_API_URL}?token={config.TOKEN}"
        headers = self.get_authorization_header()

        try:
            response = requests.get(url, headers=headers, timeout=30)

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
        """Extract obj_token from Wiki data"""
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
        """Create an export task"""
        headers = self.get_authorization_header()
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = {"file_extension": "xlsx", "token": obj_token, "type": "bitable"}

        try:
            logging.info("🔄 Creating export task...")
            response = requests.post(config.EXPORT_TASK_URL, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                ticket = response_data.get("data", {}).get("ticket")

                if ticket and ticket.strip():
                    logging.info("✅ Export task created")
                    return ticket
                else:
                    # If the first POST did not return a valid ticket, the task creation failed
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
        """Query export task status and retrieve the file_token"""
        if not ticket:
            logging.error("❌ Invalid ticket, cannot get export task status")
            return None

        url = config.get_export_task_status_url(ticket, obj_token)
        headers = self.get_authorization_header()

        try:
            for attempt in range(config.MAX_EXPORT_STATUS_CHECKS):
                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    response_data = response.json()
                    # API response details removed

                    result = response_data.get('data', {}).get('result', {})
                    job_status = result.get("job_status")
                    file_token = result.get("file_token")

                    # Status details removed

                    if file_token and file_token.strip():
                        logging.info("✅ Export ready")
                        return file_token

                    # file_token is the sole success condition; status=2 is transient on the Lark API
                    # (returned on first polls before the file is ready) — keep polling until file_token appears
                    error_msg = result.get("job_error_msg", "")
                    log_fn = logging.warning if job_status == 2 else logging.info
                    log_fn(f"⚠️ Export job status={job_status} (no file_token yet): {error_msg!r} (attempt {attempt + 1}/{config.MAX_EXPORT_STATUS_CHECKS})")
                else:
                    logging.error(f"❌ Failed to get task status, status code: {response.status_code}")

                # Use the configurable check interval
                time.sleep(config.EXPORT_STATUS_CHECK_INTERVAL)

            logging.error("❌ Timeout waiting for file_token")
            return None

        except requests.RequestException as e:
            logging.error(f"❌ Network exception when getting export task status: {e}")
            return None

    @with_network_retry
    def download_file(self, file_token):
        """Download the file and return its content"""
        if not file_token:
            logging.error("❌ Invalid file_token, cannot download file")
            return None

        url = config.get_download_url(file_token)
        headers = self.get_authorization_header()

        try:
            logging.info("🔄 Downloading file...")

            # 10s connect timeout, 300s read timeout — file can be up to ~200 MB
            response = requests.get(url, headers=headers, timeout=(10, 300))

            if response.status_code == 200:
                # Retrieve content
                content = response.content

                # Validate retrieved content
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

# Global API service instance
api_service = APIService()
