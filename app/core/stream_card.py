from loguru import logger
from dataclasses import dataclass
import json
from enum import IntEnum
from threading import Lock

from app.service.reply_service import reply_service, ContentType, CardData


class StepStatus(IntEnum):
    """
    步骤状态枚举
    """

    ERROR = 0
    """
    出错，图标会是一个❌
    """
    SUCCESS = 1
    """
    成功，图标会一个✅
    """
    EXECUTING = 2
    """
    正在处理中，图标会一个loading转圈
    """
    INITIAL = 3
    """
    初始状态
    """


@dataclass
class _PlanStep:
    taskId: str
    status: int
    content: str
    output: str
    expand: bool


class StreamCard:
    def __init__(
        self,
        token: str,
    ) -> None:
        """Construct a new stream card instance.

        创建一个AI助理的流式卡片对象，用于处理AI的流式输出。:
        - `token`  AI助理回调的会话token
        """
        self.__conversation_token = token
        self.__template_id = "4b6e421f-5300-4ba4-bb0b-0fcea69051f0.schema"
        self.__stream_data = ""
        self.__title = ""
        self.__buffer_size = 0
        self.__cached_size = 0

        self.__steps_name_list = []
        self.__steps_map = {}

        self.__lock = Lock()

        self.__initialized = False
        self.__stream_changed = False

    @classmethod
    async def create(cls, token: str) -> "StreamCard":
        """
        工厂方法：创建一个新的 StreamCard 实例
        :param token: 会话 token
        :return: StreamCard 实例
        """
        card_instance = cls(token)
        await card_instance.__initial()
        return card_instance

    async def update_title(self, title: str):
        """
        更新卡片的title
         - `title` 卡片title
        """
        await self.__empty_stream()
        self.__title = title
        card_data = {"title": title, "config": {"autoLayout": True}}
        await reply_service.update_card(
            conversation_token=self.__conversation_token,
            card_data=CardData(
                card_data=card_data,
                template_id=self.__template_id,
                options={"componentTag": "staticComponent"},
            ),
        )

    async def update_once(self, full_content: str):
        """
        全量更新卡片流式内容，流式字段会被full_content覆盖更新
         - `full_content` 全量卡片内容
        """
        self.__stream_changed = True
        self.__lock.acquire()
        self.__stream_data = full_content
        self.__lock.release()
        card_data = CardData(
            card_data={
                "key": "result",  # 流式更新，只更新result字段
                "value": self.__stream_data,
                "isFinalize": True,  # 因为是全量更新，会结束卡片流式状态
            },
            options={"componentTag": "streamingComponent"},
            template_id=self.__template_id,
        )

        await reply_service.update_card(
            conversation_token=self.__conversation_token,
            card_data=card_data,
        )

    async def update_delta(self, delta_content: str, flush: bool = False):
        """
        增量更新卡片流式内容
         - `delta_content` 增量卡片内容
         - `flush` 是否立即刷新，如果设置了buffer_size，又希望更新立即刷新，请设置此参数
        """
        self.__stream_changed = True
        self.__lock.acquire()
        delta_size = len(delta_content)
        self.__stream_data += delta_content
        self.__cached_size += delta_size
        self.__lock.release()

        if not flush and self.__cached_size < self.__buffer_size:
            return
        self.__cached_size = 0
        card_data = CardData(
            card_data={
                "key": "result",  # 流式更新，只更新result字段
                "value": self.__stream_data,
                "isFinalize": False,  # 流式输出中，不能设置为True
            },
            options={"componentTag": "streamingComponent"},
            template_id=self.__template_id,
        )

        await reply_service.update_card(
            conversation_token=self.__conversation_token,
            card_data=card_data,
        )

    async def finish(self):
        """
        结束卡片流式输出
        """
        self.__stream_changed = True
        card_data = CardData(
            card_data={
                "key": "result",  # 流式更新，只更新result字段
                "value": self.__stream_data,
                "isFinalize": True,  # 流式输出中，不能设置为True
            },
            options={"componentTag": "streamingComponent"},
            template_id=self.__template_id,
        )

        await reply_service.update_card(
            conversation_token=self.__conversation_token,
            card_data=card_data,
        )

    async def create_plan_step(
        self,
        step_name: str,
        step_status: StepStatus,
        step_desc: str,
        step_detail: str = "",
    ):
        """
        创建Plan，如果Plan已经存在，则抛出异常
         - `step_name` 步骤名称
         - `step_status` 步骤状态
         - `step_desc` 步骤描述
         - `step_detail` 步骤详情
        """
        await self.__empty_stream()
        if step_name in self.__steps_map:
            raise ValueError("step already exists")
        expand = True
        step = _PlanStep(step_name, step_status, step_desc, step_detail, expand)
        self.__steps_name_list.append(step_name)
        self.__steps_map[step_name] = step
        steps = []
        for name in self.__steps_name_list:
            steps.append(self.__steps_map[name])
        steps_str = json.dumps(steps, default=lambda k: k.__dict__)
        card_data = {
            "planList": json.loads(steps_str),
        }
        await reply_service.reply(
            self.__conversation_token,
            None,
            content_type=ContentType.AI_CARD,
            card_data=CardData(
                card_data=card_data,
                template_id=self.__template_id,
                options={"componentTag": "staticComponent"},
            ),
        )

    async def update_plan_step(
        self,
        step_name: str,
        step_status: StepStatus,
        step_desc: str,
        step_detail: str,
    ):
        """
        更新Plan步骤，如果Plan不存在，会创建Plan
         - `step_name` 步骤名称
         - `step_status` 步骤状态
         - `step_desc` 步骤描述
         - `step_detail` 步骤详情
        """
        await self.__empty_stream()
        if step_name not in self.__steps_map:
            self.__steps_name_list.append(step_name)

        expand = True
        step = _PlanStep(step_name, step_status, step_desc, step_detail, expand)
        self.__steps_map[step_name] = step
        steps = []
        for name in self.__steps_name_list:
            steps.append(self.__steps_map[name])
        steps_str = json.dumps(steps, default=lambda k: k.__dict__)
        card_data = {
            "planList": json.loads(steps_str),
        }
        await reply_service.reply(
            self.__conversation_token,
            None,
            content_type=ContentType.AI_CARD,
            card_data=CardData(
                card_data=card_data,
                template_id=self.__template_id,
                options={"componentTag": "staticComponent"},
            ),
        )

    def update_buffer_size(self, buffer_size: int):
        """
        设置流式输出缓存大小，默认为0，即本地不缓存，每调用一次update_delta，都会调用一次钉钉开放平台API
         - `buffer_size` 缓存大小
        """
        self.__buffer_size = buffer_size

    async def __initial(self):
        if self.__initialized:
            return
        self.__initialized = True
        card_data = {"config": {"autoLayout": True}}
        if self.__title:
            card_data["title"] = self.__title

        await reply_service.reply(
            self.__conversation_token,
            None,
            content_type=ContentType.AI_CARD,
            card_data=CardData(
                card_data=card_data,
                template_id=self.__template_id,
                options={"componentTag": "staticComponent"},
            ),
        )

    async def __empty_stream(self):
        """
        用于输入一个空的streamcontent，否则其他静态区域在没有流式变更时，不会显示
        """
        if self.__stream_changed:
            return
        self.__stream_changed = True
        card_data = CardData(
            card_data={
                "key": "result",  # 流式更新，只更新result字段
                "value": "~",
                "isFinalize": False,  # 流式输出中，不能设置为True
            },
            options={"componentTag": "streamingComponent"},
            template_id=self.__template_id,
        )

        await reply_service.update_card(
            conversation_token=self.__conversation_token,
            card_data=card_data,
        )


