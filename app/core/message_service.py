from typing import Dict, Any, List
from loguru import logger
import asyncio

from .message_context import MessageContext
from app.api.dingtalk.reply_service import reply_service
from app.agent.agent_manager import AgentManager


class MessageService:
    def __init__(self):
        self.agent_manager = None
        self.reply_service = None
        self._init_lock = asyncio.Lock()


    async def process_stream_message(self, context: MessageContext) -> str:
        """
        Process a stream message using the agent.
        
        Args:
            context: Message context containing all necessary information
        
        Returns:
            Dict containing the processed message response
        """
        try:
            if not context.content:
                return {
                    "status": "error",
                    "message": "Empty message content"
                }

            # Log message processing
            logger.info(f"Processing message from {context.user_name} ({context.user_id}) in {'group' if context.is_group_chat else 'private'} chat")
            if context.is_group_chat and context.group_name:
                logger.info(f"Group: {context.group_name}")

            # 确保 agent_manager 已初始化
            agent_manager = AgentManager(current_user_info=context.to_dict())
            
            # Process message with agent
            response = await agent_manager.process_message(context)

            # Send reply if conversation token is available
            # if context.conversation_token:
            #     await reply_service.reply_text(context.conversation_token, response if response else "暂无回复")

            # Construct response
            return response

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            error_message = f"Error processing message: {str(e)}"
            
            # Try to send error message if conversation token is available
            if context.conversation_token:
                await reply_service.reply_text(context.conversation_token, error_message)
            
            return {
                "status": "error",
                "message": error_message
            }


    async def cleanup(self):
        """清理资源"""
        if self.agent_manager:
            await self.agent_manager.cleanup()
            self.agent_manager = None


# Create a singleton instance
message_service = MessageService() 