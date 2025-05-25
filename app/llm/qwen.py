from openai import OpenAI
from typing import List, Dict, Any
import os


class QwenClient:
    def __init__(self):
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url="https://aipaas.dingtalk.alibaba-inc.com/v1",
            api_key="dummy-key",  # 钉钉API不需要实际的OpenAI密钥
            default_headers={
                "productCode": "DING_APP_STORE",
                "module": "qwen3-235b"
            }
        )

    def chat_stream(self, messages: List[Dict[str, str]]) -> Any:
        """
        使用流式方式与通义千问模型对话

        Args:
            messages: 对话历史，格式为[{"role": "user/assistant", "content": "内容"}]

        Returns:
            流式响应对象
        """
        try:
            return self.client.chat.completions.create(
                model="qwen3-235b",
                messages=messages,
                stream=True
            )
        except Exception as e:
            print(f"错误: {str(e)}")
            return None


def main():
    # 创建客户端实例
    client = QwenClient()

    # 测试对话历史
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么我可以帮你的吗？"},
        {"role": "user", "content": "请介绍一下你自己"}
    ]

    print("用户: 请介绍一下你自己")
    print("AI: ", end="", flush=True)

    # 获取流式响应
    stream = client.chat_stream(messages)
    if stream:
        try:
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    print(chunk.choices[0].delta.content, end="", flush=True)
            print()  # 最后打印换行
        except Exception as e:
            print(f"\n处理响应时出错: {str(e)}")


if __name__ == "__main__":
    main()