##############################################  测试例子  ##############################################


async def __test_genereate_result(contents):
    for index, item in enumerate(contents):
        await asyncio.sleep(0.1)
        yield item


async def __test_simple(token: str):
    card = await StreamCard.create(token)
    POETRY = [
        "## 沁园春·雪  \n\n  ",
        "**北国风光，千里冰封，万里雪飘。**  \n\n  ",
        "**望长城内外，惟余莽莽；大河上下，顿失滔滔。**  \n\n  ",
        "**山舞银蛇，原驰蜡象，欲与天公试比高。**  \n\n  ",
        "**须晴日，看红装素裹，分外妖娆。**  \n\n  ",
        "**江山如此多娇，引无数英雄竞折腰。**  \n\n  ",
        "**惜秦皇汉武，略输文采；**  \n\n  ",
        "**唐宗宋祖，稍逊风骚。**  \n\n  ",
        "**一代天骄，成吉思汗，只识弯弓射大雕。**  \n\n  ",
        "**俱往矣，数风流人物，还看今朝。**  \n\n  ",
    ]
    async for delta_data in __test_genereate_result(POETRY):
        if delta_data is None:
            continue
        await card.update_delta(delta_data)

    await card.finish()


async def __test_full_update(token: str):
    card = await StreamCard.create(token)
    await card.update_title("正在处理您的请求...")
    POETRY = [
        "## 沁园春·雪  \n\n  ",
        "**北国风光，千里冰封，万里雪飘。**  \n\n  ",
        "**望长城内外，惟余莽莽；大河上下，顿失滔滔。**  \n\n  ",
        "**山舞银蛇，原驰蜡象，欲与天公试比高。**  \n\n  ",
        "**须晴日，看红装素裹，分外妖娆。**  \n\n  ",
        "**江山如此多娇，引无数英雄竞折腰。**  \n\n  ",
        "**惜秦皇汉武，略输文采；**  \n\n  ",
        "**唐宗宋祖，稍逊风骚。**  \n\n  ",
        "**一代天骄，成吉思汗，只识弯弓射大雕。**  \n\n  ",
        "**俱往矣，数风流人物，还看今朝。**  \n\n  ",
    ]
    full_content = ""
    for poetry in POETRY:
        full_content += poetry
    await card.update_once(full_content)


