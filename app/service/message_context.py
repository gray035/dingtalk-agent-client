"""
Message context data structures
"""
from typing import Optional
from dataclasses import dataclass
from app.core.stream_card import StreamCard

@dataclass
class MessageContext:
    """Data class for message context information"""
    # 用户相关属性
    user_name: str
    user_id: str # Typically senderId from DingTalk
    content: str
    # 以下为有默认值的字段
    sender_union_id: Optional[str] = None
    is_group_chat: bool = False
    group_name: Optional[str] = None
    conversation_id: Optional[str] = None
    timestamp: Optional[str] = None # Consider converting to datetime object for consistency
    conversation_token: Optional[str] = None

    @classmethod
    def from_dingtalk_message(cls, message: dict) -> 'MessageContext':
        """Create MessageContext from DingTalk message"""
        return cls(
            user_name=message.get("senderNick", "Unknown"),
            user_id=message.get("senderId", ""),
            sender_union_id=message.get("senderUnionId"),
            content=message.get("text", {}).get("content", ""),
            is_group_chat=message.get("conversationType") == "2",
            group_name=message.get("conversationTitle"),
            conversation_id=message.get("conversationId"),
            timestamp=message.get("createAt"),
            conversation_token=message.get("conversationToken"),
        )

    def to_dict(self) -> dict:
        """Convert MessageContext to dictionary for agent context or serialization"""
        data = {
            "user_name": self.user_name,
            "user_id": self.user_id,
            "sender_union_id": self.sender_union_id,
            "content": self.content,
            "is_group_chat": self.is_group_chat,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
        }
        if self.is_group_chat:
            data["group_name"] = self.group_name
        if self.conversation_token:
            data["conversation_token"] = self.conversation_token
        return data

class AgentRunningContext:
    def __init__(self, context: MessageContext, stream_card: StreamCard):
        self.context = context
        self.stream_card = stream_card