"""
MCP 服务器实现
"""
import os
import sys
import random
import datetime
from typing import Optional, Dict, List
from loguru import logger
from sqlalchemy import func, desc
from mcp.server.fastmcp import FastMCP
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.llm_service import LLMService
from app.api.auth import get_auth
from app.api.client.open.openapi_client import DingtalkClient

mcp = FastMCP("DINGTALK_MCP_SERVER")
registered_tools = []
llm_service = LLMService()


def register_tool(name: str, description: str):
    def decorator(func):
        mcp.tool(name=name, description=description)(func)
        registered_tools.append((name, description))
        return func
    return decorator

@register_tool(name="list_tools", description="List all available tools and their descriptions")
def list_tools() -> str:
    result = "🛠️ 当前可用功能列表：\n"
    for name, desc in registered_tools:
        result += f"- `{name}`：{desc}\n"
    return result

@register_tool(name="get_weather", description="获取城市天气")
def get_weather(city):
    """
    获取城市天气
    :param city: 城市名称
    :return: 城市天气
    """
    from extension.weather_api.api import get_city_weather
    return get_city_weather(city)

@register_tool(name="extra_order_from_content", description="提取文字中的订单信息，包括订单号、商品名称、数量等，以json格式返回")
def extra_order_from_content(content: str) -> str:
    """
    提取订单信息
    :param content: 消息内容
    :return: 提取的订单信息
    """
    res = llm_service.chat_completion(
        messages=[
            {"role": "user", "content": content},
            {"role": "system", "content": "请提取订单信息，包括订单号、商品名称、数量等，以json格式返回"},
        ],
        tools=None,
        model="qwen-plus"
    )
    if res and res.choices:
        content = res.choices[0].message.content
        if content:
            return content
    return "未能提取到订单信息，请检查消息内容是否包含有效的订单信息。"


@register_tool(name="tell_joke", description="Tell a random joke")
def tell_joke() -> str:
    jokes = [
        "为什么程序员都喜欢黑色？因为他们不喜欢 bug 光。",
        "Python 和蛇有什么共同点？一旦缠上你就放不下了。",
        "为什么 Java 开发者很少被邀去派对？因为他们总是抛出异常。",
    ]
    return random.choice(jokes)


@register_tool(name="get_time", description="Get the current time")
def get_time() -> str:
    now = datetime.datetime.now()
    return f"当前时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}"


@register_tool(name="fortune", description="Draw a random fortune")
def fortune() -> str:
    fortunes = [
        "大吉：今天适合尝试新事物！✨",
        "中吉：平稳的一天，保持专注。",
        "小吉：会有小惊喜出现～",
        "凶：注意不要过度疲劳。",
        "大凶：小心电子设备出问题 🧯"
    ]
    return random.choice(fortunes)

@register_tool(name="send_message", description="给指定用户发送消息 {user:用户名称 content:消息内容}")
def send_message(user: str, content: str) -> str:
    """
    给指定用户发送私信

    Args:
        user: 用户名称
        content: 消息内容

    Returns:
        发送结果描述
    """
    try:
        # 初始化客户端
        dingtalk_client = DingtalkClient(get_auth())
        logger.info(f"开始向用户 '{user}' 发送消息")

        # 搜索用户
        users = dingtalk_client.search_users(user)
        if not users:
            logger.warning(f"未找到用户 '{user}'")
            return f"未找到用户 '{user}'"

        # 获取第一个匹配的用户信息
        user_info = users[0]
        user_id = user_info.get('userId')
        user_name = user_info.get('name', user)

        if not user_id:
            logger.error(f"无法获取用户 '{user}' 的ID")
            return f"无法获取用户 '{user}' 的ID"

        # 发送消息
        success = dingtalk_client.send_text_message(user_id, content)
        if success:
            logger.info(f"成功向用户 '{user_name}' 发送消息")
            return f"成功向 {user_name} 发送了私信: '{content}'"
        else:
            logger.error(f"向用户 '{user_name}' 发送消息失败")
            return f"向 {user_name} 发送私信失败"

    except Exception as e:
        logger.error(f"发送消息时发生错误: {str(e)}")
        return f"发送消息时发生错误: {str(e)}"