async def __test_stream_update(token: str):
    card = await StreamCard.create(token)
    await card.update_title("正在处理您的请求...")
    POETRY = [
        "## 沁园春·雪  \n\n  ",
        "**北国风光，千里冰封，万里雪飘。**  \n\n  ",
        "**望长城内外，惟余莽莽；大河上下，顿失滔滔。**  \n\n  ",
        "**山舞银蛇，原驰蜡象，欲与天公试比高。**  \n\n  ",
        "**须晴日，看红装素裹，分外妖娆。**  \n\n  ",
        "**江山如此多娇，引无数英雄竞折腰。**  \n\n  ",
        "**惜秦皇汉武，略输文采；**  \n\n  ",
        "**唐宗宋祖，稍逊风骚。**  \n\n  ",
        "**一代天骄，成吉思汗，只识弯弓射大雕。**  \n\n  ",
        "**俱往矣，数风流人物，还看今朝。**  \n\n  ",
    ]
    async for delta_data in __test_genereate_result(POETRY):
        if delta_data is None:
            continue
        await card.update_delta(delta_data)
    await card.update_title("您的请求处理完成")
    await card.finish()


async def __test_plan_update(token: str):
    card = await StreamCard.create(token)
    await card.update_title("正在处理您的请求...")
    await card.create_plan_step("task1", StepStatus.EXECUTING, "执行任务1")
    await asyncio.sleep(2)
    await card.update_plan_step(
        "task1", StepStatus.SUCCESS, "执行任务1", "**任务1执行成功**"
    )

    await card.create_plan_step("task2", StepStatus.EXECUTING, "执行任务2")
    await asyncio.sleep(2)
    await card.update_plan_step(
        "task2",
        StepStatus.ERROR,
        "执行任务2",
        "**任务1执行失败**  \n\n 可能原因:   \n\n  - 缺少权限  \n\n  - 数据库连接失败\n\n",
    )
    POETRY = [
        "## 沁园春·雪  \n\n  ",
        "**北国风光，千里冰封，万里雪飘。**  \n\n  ",
        "**望长城内外，惟余莽莽；大河上下，顿失滔滔。**  \n\n  ",
        "**山舞银蛇，原驰蜡象，欲与天公试比高。**  \n\n  ",
        "**须晴日，看红装素裹，分外妖娆。**  \n\n  ",
        "**江山如此多娇，引无数英雄竞折腰。**  \n\n  ",
        "**惜秦皇汉武，略输文采；**  \n\n  ",
        "**唐宗宋祖，稍逊风骚。**  \n\n  ",
        "**一代天骄，成吉思汗，只识弯弓射大雕。**  \n\n  ",
        "**俱往矣，数风流人物，还看今朝。**  \n\n  ",
    ]
    async for delta_data in __test_genereate_result(POETRY):
        if delta_data is None:
            continue
        await card.update_delta(delta_data)
    await card.finish()


async def __test_async_main(token: str):
    await __test_simple(token)
    await __test_full_update(token)
    await __test_stream_update(token)
    await __test_plan_update(token)


if __name__ == "__main__":
    import asyncio

    token = ""
    asyncio.run(__test_async_main(token))
