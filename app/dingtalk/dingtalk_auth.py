"""
钉钉认证模块
"""
import time
from loguru import logger

from alibabacloud_dingtalk.oauth2_1_0.client import Client as dingtalkoauth2_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.oauth2_1_0 import models as dingtalkoauth_2__1__0_models
from alibabacloud_tea_util.client import Client as UtilClient

from app.config.settings import settings


class DingtalkAuth:
    """钉钉认证类"""

    def __init__(self):
        """初始化认证对象"""
        # 用户级 token
        self.user_access_token = None
        self.user_refresh_token = None
        self.user_expires_in = 0
        self.user_last_refresh_time = 0
        
        # 应用级 token
        self.app_access_token = None
        self.app_expires_in = 0
        self.app_last_refresh_time = 0
        
        self.client = self._create_client()

    def _create_client(self) -> dingtalkoauth2_1_0Client:
        """
        创建钉钉OAuth2客户端

        Returns:
            dingtalkoauth2_1_0Client: 钉钉OAuth2客户端实例
        """
        config = open_api_models.Config()
        config.protocol = 'https'
        config.region_id = 'central'
        return dingtalkoauth2_1_0Client(config)

    def get_app_access_token(self) -> str:
        """
        获取企业应用访问令牌

        Returns:
            str: 应用访问令牌
        """
        if self.app_access_token and self._is_app_token_valid():
            return self.app_access_token

        return self._refresh_app_token()

    def _is_app_token_valid(self) -> bool:
        """
        检查应用令牌是否有效

        Returns:
            bool: 令牌是否有效
        """
        if not self.app_access_token or not self.app_expires_in or not self.app_last_refresh_time:
            return False

        # 检查是否过期（提前5分钟刷新）
        current_time = time.time()
        return current_time < (self.app_last_refresh_time + self.app_expires_in - 300)

    def _refresh_app_token(self) -> str:
        """
        刷新应用访问令牌

        Returns:
            str: 新的应用访问令牌
        """
        try:
            request = dingtalkoauth_2__1__0_models.GetAccessTokenRequest(
                app_key=settings.DINGTALK_CLIENT_ID,
                app_secret=settings.DINGTALK_CLIENT_SECRET
            )

            response = self.client.get_access_token(request)
            if response.body:
                self.app_access_token = response.body.access_token
                self.app_expires_in = response.body.expire_in
                self.app_last_refresh_time = time.time()
                return self.app_access_token
        except Exception as e:
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"获取应用访问令牌失败: {e.code} - {e.message}")
            else:
                logger.error(f"获取应用访问令牌时发生错误: {str(e)}")

        return ""


def get_auth() -> DingtalkAuth:
    """
    获取认证对象

    Returns:
        DingtalkAuth: 认证对象
    """
    return DingtalkAuth()