@register_tool(name="search_users", description="搜索钉钉用户 {query:搜索关键词 exact_match:是否精确匹配}")
def search_users(query: str, exact_match: bool = False) -> str:
    """
    搜索钉钉用户

    Args:
        query: 搜索关键词
        exact_match: 是否精确匹配，默认为False（模糊匹配）

    Returns:
        用户信息列表的字符串表示
    """
    try:
        # 初始化客户端
        dingtalk_client = DingtalkClient(get_auth())
        logger.info(f"开始搜索用户: {query}")

        # 搜索用户ID
        user_ids = dingtalk_client.search_users(query, exact_match=exact_match)
        if not user_ids:
            logger.warning(f"未找到匹配的用户: {query}")
            return f"未找到匹配的用户: {query}"

        # 获取用户详细信息
        users = dingtalk_client.get_users_info(user_ids)
        if not users:
            logger.warning(f"获取用户详细信息失败: {query}")
            return f"获取用户详细信息失败: {query}"

        # 格式化用户信息
        result = f"找到 {len(users)} 个匹配的用户：\n"
        for user in users:
            result += f"- {user.get('name', '未知用户')} (ID: {user.get('userid', '未知')})\n"
            if user.get('mobile'):
                result += f"  手机号: {user['mobile']}\n"
            if user.get('email'):
                result += f"  邮箱: {user['email']}\n"
            if user.get('department'):
                result += f"  部门: {', '.join(user['department'])}\n"
            result += "\n"

        return result

    except Exception as e:
        logger.error(f"搜索用户时发生错误: {str(e)}")
        return f"搜索用户时发生错误: {str(e)}"

@register_tool(name="get_user_info", description="获取指定用户的详细信息 {user_id:用户ID}")
def get_user_info(user_id: str) -> str:
    """
    获取指定用户的详细信息

    Args:
        user_id: 用户ID

    Returns:
        用户详细信息的字符串表示
    """
    try:
        # 初始化客户端
        dingtalk_client = DingtalkClient(get_auth())
        logger.info(f"开始获取用户信息: {user_id}")

        # 获取用户信息
        url = "https://oapi.dingtalk.com/topapi/v2/user/get"
        access_token = dingtalk_client.auth.get_app_access_token()
        if not access_token:
            logger.error("获取应用访问令牌失败")
            return "获取应用访问令牌失败"

        params = {
            "access_token": access_token
        }
        data = {
            "language": "zh_CN",
            "userid": user_id
        }

        response = requests.post(url, params=params, json=data)
        if response.status_code != 200:
            logger.error(f"获取用户信息请求失败: HTTP {response.status_code}, 响应: {response.text}")
            return f"获取用户信息请求失败: HTTP {response.status_code}"

        result = response.json()
        if result.get("errcode") != "0":
            logger.error(f"获取用户信息失败: {result.get('errmsg')}")
            return f"获取用户信息失败: {result.get('errmsg')}"

        user = result.get("result", {})
        if not user:
            logger.warning(f"未找到用户: {user_id}")
            return f"未找到用户: {user_id}"

        # 格式化用户信息
        result = f"用户信息：\n"
        result += f"- 姓名: {user.get('name', '未知')}\n"
        result += f"- 用户ID: {user.get('userid', '未知')}\n"
        result += f"- 工号: {user.get('job_number', '未知')}\n"
        if user.get('mobile'):
            result += f"- 手机号: {user['mobile']}\n"
        if user.get('email'):
            result += f"- 邮箱: {user['email']}\n"
        if user.get('org_email'):
            result += f"- 企业邮箱: {user['org_email']}\n"
        if user.get('telephone'):
            result += f"- 分机号: {user['telephone']}\n"
        if user.get('avatar'):
            result += f"- 头像: {user['avatar']}\n"
        if user.get('title'):
            result += f"- 职位: {user['title']}\n"
        if user.get('work_place'):
            result += f"- 办公地点: {user['work_place']}\n"
        if user.get('remark'):
            result += f"- 备注: {user['remark']}\n"
        if user.get('dept_id_list'):
            result += f"- 部门: {user['dept_id_list']}\n"
        if user.get('leader_in_dept'):
            result += f"- 部门领导: {'是' if user['leader_in_dept'].get('leader') == 'true' else '否'}\n"
        if user.get('hired_date'):
            from datetime import datetime
            hired_date = datetime.fromtimestamp(int(user['hired_date']) / 1000)
            result += f"- 入职时间: {hired_date.strftime('%Y-%m-%d')}\n"

        return result

    except Exception as e:
        logger.error(f"获取用户信息时发生错误: {str(e)}")
        return f"获取用户信息时发生错误: {str(e)}"

if __name__ == "__main__":
    print(get_weather("北京"))
    mcp.run(transport="stdio")