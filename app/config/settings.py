import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings"""

    # DingTalk API configuration
    # For Stream API (WebSocket)
    DINGTALK_APP_KEY = os.getenv("DINGTALK_APP_KEY", "")
    DINGTALK_APP_SECRET = os.getenv("DINGTALK_APP_SECRET", "")
    DINGTALK_STREAM_TOPIC = os.getenv("DINGTALK_STREAM_TOPIC", "/v1.0/graph/api/invoke")

    # CARD TEMPLATE ID
    DINGTALK_CARD_TEMPLATE_ID = os.getenv("DINGTALK_CARD_TEMPLATE_ID", "")

    # LLM API configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL", "qwen-plus")

settings = Settings()