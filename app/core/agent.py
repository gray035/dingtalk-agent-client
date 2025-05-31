from abc import ABC, abstractmethod
from app.service.message_context import MessageContext


class HandleResult:
    def __init__(self, result_code: int, result_message: str, result: str):
        self.result_code = result_code
        self.result_message = result_message
        self.result = result


class SuccessHandleResult(HandleResult):
    def __init__(self, result: str):
        super().__init__(200, "OK", result)


class BadRequestHandleResult(HandleResult):
    def __init__(self, result_message: str):
        super().__init__(400, result_message, "")


class InternalErrorHandleResult(HandleResult):
    def __init__(self, result_message: str):
        super().__init__(500, result_message, "")


class BaseAgent(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    async def handle_message(self, context: MessageContext) -> HandleResult:
        """处理消息的抽象方法"""
        pass

    async def before_handle(self, context: MessageContext):
        """消息处理前的钩子"""
        pass

    async def after_handle(self, context: MessageContext, response: str):
        """消息处理后的钩子"""
        pass
