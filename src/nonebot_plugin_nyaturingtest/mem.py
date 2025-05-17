import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from nonebot import logger

from .client import LLMClient


@dataclass
class Message:
    time: datetime
    """
    消息时间
    """
    user_name: str
    """
    消息发送者名称
    """
    content: str
    """
    消息内容
    """

    def to_json(self) -> dict:
        """
        转换为 JSON 格式
        """
        return {
            "time": self.time.isoformat(),
            "user_name": self.user_name,
            "content": self.content,
        }

    @staticmethod
    def from_json(data: dict) -> "Message":
        """
        从 JSON 格式转换为 Message 对象
        """
        return Message(
            time=datetime.fromisoformat(data["time"]),
            user_name=data["user_name"],
            content=data["content"],
        )


@dataclass
class MemoryRecord:
    messages: list[Message]
    """
    消息记录
    """
    compressed_history: str
    """
    压缩后的历史消息
    """


class Memory:
    def __init__(
        self,
        llm_client: LLMClient,
        compressed_message: str | None = None,
        messages: list[Message] | None = None,
        length_limit: int = 10,
    ):
        self.__length_limit = length_limit
        self.__compressed_message = compressed_message or ""
        self.__messages = deque(messages, maxlen=length_limit * 5) if messages else deque(maxlen=length_limit * 5)
        self.__llm_client = llm_client
        self.__compress_counter = 0
        self.__compress_task: asyncio.Task | None = None  # 压缩任务句柄

    def related_users(self) -> list[str]:
        """
        获取相关用户列表
        """
        return list({message.user_name for message in self.__messages})

    async def clear(self) -> None:
        """
        清除所有记忆
        """
        self.__messages.clear()
        self.__compressed_message = ""
        self.__compress_counter = 0
        await self.__cancel_compress_task()
        logger.info("已清除所有记忆")

    async def __compress_message(self, after_compress: Callable[[], None] | None = None):
        history_messages = [f"{msg.user_name}: {msg.content}" for msg in self.__messages]
        prompt = f"""
请将以下消息分参与的话题压缩，提取

- 话题简要内容
- 参与者和它们的发言总结

格式类似:

[话题: 话题简要内容]
参与者:
- a: a发言总结

以下是消息列表，按时间排序从老到新：

{history_messages}
"""
        try:
            response = await self.__llm_client.generate_response(prompt, model="Qwen/Qwen3-8B")
            if after_compress:
                after_compress()
            if response:
                self.__compressed_message = response
                logger.info(f"压缩消息成功: {response}")
            else:
                logger.warning("压缩消息失败，原因未知")
        except asyncio.CancelledError:
            logger.info("压缩任务被取消")
            raise
        except Exception as e:
            logger.error(f"压缩消息时发生错误: {e}")

    def access(self) -> MemoryRecord:
        """
        访问记忆
        """
        return MemoryRecord(
            messages=list(self.__messages)[-self.__length_limit :],  # 只允许访问后面部分消息
            compressed_history=self.__compressed_message,
        )

    async def __cancel_compress_task(self):
        """
        取消压缩任务
        """
        if self.__compress_task and not self.__compress_task.done():
            self.__compress_task.cancel()
            try:
                await self.__compress_task
            except asyncio.CancelledError:
                pass

    async def update(self, message_chunk: list[Message], after_compress: Callable[[], None] | None = None):
        self.__messages.extend(message_chunk)

        # 每self.__length_limit条消息压缩一次
        self.__compress_counter += len(message_chunk)
        if self.__compress_counter < self.__length_limit:
            return
        self.__compress_counter = 0

        # 如果有正在执行的压缩任务，先取消它
        await self.__cancel_compress_task()

        # 开启新的压缩任务
        self.__compress_task = asyncio.create_task(self.__compress_message(after_compress=after_compress))
