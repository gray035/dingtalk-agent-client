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

    # For REST API (HTTP)
    DINGTALK_BASE_URL = "https://api.dingtalk.com/"
    DINGTALK_CORP_ID = os.getenv("DINGTALK_CORP_ID", "")
    DINGTALK_CLIENT_ID = os.getenv("DINGTALK_CLIENT_ID", "")
    DINGTALK_CLIENT_SECRET = os.getenv("DINGTALK_CLIENT_SECRET", "")
    DINGTALK_WEBHOOK_TOKEN = os.getenv("DINGTALK_WEBHOOK_TOKEN", "")

    # Function trigger and bot settings
    FUNCTION_TRIGGER_FLAG = os.getenv("FUNCTION_TRIGGER_FLAG", "/run")


    # LLM API configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL", "qwen-plus")

settings = Settings()