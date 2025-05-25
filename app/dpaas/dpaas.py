from app.agent.doc2bot_agent import create_doc2bot_agent

# 创建 MCP 服务器连接
employee_server = MCPServerStdio(
    params={
        "command": "python",
        "args": ["/Users/yangshenneng/PycharmProjects/dingtalk-agent-client/app/agent/server/doc2bot_mcp_server.py"]
    }
)

# 创建 Agent 实例
agent = Agent(
    name="问答排查助理",
    instructions="使用工具查询问答明细",
    mcp_servers=[employee_server]
)

if __name__ == '__main__':
    agent.run("0b51258d17479908039123525e1507")