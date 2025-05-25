from mcp.server.fastmcp import FastMCP
from typing import Dict, Any

# 模拟员工数据库（实际场景应连接真实数据库）
EMPLOYEE_DB = {
    "075881": {"name": "张三", "department": "技术部", "position": "工程师"},
    "E002": {"name": "李四", "department": "市场部", "position": "主管"}
}

# 创建 MCP 服务器实例
mcp = FastMCP("EmployeeInfoServer")

@mcp.tool()
async def query_employee_info(employee_id: str) -> Dict[str, Any]:
    """
    查询员工详细信息
    参数:
        employee_id: 员工工号（如 E001）
    返回:
        包含姓名、部门、职位的字典
    """
    return EMPLOYEE_DB.get(employee_id, {"error": "未找到员工信息"})

@mcp.resource("employee://{id}")
async def get_employee_profile(id: str) -> Dict[str, Any]:
    """
    获取员工资料（作为补充查询方式）
    """
    return await query_employee_info(id)

if __name__ == "__main__":
    # 以 stdio 协议启动服务器
    mcp.run(transport="stdio")