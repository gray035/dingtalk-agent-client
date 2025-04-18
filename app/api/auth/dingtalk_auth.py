"""
钉钉认证模块
"""
import time
from typing import Optional, Tuple, List
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

    def get_user_access_token(self) -> str:
        """
        获取用户访问令牌

        Returns:
            str: 用户访问令牌
        """
        if self.user_access_token and self._is_user_token_valid():
            return self.user_access_token

        return self._refresh_user_token()

    def _is_user_token_valid(self) -> bool:
        """
        检查用户令牌是否有效

        Returns:
            bool: 令牌是否有效
        """
        if not self.user_access_token or not self.user_expires_in or not self.user_last_refresh_time:
            return False

        # 检查是否过期（提前5分钟刷新）
        current_time = time.time()
        return current_time < (self.user_last_refresh_time + self.user_expires_in - 300)

    def _refresh_user_token(self) -> str:
        """
        刷新用户访问令牌

        Returns:
            str: 新的用户访问令牌
        """
        try:
            # 如果已有刷新令牌，使用刷新令牌获取新的访问令牌
            if self.user_refresh_token:
                return self._get_user_token(grant_type="refresh_token", refresh_token=self.user_refresh_token)

            # 如果没有刷新令牌，需要重新获取授权码
            logger.error("没有可用的用户刷新令牌，需要重新授权")
            return ""
        except Exception as e:
            logger.error(f"刷新用户访问令牌时发生错误: {str(e)}")
            return ""

    def _get_user_token(self, grant_type: str, refresh_token: Optional[str] = None, code: Optional[str] = None) -> str:
        """
        获取用户访问令牌

        Args:
            grant_type: 授权类型
            refresh_token: 刷新令牌
            code: 授权码

        Returns:
            str: 用户访问令牌
        """
        try:
            # 构建请求参数
            request_params = {
                "client_id": settings.DINGTALK_CLIENT_ID,
                "client_secret": settings.DINGTALK_CLIENT_SECRET,
                "grant_type": grant_type
            }

            # 根据授权类型添加相应参数
            if grant_type == "refresh_token" and refresh_token:
                request_params["refresh_token"] = refresh_token
            elif grant_type == "authorization_code" and code:
                request_params["code"] = code
            else:
                logger.error(f"无效的授权类型或缺少必要参数: grant_type={grant_type}")
                return ""

            request = dingtalkoauth_2__1__0_models.GetUserTokenRequest(**request_params)
            response = self.client.get_user_token(request)

            if response.body:
                self.user_access_token = response.body.access_token
                self.user_expires_in = response.body.expire_in
                self.user_last_refresh_time = time.time()
                if response.body.refresh_token:
                    self.user_refresh_token = response.body.refresh_token
                return self.user_access_token
        except Exception as e:
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"获取用户访问令牌失败: {e.code} - {e.message}")
            else:
                logger.error(f"获取用户访问令牌时发生错误: {str(e)}")

        return ""

    def get_user_token_with_code(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        """
        使用授权码获取用户访问令牌

        Args:
            code: 授权码

        Returns:
            Tuple[Optional[str], Optional[str]]: (access_token, refresh_token)
        """
        try:
            request = dingtalkoauth_2__1__0_models.GetUserTokenRequest(
                client_id=settings.DINGTALK_CLIENT_ID,
                client_secret=settings.DINGTALK_CLIENT_SECRET,
                code=code,
                grant_type="authorization_code"
            )

            response = self.client.get_user_token(request)
            if response.body:
                # 保存用户令牌信息
                self.user_access_token = response.body.access_token
                self.user_expires_in = response.body.expire_in
                self.user_last_refresh_time = time.time()
                self.user_refresh_token = response.body.refresh_token
                return response.body.access_token, response.body.refresh_token
        except Exception as e:
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"获取用户访问令牌失败: {e.code} - {e.message}")
            else:
                logger.error(f"获取用户访问令牌时发生错误: {str(e)}")

        return None, None

    def search_users(self, keyword: str) -> List[str]:
        """
        搜索用户

        Args:
            keyword: 关键词

        Returns:
            List[str]: 用户ID列表
        """
        try:
            response = self.client.search_users(keyword)
            if response.body:
                return response.body.user_ids
        except Exception as e:
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"搜索用户失败: {e.code} - {e.message}")
            else:
                logger.error(f"搜索用户时发生错误: {str(e)}")

        return []

    def send_message(self, user_id: str, message: str) -> bool:
        """
        发送消息

        Args:
            user_id: 用户ID
            message: 消息内容

        Returns:
            bool: 是否发送成功
        """
        try:
            response = self.client.send_message(user_id, message)
            return response.body.result
        except Exception as e:
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"发送消息失败: {e.code} - {e.message}")
            else:
                logger.error(f"发送消息时发生错误: {str(e)}")

        return False


def get_auth() -> DingtalkAuth:
    """
    获取认证对象

    Returns:
        DingtalkAuth: 认证对象
    """
    return DingtalkAuth()