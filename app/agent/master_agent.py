from agents import Agent
from app.core.message_context import MessageContext
from app.config.settings import settings
from agents.mcp import MCPServerStdio
from agents.run_context import RunContextWrapper
from datetime import datetime

# 动态 instructions 函数
async def dynamic_instructions(context: RunContextWrapper[MessageContext], agent: Agent[MessageContext]) -> str:
    ctx = context.context
    return (
        f"用户信息如下：\n"
        f"- 当前用户名: {ctx.user_name}\n"
        f"- 当前用户工号: {ctx.user_id}\n"
        f"- 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"请根据上述信息，完成用户输入请求"
    )

# 工厂函数，异步初始化 agent
async def get_code_quality_agent():
    # 初始化 MCP server
    server = MCPServerStdio(
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking", "--stdio", "--debug"]
            },
            cache_tools_list=True,
            name="sequential-thinking",
            client_session_timeout_seconds=30.0
        )
    await server.connect()
    
    # 构建 agent
    agent = Agent[MessageContext](
        name="Code Quality Agent",
        instructions=dynamic_instructions,
        model=settings.OPENAI_API_MODEL,
        output_type=str,
        mcp_servers=[server]
    )
    return agent