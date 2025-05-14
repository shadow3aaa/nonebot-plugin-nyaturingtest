from collections import deque
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
    """
    短时记忆
    """

    def __init__(
        self,
        llm_client: LLMClient,
        compressed_message: str | None = None,
        messages: list[Message] | None = None,
        length_limit: int = 10,
    ):
        """
        初始化记忆
        参数

        - length_limit: 记忆消息长度限制
        """
        self.__length_limit = length_limit

        if compressed_message:
            self.__compressed_message = compressed_message
            """
            压缩后的旧消息
            """
        else:
            self.__compressed_message = ""

        if messages:
            self.__messages = deque(messages, maxlen=length_limit * 5)  # 有4/5空间不可直接访问，用于放置待压缩消息
            """
            记忆消息列表
            """
        else:
            self.__messages: deque[Message] = deque(
                maxlen=length_limit * 5
            )  # 有4/5空间不可直接访问，用于放置待压缩消息

        self.__llm_client = llm_client
        """
        用于压缩消息的 LLM 客户端
        """

    def related_users(self) -> list[str]:
        """
        获取相关用户列表
        """
        return list({message.user_name for message in self.__messages})

    def compress_message(self):
        """
        压缩历史消息
        """
        history_messages = [f"{message.user_name}: {message.content}" for message in self.__messages][
            : self.__length_limit
        ]
        prompt = f"""
请将以下消息分参与的话题压缩，保留

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
            response = self.__llm_client.generate_response(prompt, model="Qwen/Qwen3-8B")
            if response:
                self.__compressed_message = response
                logger.info(f"压缩消息成功: {response}")
            else:
                logger.warning("压缩消息失败，原因未知")
        except Exception as e:
            logger.error(f"压缩消息时发生错误: {e}")

    def clear(self) -> None:
        """
        清除所有记忆
        """
        self.__messages.clear()
        self.__compressed_message = ""
        logger.info("已清除所有记忆")

    def access(self) -> MemoryRecord:
        """
        访问记忆
        """
        return MemoryRecord(
            messages=list(self.__messages)[-self.__length_limit :],  # 只允许访问后面部分消息
            compressed_history=self.__compressed_message,
        )

    def update(self, message_chunk: list[Message]):
        """
        更新记忆
        参数

        - message_chunk: 消息块
        """
        self.__messages.extend(message_chunk)
