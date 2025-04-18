"""
钉钉开放平台 API 客户端
"""
import requests
import json
from typing import Dict, List, Optional, Union, Tuple
from loguru import logger

from app.config.settings import settings
from app.api.auth.dingtalk_auth import DingtalkAuth


class DingtalkClient:
    """钉钉开放平台 API 客户端"""

    def __init__(self, auth: DingtalkAuth):
        """
        初始化钉钉客户端

        Args:
            auth: 认证对象
        """
        self.auth = auth
        self.base_url = settings.DINGTALK_BASE_URL
        self.me_id = self.get_self_user_info()

    def get_self_user_info(self) -> Optional[str]:
        """
        获取当前用户信息

        Returns:
            Optional[str]: 用户ID，如果获取失败则返回None
        """
        access_token = self.auth.get_user_access_token()
        if not access_token:
            logger.error("获取用户访问令牌失败")
            return None

        url = f"{self.base_url}v1.0/contact/users/me"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    return result.get("userid")
                else:
                    logger.error(f"获取用户信息失败: {result.get('errmsg')}")
            else:
                logger.error(f"获取用户信息请求失败: {response.text}")
        except Exception as e:
            logger.error(f"获取用户信息时发生错误: {str(e)}")

        return None

    def search_users(self, query_word: str, offset: int = 0, size: int = 10, exact_match: bool = False) -> List[str]:
        """
        搜索用户

        Args:
            query_word: 搜索关键词
            offset: 分页偏移量，默认0
            size: 分页大小，默认10
            exact_match: 是否精确匹配用户名称，默认False（模糊匹配）

        Returns:
            List[str]: 用户ID列表
        """
        try:
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("获取应用访问令牌失败")
                return []

            url = f"{self.base_url}v1.0/contact/users/search"
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": access_token
            }
            data = {
                "queryWord": query_word,
                "offset": offset,
                "size": size
            }
            
            # 只有在需要精确匹配时才添加 fullMatchField 参数
            if exact_match:
                data["fullMatchField"] = 1
            
            logger.info(f"搜索用户请求参数: {data}")
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"搜索用户响应: {result}")
                
                # 检查是否有错误码
                if "errcode" in result and result["errcode"] != 0:
                    error_msg = result.get("errmsg", "未知错误")
                    logger.error(f"搜索用户失败: {error_msg}, 错误码: {result.get('errcode')}")
                    return []
                
                # 返回用户ID列表
                return result.get("list", [])
            else:
                logger.error(f"搜索用户请求失败: HTTP {response.status_code}, 响应: {response.text}")
        except Exception as e:
            logger.error(f"搜索用户时发生错误: {str(e)}")
        
        return []

    def get_users_info(self, user_ids: List[str]) -> List[Dict]:
        """
        获取用户详细信息

        Args:
            user_ids: 用户ID列表

        Returns:
            用户详细信息列表
        """
        try:
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("获取应用访问令牌失败")
                return []

            url = "https://oapi.dingtalk.com/topapi/v2/user/get"
            users_info = []
            
            for user_id in user_ids:
                params = {
                    "access_token": access_token
                }
                data = {
                    "language": "zh_CN",
                    "userid": user_id
                }

                response = requests.post(url, params=params, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("errcode") == 0:  # 注意：errcode 是数字 0
                        user_info = result.get("result", {})
                        if user_info:
                            users_info.append(user_info)
                        else:
                            logger.warning(f"用户 {user_id} 信息为空")
                    else:
                        logger.error(f"获取用户 {user_id} 信息失败: {result.get('errmsg')}")
                else:
                    logger.error(f"获取用户 {user_id} 信息请求失败: HTTP {response.status_code}, 响应: {response.text}")

            return users_info

        except Exception as e:
            logger.error(f"获取用户信息时发生错误: {str(e)}")
            return []

    def create_chat(self, user_ids: List[str], name: Optional[str] = None) -> Optional[str]:
        """创建群聊"""
        access_token = self.auth.get_app_access_token()
        if not access_token:
            logger.error("获取应用访问令牌失败")
            return None

        url = f"{self.base_url}v1.0/im/chat/create"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }
        data = {
            "userIds": user_ids if isinstance(user_ids, list) else [user_ids],
            "name": name or f"Chat with {self.me_id}"
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    return result.get("chatId")
                else:
                    logger.error(f"创建群聊失败: {result.get('errmsg')}")
            else:
                logger.error(f"创建群聊请求失败: {response.text}")
        except Exception as e:
            logger.error(f"创建群聊时发生错误: {str(e)}")

        return None

    def send_message(self, receiver_uid: str, content: str, msg_type: str = "text", 
                    at_user_ids: Optional[List[str]] = None, is_at_all: bool = False) -> bool:
        """
        发送消息

        Args:
            receiver_uid: 接收者ID
            content: 消息内容
            msg_type: 消息类型，默认为text
            at_user_ids: @的用户ID列表
            is_at_all: 是否@所有人

        Returns:
            是否发送成功
        """
        access_token = self.auth.get_user_access_token()
        if not access_token:
            logger.error("获取用户访问令牌失败")
            return False

        url = f"{self.base_url}v1.0/im/me/messages/send"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }

        # 构建消息内容
        message_content = {
            "content": content
        }

        # 添加@信息
        if at_user_ids or is_at_all:
            message_content["at"] = {
                "atUserIds": at_user_ids or [],
                "isAtAll": is_at_all
            }

        data = {
            "content": json.dumps(message_content),
            "receiverUid": receiver_uid,
            "msgType": msg_type
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response_text = response.text
            
            if response.status_code == 200:
                try:
                    response_data = json.loads(response_text)
                    if isinstance(response_data, dict):
                        if response_data.get("success") == "true":
                            logger.info(f"消息发送成功，任务ID: {response_data.get('result', {}).get('openTaskId')}")
                            return True
                        else:
                            logger.error(f"发送消息失败: {response_data}")
                    else:
                        logger.error(f"发送消息失败: 响应格式错误: {response_text}")
                except json.JSONDecodeError:
                    logger.error(f"发送消息失败: 无法解析响应JSON: {response_text}")
            else:
                logger.error(f"发送消息请求失败: HTTP {response.status_code}, 响应: {response_text}")
        except Exception as e:
            logger.error(f"发送消息时发生错误: {str(e)}")

        return False

    def send_text_message(self, receiver_uid: str, text: str, 
                         at_user_ids: Optional[List[str]] = None, is_at_all: bool = False) -> bool:
        """
        发送文本消息

        Args:
            receiver_uid: 接收者ID
            text: 文本内容
            at_user_ids: @的用户ID列表
            is_at_all: 是否@所有人

        Returns:
            是否发送成功
        """
        return self.send_message(receiver_uid, text, "text", at_user_ids, is_at_all)

    def send_markdown_message(self, receiver_uid: str, title: str, text: str,
                            at_user_ids: Optional[List[str]] = None, is_at_all: bool = False) -> bool:
        """
        发送 Markdown 消息

        Args:
            receiver_uid: 接收者ID
            title: 消息标题
            text: Markdown 内容
            at_user_ids: @的用户ID列表
            is_at_all: 是否@所有人

        Returns:
            是否发送成功
        """
        content = f"# {title}\n\n{text}"
        return self.send_message(receiver_uid, content, "markdown", at_user_ids, is_at_all)