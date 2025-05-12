from collections import deque
from dataclasses import dataclass
from datetime import datetime


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


class Memory:
    """
    短时记忆
    """

    def __init__(self, length_limit: int = 20):
        """
        初始化记忆
        参数

        - length_limit: 记忆消息长度限制
        """
        self.__messages: deque[Message] = deque(maxlen=length_limit)
        """
        记忆消息列表
        """

    def access(self) -> list[Message]:
        """
        访问记忆
        """
        return list(self.__messages)

    def update(self, message_chunk: list[Message]):
        """
        更新记忆
        参数

        - message_chunk: 消息块
        """
        self.__messages.extend(message_chunk)
