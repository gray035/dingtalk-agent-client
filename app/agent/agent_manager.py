"""
Agent manager for handling different types of agents
"""
from typing import Dict, Any, Optional, List, TypedDict, Union
from typing_extensions import NotRequired
from loguru import logger


from agents import (
    
    Runner,
    
)
from agents.mcp import MCPServerStdio
from app.config.settings import settings
from app.api.dingtalk.reply_service import CardData, reply_service
from app.agent.master_agent import get_code_quality_agent
from app.core.message_context import MessageContext

class MCPConfig(TypedDict):
    """Configuration for MCP servers."""
    convert_schemas_to_strict: NotRequired[bool]
    """If True, we will attempt to convert the MCP schemas to strict-mode schemas."""


class AgentManager:
    def __init__(self, current_user_info: Optional[Dict[str, Any]] = None):
        self.reply_service = reply_service
        self.agents: Dict[str, Any] = {}
        self.current_user_info = current_user_info or {}
        self.mcp_servers: List[MCPServerStdio] = []
        self.agent = None
        self.client = None
        logger.info(f"初始化 AgentManager，用户信息: {self.current_user_info}")

    def _prepare_progress(self, index) -> float:
        return min(index * 5 + 40, 90)

    async def _send_progress(self, context: MessageContext, title, progress):
        """发送进度"""
        card_data=CardData(
            card_data={"preparations": [{"name": title, "progress": progress}]},
            template_id=settings.DINGTALK_CARD_TEMPLATE_ID
        )
        # 发送卡片内容
        await self.reply_service.update_card(
            conversation_token=context.conversation_token,
            card_data=card_data,
        )

    async def cleanup(self):
        """清理资源"""
        try:
            # 停止所有 MCP 服务器
            for server in self.mcp_servers:
                try:
                    await server.cleanup()
                    logger.info(f"MCP 服务器 {server.name} 已清理")
                except Exception as e:
                    logger.error(f"清理 MCP 服务器 {server.name} 失败: {str(e)}")
            self.mcp_servers = []
            self.agent = None
            self.client = None
            logger.info("所有资源已清理")
        except Exception as e:
            logger.error(f"清理资源失败: {str(e)}", exc_info=True)
            raise


    async def process_message(self, context: MessageContext) -> str:
        """处理消息"""
        try:
            logger.info(f"收到消息: {context.content}")
            # agent 执行逻辑
            agent = await get_code_quality_agent()
            result = await Runner.run(agent, context.content, context=context)
            logger.info(f"\n\nFinal response:\n{result.final_output}")
                    # 创建卡片内容
            delta_card = CardData(
                card_data={
                    "key": "content",
                    "value": result.final_output,
                    "isFinalize": False
                },
                options={
                    "componentTag": "streamingComponent"
                },
                template_id=settings.DINGTALK_CARD_TEMPLATE_ID,
            )
            # 发送卡片内容
            await self.reply_service.update_card(
                conversation_token=context.conversation_token,
                card_data=delta_card,
            )
            
            await self._send_progress(context, "完成输出", 100)
            await self.reply_service.finish_card(conversation_token=context.conversation_token)           

            return result
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return f"处理消息时出错: {str(e)}"
