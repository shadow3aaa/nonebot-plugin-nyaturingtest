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

    def __init__(self, memory_limit: int = 30, length_limit: int = 20):
        """
        初始化记忆
        参数

        - memory_limit: 记忆时间限制，单位分钟(默认30分钟)
        """
        self.__memory_limit = memory_limit
        """
        记忆时间限制，单位分钟(默认30分钟)
        """
        self.__length_limit = length_limit
        """
        记忆长度限制，单位条数(默认20条)
        """
        self.__messages: list[Message] = []
        """
        记忆消息列表
        """

    def access(self):
        """
        访问记忆
        """
        now = datetime.now()
        # 清除过期的记忆
        self.__messages = [
            msg for msg in self.__messages if (now - msg.time).total_seconds() / 60 < self.__memory_limit
        ]
        self.__messages = self.__messages[-self.__length_limit :]
        return self.__messages

    def update(self, message_chunk: list[Message]):
        """
        更新记忆
        参数

        - message_chunk: 消息块
        """
        now = datetime.now()
        # 清除过期的记忆
        self.__messages = [
            msg for msg in self.__messages if (now - msg.time).total_seconds() / 60 < self.__memory_limit
        ]
        # 添加新消息
        self.__messages.extend(message_chunk)
