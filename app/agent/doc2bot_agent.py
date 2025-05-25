from agents import Agent
from app.config.settings import settings
from agents.mcp import MCPServerStdio
from agents.run_context import RunContextWrapper
from datetime import datetime
from app.service.message_context import MessageContext
async def dynamic_instructions(context: RunContextWrapper[MessageContext], agent: Agent[MessageContext]) -> str:
    # 递归解包context，直到找到MessageContext
    ctx = context
    while hasattr(ctx, "context") and not isinstance(ctx, MessageContext):
        ctx = ctx.context

    # 直接使用当前时间
    dt = datetime.now()
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")

    # 构建基础用户信息部分
    user_info = (
        f"## 用户信息\n"
        f"- 当前用户名: {ctx.user_name or '未知'}\n"
        f"- 当前用户工号: {ctx.user_id or '未知'}\n"
        f"- 当前时间: {formatted_time}\n"
    )

    # 基础信息查询助理的核心指令
    core_instruction = """
## 角色
你是一个问答系统的排查助理，可以通过traceId查询（traceId是30位长的字符串，如：0b51258d17479908039123525e1507）一次问答请求的明细。

### 核心能力
1. **用户信息解析**：从用户输入中提取traceId的信息
2. **请求信息查询**：通过traceId调工具去查询一次问答的明细

### 工作流程指南
当收到用户请求时：
1. 解析用户输入，识别关键信息（如traceId）
2. 使用合适的工具查询所需的基础信息
3. 整合查询结果，以结构化格式输出
"""

    # 工作流程示例部分
    workflow_examples = """
### 工作流程示例
**基础用户信息查询流程**:
1. 解析用户输入，提取出traceId
2. 使用traceId查询问答的明细信息
3. 结构化整理用户数据并输出

### 输出格式
通过查询到的过程信息（如用户的问题（question），助理的回答（answer），召回的片段（retrievalList中的Content内容））输出分析结果，以及改进建议
"""

    # 组合完整的动态指令
    final_instruction = f"{user_info}\n{core_instruction}\n{workflow_examples}\n\n请根据用户输入，提取所需的用户信息和团队数据，为后续处理提供基础支持。输出必须是一个包含用户信息的列表。"
    return final_instruction

# MCP服务器创建函数
async def create_doc2bot_info_mcp():
    mcp_server = MCPServerStdio(
        name="qa_debug_mcp",
        params={
            "command": "python",
            "args": ["/Users/yangshenneng/PycharmProjects/dingtalk-agent-client/app/agent/server/doc2bot_mcp_server.py"]
        },
        client_session_timeout_seconds = 600.0
    )
    await mcp_server.connect()
    return mcp_server

# Agent工厂函数
async def create_doc2bot_agent():
    mcp_server = await create_doc2bot_info_mcp()
    agent = Agent[MessageContext](
        name="问答问题排查助手",
        instructions=dynamic_instructions,
        model=settings.LLM_API_MODEL,
        mcp_servers=[mcp_server]
    )
    return agent
