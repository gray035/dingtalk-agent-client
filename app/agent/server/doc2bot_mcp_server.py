from mcp.server.fastmcp import FastMCP
from typing import Dict, Any
from loguru import logger

import httpx

# 创建 MCP 服务器实例
mcp = FastMCP("QADetailInfoServer")

# 可提取为配置文件或环境变量
QA_TRACE_URL = "https://pre-lippi-doc2bot.dingtalk.com/qa/trace"

@mcp.tool()
async def query_qa_detail_info(trace_id: str) -> Dict[str, Any]:
    """
    查询问答明细
    参数:
        trace_id: 请求唯一标识
    返回:
        问答明细的对象
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                QA_TRACE_URL,
                json={"traceId": trace_id}
            )
            response.raise_for_status()
            result = response.json()
            if 'retrievalList' in result['result']:
                result['result']['retrievalList'] = [{'content': f"标题:{item.get('name', '')} 答案:{item.get('content', '')}", 'score': item.get('score', 0)} for item in result['result']['retrievalList']]
            # 可以添加日志记录用于调试
            logger.info(f"处理后的问答明细: {result}")
            return result
        except httpx.RequestError as e:
            # 可记录日志并抛出自定义异常或返回默认结构
            raise RuntimeError(f"Network error occurred: {e}")


@mcp.tool()
async def call_agent_code(agent_code: str) -> Dict[str, Any]:
    """
    获取学习详情
    参数:
        agent_code: 智能助手的id
    返回:
        学习详情信息
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                "https://pre-lippi-doc2bot.dingtalk.com/qa/studyDetail",
                json={"agentCode": agent_code}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"处理后的智能助手返回结果: {result}")
            return result
        except httpx.RequestError as e:
            # 可记录日志并抛出自定义异常或返回默认结构
            raise RuntimeError(f"Network error occurred: {e}")


@mcp.resource("employee://{id}")
async def get_employee_profile(id: str) -> Dict[str, Any]:
    """
    获取员工资料（作为补充查询方式）
    """
    return await query_qa_detail_info(id)

if __name__ == "__main__":
    # 以 stdio 协议启动服务器
    mcp.run(transport="stdio")