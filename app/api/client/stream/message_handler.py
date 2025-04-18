# app/api/dingtalk_stream_client.py
import json
import asyncio
import threading
import time
import urllib.parse
from typing import Callable, Any, Dict, Optional, Tuple

from dingtalk_stream import GraphRequest, CallbackMessage, AckMessage
from dingtalk_stream import DingTalkStreamClient
from dingtalk_stream import Credential
from dingtalk_stream.frames import Headers
from dingtalk_stream.graph import GraphResponse, GraphHandler
from loguru import logger

from app.config.settings import settings
from app.core.message_service import MessageService


class DingTalkChatbotHandler(GraphHandler):
    """Enhanced handler for processing DingTalk chatbot messages"""

    def __init__(self, message_service: MessageService):
        """
        Initialize with a message service

        Args:
            message_service: Service for processing messages
        """
        super(GraphHandler, self).__init__()
        self.message_service = message_service
        self.processing_lock = asyncio.Lock()
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "errors": 0,
            "last_message_time": 0
        }

    def pre_start(self):
        """Optional: Called before the handler starts (for dingtalk_stream compatibility)"""
        pass

    async def process(self, callback: CallbackMessage):
        """
        处理钉钉流消息并返回 GraphResponse
        此方法由 raw_process 方法调用
        """
        try:
            # 解析传入的消息
            graph_request = GraphRequest.from_dict(callback.data)
            logger.debug(f"正在同步处理消息... {graph_request.body}")

            # 提取消息内容和元数据
            text_content, message_metadata = self._parse_message_content(graph_request.body)
            
            # 跳过空消息
            if not text_content:
                return self._create_empty_response()

            # 使用锁处理消息，防止并发处理
            async with self.processing_lock:
                try:
                    # 通过消息服务处理消息
                    result = await self._process_message_with_service(text_content, message_metadata)
                    
                    # 创建并返回适当的响应
                    return self._create_response(result)
                    
                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(f"处理消息时出错: {str(e)}", exc_info=True)
                    return self._create_error_response(str(e))

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"解析回调消息时出错: {str(e)}", exc_info=True)
            return self._create_error_response(f"解析消息时出错: {str(e)}")

    def _parse_message_content(self, body: Any) -> Tuple[str, Dict[str, Any]]:
        """解析消息内容并提取元数据"""
        try:
            # 如果 body 是字符串，则解析它
            if isinstance(body, str):
                body = json.loads(body)
            
            # 创建消息对象并提取内容
            message = type("IncomingMessage", (), body)() if isinstance(body, dict) else body
            text_content = body.get("input", "") if isinstance(body, dict) else ""
            
            # 提取元数据
            metadata = {
                "sender_id": getattr(message, "sender_id", None),
                "sender_nick": getattr(message, "sender_nick", "Unknown User"),
                "conversation_id": getattr(message, "conversation_id", None),
                "conversation_type": getattr(message, "conversation_type", "1"),
                "group_name": getattr(message, "conversation_title", None)
            }
            
            return text_content, metadata
            
        except Exception as e:
            logger.warning(f"解析消息内容失败: {e}")
            return "", {}

    async def _process_message_with_service(self, text_content: str, metadata: Dict[str, Any]) -> Any:
        """通过消息服务处理消息"""
        is_group_chat = metadata["conversation_type"] != '1'
        
        return await self.message_service.process_stream_message(
            user_name=metadata["sender_nick"],
            user_id=metadata["sender_id"],
            content=text_content,
            is_group_chat=is_group_chat,
            group_name=metadata["group_name"],
            chat_id=metadata["conversation_id"]
        )

    def _create_response(self, result: Any) -> Tuple[int, Dict]:
        """根据结果类型创建适当的响应"""
        if not result:
            return self._create_empty_response()

        self.stats["messages_processed"] += 1
        response = self._create_base_response()

        if isinstance(result, dict) and "tool_name" in result:
            response.body = self._create_tool_response(result)
        else:
            response.body = self._create_text_response(result)

        return AckMessage.STATUS_OK, response.to_dict()

    def _create_base_response(self) -> GraphResponse:
        """创建带有通用设置的基础响应"""
        response = GraphResponse()
        response.status_line.code = 200
        response.status_line.reason_phrase = "OK"
        response.headers["Content-Type"] = "application/json"
        return response

    def _create_tool_response(self, result: Dict) -> Dict:
        """创建工具执行结果的响应"""
        return {
            "tool_name": result["tool_name"],
            "tool_args": result["tool_args"],
            "tool_output": self._make_json_serializable(result["tool_output"]),
            "text": result["summary"]
        }

    def _create_text_response(self, result: Any) -> Dict:
        """创建文本内容的响应"""
        if hasattr(result, "text") and hasattr(result, "type"):
            return {"text": result.text}
        return {"text": self._make_json_serializable(result)}

    def _create_empty_response(self) -> Tuple[int, Dict]:
        """创建空消息的响应"""
        response = self._create_base_response()
        response.body = {"text": "No valid text content"}
        return AckMessage.STATUS_OK, response.to_dict()

    def _create_error_response(self, error_message: str) -> Tuple[int, Dict]:
        """创建错误响应"""
        response = self._create_base_response()
        response.status_line.code = 500
        response.status_line.reason_phrase = "Internal Server Error"
        response.body = {"error": error_message}
        return AckMessage.STATUS_SYSTEM_EXCEPTION, response.to_dict()

    async def raw_process(self, callback: CallbackMessage):
        """
        Process a message from DingTalk stream and return an AckMessage
        This method follows the dingtalk_stream library's expected behavior
        """
        code, response_dict = await self.process(callback)
        ack_message = AckMessage()
        ack_message.code = code
        ack_message.headers.message_id = callback.headers.message_id
        ack_message.headers.content_type = Headers.CONTENT_TYPE_APPLICATION_JSON
        ack_message.data = {"response": response_dict}
        return ack_message


    def _extract_message_content(self, message: Any) -> str:
        """
        Extract content from different message types

        Args:
            message: The message object

        Returns:
            The extracted text content
        """
        # Handle different message types
        if hasattr(message, 'msgtype'):
            msgtype = message.msgtype

            if msgtype == 'text' and hasattr(message, 'text') and hasattr(message.text, 'content'):
                return message.text.content
            elif msgtype == 'markdown' and hasattr(message, 'markdown'):
                markdown = message.markdown
                title = markdown.title if hasattr(markdown, 'title') else 'Untitled'
                text = markdown.text if hasattr(markdown, 'text') else ''
                return f"[Markdown: {title}] {text[:50]}..."
            elif msgtype == 'image':
                return "[Image message]"
            elif msgtype == 'file':
                filename = message.file.file_name if hasattr(message, 'file') and hasattr(message.file, 'file_name') else 'Unnamed file'
                return f"[File: {filename}]"
            else:
                return f"[{msgtype} message]"

        # Default case if message type cannot be determined
        return "[Unknown message type]"

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        return self.stats




    def _make_json_serializable(self, obj):
        """将对象转换为可 JSON 序列化的形式"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif hasattr(obj, "text") and hasattr(obj, "type"):
            # 处理 TextContent 类型
            return obj.text
        elif hasattr(obj, "__dict__"):
            # 尝试将对象转换为字典
            return self._make_json_serializable(obj.__dict__)
        else:
            # 其他类型转换为字符串
            return str(obj)


__all__ = ["DingTalkChatbotHandler"]