"""
Agent manager for handling different types of agents
"""
from typing import Dict, Any, Optional, List, TypedDict
from typing_extensions import NotRequired
from loguru import logger
from app.agent.employee_agent import create_employee_info_agent
from app.agent.doc2bot_agent import create_doc2bot_agent
from openai import AsyncOpenAI
from app.drag.drag_service import *
from app.service.message_context import AgentRunningContext
from app.core.stream_card import StreamCard
from openai.types.responses import ResponseTextDeltaEvent
from app.core.agent import HandleResult

from agents import (
    
    Runner,set_default_openai_client, set_default_openai_api, set_tracing_disabled
    
)

from app.config.settings import settings
from app.service.message_context import MessageContext

class AgentManager:
    def __init__(self, current_user_info: Optional[Dict[str, Any]] = None):
        self.current_user_info = current_user_info or {}
        self.agent = None
        self.client = None
        self._setup_llm_client()
        logger.info(f"初始化 AgentManager，用户信息: {self.current_user_info}")

    def _setup_llm_client(self):
        """设置 LLM 客户端和全局配置"""
        try:
            base_url = settings.LLM_API_BASE_URL
            api_key = settings.LLM_API_KEY
            
            if not base_url or not api_key:
                raise ValueError("Please set LLM_API_BASE_URL and LLM_API_KEY")
            
            self.client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key
            )
            set_default_openai_client(client=self.client, use_for_tracing=False)
            set_default_openai_api("chat_completions")
            set_tracing_disabled(disabled=True)
            logger.info(" LLM Client 设置成功")
        except Exception as e:
            logger.error(f"LLM Client 设置失败: {str(e)}", exc_info=True)
            raise


    async def cleanup(self):
        """清理资源"""
        try:
            # 停止所有 MCP 服务器
            for server in self.agent.mcp_servers:
                try:
                    await server.cleanup()
                    logger.info(f"MCP 服务器 {server.name} 已清理")
                except Exception as e:
                    logger.error(f"清理 MCP 服务器 {server.name} 失败: {str(e)}")
            self.agent.mcp_servers = []
            self.agent = None
            self.client = None
            logger.info("所有资源已清理")
        except Exception as e:
            logger.error(f"清理资源失败: {str(e)}", exc_info=True)
            raise


    async def process_message(self, context: MessageContext) -> HandleResult:
        """处理消息"""
        try:
            logger.info(f"收到消息: {context.content}")
            # agent 执行逻辑
            self.agent = await create_doc2bot_agent()
            # 1. 新建流式卡片，卡片会显示在AI助理的聊天窗口中
            stream_card = await StreamCard.create(context.conversation_token)

            agent_running_context = AgentRunningContext(context=context, stream_card=stream_card)
            result = Runner.run_streamed(self.agent, context=agent_running_context, input=context.content)
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    logger.info("event delta: {}".format(event.data.delta))
                    # 增量更新卡片内容
                    await stream_card.update_delta(event.data.delta)

            # 结束卡片更新，停止等待动画
            await stream_card.finish()

            # 返回成功，AI助理平台根据直通模式的配置，会忽略这个返回值
            return HandleResult(200, "OK", "OK")
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return HandleResult(500, "Internal Server Error", str(e))
