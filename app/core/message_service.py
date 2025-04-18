# app/core/message_service.py
"""
Service for processing DingTalk messages
"""
import json
import os

from loguru import logger
from datetime import datetime
from app.config.settings import settings
from app.core.llm_service import LLMService
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

class MessageService:
    """Service for processing messages"""

    def __init__(self, dingtalk_client):
        self.dingtalk_client = dingtalk_client
        self.llm_service = LLMService()
        self.mcp_transport = PythonStdioTransport("app/core/mcp_server.py", env={"PATHEXT": os.environ.get("PATHEXT", "")})
        self.system_message = {"role": "system", "content": "你是一个很有帮助的助手。当用户提问需要调用工具时，请使用 tools 中定义的函数。"}

    async def process_stream_message(self, user_name, user_id, content, is_group_chat, group_name, chat_id):
        """Process a message from the DingTalk stream"""
        try:
            message_source = f"群聊 {group_name}" if is_group_chat else "私聊"
            logger.info(f"收到{message_source}消息 - 用户: {user_name}, 内容: {content}")

            # Skip if content is empty
            if not content or not content.strip():
                logger.warning("收到空消息，跳过处理")
                return None

            # Check for function call trigger
            if content.strip().startswith(settings.FUNCTION_TRIGGER_FLAG):
                return await self._handle_function_call(user_name, content, chat_id, is_group_chat)

            return None

        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            return f"处理消息时出错: {str(e)}"

    async def _handle_function_call(self, user_name, content, chat_id, is_group_chat):
        """Handle function call triggered by message"""
        try:
            logger.info(f"触发flag函数调用 - 用户: {user_name}, 内容: {content}")
            query = content.strip()[len(settings.FUNCTION_TRIGGER_FLAG):].strip()
            if not self.llm_service.is_available():
                error_msg = "未在配置中设置 OPENAI_API_KEY"
                logger.error(error_msg)
                return error_msg

            async with Client(self.mcp_transport) as mcp_client:
                tools = []
                for tool in await mcp_client.list_tools():
                    info = tool.model_dump() if hasattr(tool, "model_dump") else tool.dict()
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": info["name"],
                            "description": info.get("description", ""),
                            "parameters": info.get("parameters", {})
                        }
                    })
                messages = [
                    self.system_message,
                    {"role": "user", "content": query}
                ]
                resp = self.llm_service.chat_completion(messages, tools)
                msg = resp.choices[0].message
                if msg.tool_calls:
                    call = msg.tool_calls[0]
                    fn_name = call.function.name
                    args = json.loads(call.function.arguments)
                    output = await mcp_client.call_tool(fn_name, args)
                    logger.info(f"调用函数 {fn_name} -> {output}")

                    # 处理输出结果，确保可以被正确处理
                    output_for_llm = output
                    # 如果是 TextContent 类型，提取文本内容
                    if hasattr(output, "text") and hasattr(output, "type"):
                        output_for_llm = output.text

                    messages.append(msg)
                    messages.append({
                        "role": "tool",
                        "content": output_for_llm if isinstance(output_for_llm, str) else str(output_for_llm),
                        "tool_call_id": call.id
                    })
                    summary = self.llm_service.chat_completion(messages)
                    response = summary.choices[0].message.content

                    # 构建包含工具执行结果的响应
                    tool_result = {
                        "tool_name": fn_name,
                        "tool_args": args,
                        "tool_output": output,  # 保留原始输出，由 dingtalk_stream_client 处理序列化
                        "summary": response
                    }
                    return tool_result
                else:
                    return msg.content

        except Exception as e:
            logger.error(f"处理flag函数调用时出错: {str(e)}")
            return f"执行错误: {str(e)}"