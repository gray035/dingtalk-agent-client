import requests
from loguru import logger

# 可提取为配置文件或环境变量
QA_TRACE_URL = "https://pre-lippi-doc2bot.dingtalk.com/qa/trace"

def call_qa_trace(trace_id):
    response = requests.post(QA_TRACE_URL, json={"traceId": trace_id})
    result = response.json()
    if 'retrievalList' in result['result']:
        result['result']['retrievalList'] = [
            {'content': f"标题:{item.get('name', '')} 答案:{item.get('content', '')}", 'score': item.get('score', 0)}
            for item in result['result']['retrievalList']]
    # 可以添加日志记录用于调试
    logger.info(f"处理后的问答明细: {result}")
    return result

def call_agent_code(agent_code):
    return agent_code

