"""
DingTalk Chatbot Callback Handler

This module implements the callback handler for DingTalk chatbot messages with:
- Message processing and routing
- Error handling and logging
- Statistics tracking
"""

import json
import asyncio
import time
from typing import Any, Dict, Tuple

from dingtalk_stream import GraphRequest, CallbackMessage, AckMessage
from dingtalk_stream.frames import Headers
from dingtalk_stream.graph import GraphResponse, GraphHandler
from loguru import logger

from app.core.message_service import MessageService
from app.core.message_context import MessageContext
from app.api.dingtalk.reply_service import reply_service, CardData,ContentType
from app.config.settings import settings


class DingTalkChatbotHandler(GraphHandler):
    def __init__(self, message_service: MessageService):
        """
        Initialize the handler with a message service

        Args:
            message_service: Service for processing messages
        """
        super().__init__()
        self.message_service = message_service
        self.reply_service = reply_service
        self.processing_lock = asyncio.Lock()
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "errors": 0,
            "last_message_time": 0,
        }

    def pre_start(self):
        """Optional: Called before the handler starts"""
        pass

    async def process(self, callback: CallbackMessage) -> Tuple[int, Dict]:
        """
        Process DingTalk stream message and return GraphResponse
        This method is called by raw_process
        """
        try:
            # Parse incoming message
            graph_request = GraphRequest.from_dict(callback.data)
            logger.info(f"Processing message synchronously... {graph_request.body}")

            # Extract message content and metadata
            text_content, message_metadata = self._parse_message_content(
                graph_request.body
            )

            # Skip empty messages
            if not text_content:
                return self._create_empty_response()

            # 构造 MessageContext
            context = MessageContext(
                content=text_content,
                user_name=message_metadata["sender_nick"],
                user_id=message_metadata["sender_id"],
                sender_union_id=message_metadata["sender_union_id"],
                is_group_chat=message_metadata["conversation_type"] != "1",
                group_name=message_metadata["group_name"],
                conversation_id=message_metadata["conversation_id"],
                timestamp=int(time.time()),
                conversation_token=message_metadata["conversation_token"],
            )

            # Process message with lock to prevent concurrent processing
            async with self.processing_lock:
                try:
                    # Before the function call
                    if context.is_group_chat:
                        open_conversation_id = context.conversation_id
                    else:
                        open_conversation_id = None

                    # 1. 立刻响应
                    await self.reply_service.reply(
                        context.conversation_token,
                        None,
                        content_type=ContentType.AI_CARD,
                        card_data=CardData(
                            card_data={
                                "query": text_content,
                                "config": {"autoLayout": True},
                                "preparations": [
                                    {"name": "正在理解需求", "progress": 20}
                                ]
                            },
                            template_id=settings.DINGTALK_CARD_TEMPLATE_ID
                            # options={"componentTag": "staticComponent"},
                        )
                    )

                    # 2. 后台异步处理业务并更新卡片
                    
                    await self._process_and_update(
                        context, message_metadata, context.conversation_token
                    )
                    
                    return self._create_empty_response()

                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    return self._create_error_response(str(e))

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error parsing callback message: {str(e)}", exc_info=True)
            return self._create_error_response(f"Error parsing message: {str(e)}")

    async def _process_and_update(
        self, context: MessageContext, message_metadata, conversation_token
    ):
        try:
            # 通过流式更新卡片
            await self._process_message_with_service(context, message_metadata)
        except Exception as e:
            # 失败时也可以更新卡片为失败状态
            await self.reply_service.update_card(
                conversation_token=conversation_token,
                card_data=CardData(
                    content="处理失败", template_id=settings.DINGTALK_CARD_TEMPLATE_ID
                ),
                content_type="ai_card",
            )
        finally:
            logger.info("Finished processing message")

    def _parse_message_content(self, body: Any) -> Tuple[str, Dict[str, Any]]:
        """Parse message content and extract metadata"""
        try:
            # Parse body if it's a string
            if isinstance(body, str):
                body = json.loads(body)

            # Extract text content directly from input field
            text_content = body.get("input", "")
            metadata = {
                "sender_id": body.get("sender_id", ""),
                "sender_nick": body.get("sender_nick", "Unknown User"),
                "conversation_id": body.get("conversation_id", ""),
                "conversation_type": body.get("conversation_type", "1"),
                "group_name": body.get("conversation_title", ""),
                "conversation_token": body.get("conversationToken", ""),
                "sender_union_id": body.get("sender_union_id", ""),
            }

            return text_content, metadata

        except Exception as e:
            logger.warning(f"Failed to parse message content: {e}")
            return "", {}

    async def _process_message_with_service(
        self, context: MessageContext, metadata: Dict[str, Any]
    ) -> Any:
        """Process message through message service"""
        try:
            # 直接用传入的 context
            return await self.message_service.process_stream_message(context)
        except Exception as e:
            logger.error(f"Error creating message context: {str(e)}", exc_info=True)
            raise

    def _create_response(self, result: Any) -> Tuple[int, Dict]:
        """Create appropriate response based on result type"""
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
        """Create base response with common settings"""
        response = GraphResponse()
        response.status_line.code = 200
        response.status_line.reason_phrase = "OK"
        response.headers["Content-Type"] = "application/json"
        return response

    def _create_tool_response(self, result: Dict) -> Dict:
        """Create response for tool execution results"""
        return {
            "tool_name": result["tool_name"],
            "tool_args": result["tool_args"],
            "tool_output": self._make_json_serializable(result["tool_output"]),
            "text": result["summary"],
        }

    def _create_text_response(self, result: Any) -> Dict:
        """Create response for text content"""
        if hasattr(result, "text") and hasattr(result, "type"):
            return {"text": result.text}
        return {"text": self._make_json_serializable(result)}

    def _create_empty_response(self) -> Tuple[int, Dict]:
        """Create response for empty messages"""
        response = self._create_base_response()
        response.body = {"content": "No valid text content"}
        
        return AckMessage.STATUS_OK, response.to_dict()

    def _create_error_response(self, error_message: str) -> Tuple[int, Dict]:
        """Create response for errors"""
        response = self._create_base_response()
        response.status_line.code = 500
        response.status_line.reason_phrase = "Internal Server Error"
        response.body = {"error": error_message}
        return AckMessage.STATUS_SYSTEM_EXCEPTION, response.to_dict()

    async def raw_process(self, callback: CallbackMessage) -> AckMessage:
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

    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON serializable form"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif hasattr(obj, "text") and hasattr(obj, "type"):
            return obj.text
        elif hasattr(obj, "__dict__"):
            return self._make_json_serializable(obj.__dict__)
        else:
            return str(obj)

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset all statistics counters except last_message_time"""
        self.stats.update(
            {"messages_received": 0, "messages_processed": 0, "errors": 0}
        )


__all__ = ["DingTalkChatbotHandler"]
