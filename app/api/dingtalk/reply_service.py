"""
DingTalk message reply service
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import json

from alibabacloud_dingtalk.ai_interaction_1_0.client import Client as DingTalkAIClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.ai_interaction_1_0 import models as dingtalk_models
from alibabacloud_tea_util import models as util_models
from loguru import logger

from .dingtalk_auth import get_auth


class ContentType(Enum):
    """DingTalk message content types"""
    TEXT = "text"
    MARKDOWN = "markdown"
    AI_CARD = "ai_card"


@dataclass
class CardData:
    """Data for AI Card content"""
    card_data: Dict[str, Any] = None
    template_id: str = None
    options: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "templateId": self.template_id,
            "cardData": self.card_data,
            "options": self.options
        }


class DingTalkReplyService:
    """Service for sending replies to DingTalk conversations"""

    def __init__(self):
        self.client = self._create_client()
        self.auth = get_auth()

    def _create_client(self) -> DingTalkAIClient:
        """Create DingTalk AI client"""
        config = open_api_models.Config(
            protocol='https',
            region_id='central'
        )
        return DingTalkAIClient(config)

    async def reply(
        self,
        conversation_token: str,
        content: str = None,
        content_type: ContentType = ContentType.TEXT,
        card_data: Optional[CardData] = None
    ) -> bool:
        """
        Send reply to a DingTalk conversation
        
        Args:
            conversation_token: Token for the conversation
            content: Message content
            content_type: Type of content (text, markdown, or ai_card)
            card_data: Data for AI Card if content_type is ai_card
            
        Returns:
            bool: Whether the reply was successful
        """
        try:
            # Get access token
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("Failed to get access token")
                return False

            # Prepare headers
            headers = dingtalk_models.ReplyHeaders()
            headers.x_acs_dingtalk_access_token = access_token

            # Prepare content
            if content_type == ContentType.AI_CARD and card_data:
                content = json.dumps(card_data.to_dict())

            # Create request
            request = dingtalk_models.ReplyRequest(
                conversation_token=conversation_token,
                content_type=content_type.value,
                content=content
            )

            # Send reply
            await self.client.reply_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions()
            )

            logger.info(f"Successfully sent {content_type.value} reply to conversation {conversation_token}")
            return True

        except Exception as e:
            logger.error(f"Failed to send reply: {str(e)}")
            if hasattr(e, 'code') and hasattr(e, 'message'):
                logger.error(f"Error code: {e.code}, message: {e.message}")
            return False

    async def reply_text(self, conversation_token: str, text: str) -> bool:
        """Convenience method for sending text replies"""
        return await self.reply(conversation_token, text, ContentType.TEXT)

    async def reply_markdown(self, conversation_token: str, markdown: str) -> bool:
        """Convenience method for sending markdown replies"""
        return await self.reply(conversation_token, markdown, ContentType.MARKDOWN)

    async def reply_card(self, conversation_token: str, card_data: CardData) -> bool:
        """Convenience method for sending AI Card replies"""
        return await self.reply(
            conversation_token,
            "",  # Content will be generated from card_data
            ContentType.AI_CARD,
            card_data
        )

    async def prepare_card(
        self,
        open_conversation_id: str = None,
        card_data: CardData = None,
        content_type: str = "ai_card",
        union_id: str = None
    ) -> str:
        """
        主动模式下发送 loading 卡片，返回 conversation_token
        """
        try:
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("Failed to get access token")
                return ""

            headers = dingtalk_models.PrepareHeaders()
            headers.x_acs_dingtalk_access_token = access_token

            request = dingtalk_models.PrepareRequest(
                open_conversation_id=open_conversation_id,
                content_type=content_type,
                content=json.dumps(card_data.to_dict()),
                union_id=union_id
            )

            response = await self.client.prepare_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions()
            )
            # 返回 conversation_token
            return response.body.result.conversation_token
        except Exception as e:
            logger.error(f"Failed to prepare card: {str(e)}")
            return ""

    async def update_card(
        self,
        conversation_token: str,
        card_data: CardData,
        content_type: str = "ai_card"
    ) -> bool:
        """
        主动模式下更新卡片内容
        """
        try:
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("Failed to get access token")
                return False

            headers = dingtalk_models.UpdateHeaders()
            headers.x_acs_dingtalk_access_token = access_token

            request = dingtalk_models.UpdateRequest(
                conversation_token=conversation_token,
                content_type=content_type,
                content=json.dumps(card_data.to_dict())
            )

            await self.client.update_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions()
            )

            return True
        except Exception as e:
            logger.error(f"Failed to update card: {str(e)}")
            return False

    async def finish_card(
        self,
        conversation_token: str
    ) -> bool:
        """
        主动模式下完结卡片
        """
        try:
            access_token = self.auth.get_app_access_token()
            if not access_token:
                logger.error("Failed to get access token")
                return False

            headers = dingtalk_models.FinishHeaders()
            headers.x_acs_dingtalk_access_token = access_token

            request = dingtalk_models.FinishRequest(
                conversation_token=conversation_token
            )

            await self.client.finish_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions()
            )
            return True
        except Exception as e:
            logger.error(f"Failed to finish card: {str(e)}")
            return False


# Create singleton instance
reply_service = DingTalkReplyService() 