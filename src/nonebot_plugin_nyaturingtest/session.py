from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import os
import pickle
import random
import re
import traceback

from nonebot import logger
from openai import OpenAI

from .client import LLMClient
from .config import plugin_config
from .emotion import EmotionState
from .hippo_mem import HippoMemory
from .impression import Impression
from .mem import Memory, Message
from .presets import PRESETS
from .profile import PersonProfile


@dataclass
class _SearchResult:
    """
    检索阶段的结果
    """

    mem_history: list[str]
    """
    记忆记录
    """


class _ChattingState(Enum):
    ILDE = 0
    """
    潜水状态
    """
    BUBBLE = 1
    """
    冒泡状态
    """
    ACTIVE = 2
    """
    对话状态
    """

    def __str__(self):
        match self:
            case _ChattingState.ILDE:
                return "潜水状态"
            case _ChattingState.BUBBLE:
                return "冒泡状态"
            case _ChattingState.ACTIVE:
                return "对话状态"


class Session:
    """
    群聊会话
    """

    def __init__(self, siliconflow_api_key: str, id: str = "global", name: str = "terminus"):
        self.id = id
        """
        会话ID，用于持久化时的标识
        """
        self.global_memory: Memory = Memory(
            llm_client=LLMClient(
                client=OpenAI(
                    api_key=plugin_config.nyaturingtest_siliconflow_api_key,
                    base_url="https://api.siliconflow.cn/v1",
                )
            )
        )
        """
        全局短时记忆
        """
        self.long_term_memory: HippoMemory = HippoMemory(
            llm_model=plugin_config.nyaturingtest_chat_openai_model,
            llm_api_key=plugin_config.nyaturingtest_chat_openai_api_key,
            llm_base_url=plugin_config.nyaturingtest_chat_openai_base_url,
            embedding_api_key=siliconflow_api_key,
            persist_directory=f"./hippo_index_{id}",
        )
        """
        对聊天记录的长期记忆 (基于HippoRAG)
        """
        self.__name = name
        """
        我的名称
        """
        self.profiles: dict[str, PersonProfile] = {}
        """
        人物记忆
        """
        self.global_emotion: EmotionState = EmotionState()
        """
        全局情感状态
        """
        self.last_response: list[Message] = []
        """
        上次回复
        """
        self.chat_summary = ""
        """
        对话总结
        """
        self.__role = "一个男性人类"
        """
        我的角色
        """
        self.__chatting_state = _ChattingState.ILDE
        """
        对话状态
        """
        self.__bubble_willing_sum = 0.0
        """
        冒泡意愿总和（冒泡意愿会累积）
        """

        # 从文件加载会话状态（如果存在）
        self.load_session()

    def set_role(self, name: str, role: str):
        """
        设置角色
        """
        self.reset()
        self.__role = role
        self.__name = name
        self.save_session()  # 保存角色设置变更

    def role(self) -> str:
        """
        获取角色
        """
        return f"{self.__name}（{self.__role}）"

    def name(self) -> str:
        """
        获取名称
        """
        return self.__name

    def reset(self):
        """
        重置会话
        """
        self.__name = "terminus"
        self.__role = "一个男性人类"
        self.global_memory.clear()
        self.long_term_memory.clear()
        self.profiles = {}
        self.global_emotion = EmotionState()
        self.last_response = []
        self.chat_summary = ""
        self.save_session()  # 保存重置后的状态

    def calm_down(self):
        """
        冷静下来
        """
        self.global_emotion.valence = 0.0
        self.global_emotion.arousal = 0.0
        self.global_emotion.dominance = 0.0
        self.profiles = {}
        self.save_session()  # 保存冷静后的状态

    def get_session_file_path(self) -> str:
        """
        获取会话文件路径
        """
        # 确保会话目录存在
        os.makedirs("yaturningtest_sessions", exist_ok=True)
        return f"yaturningtest_sessions/session_{self.id}.json"

    def save_session(self):
        """
        保存会话状态到文件
        """
        try:
            # 准备要保存的数据
            session_data = {
                "id": self.id,
                "name": self.__name,
                "role": self.__role,
                "global_memory": {
                    "compressed_history": self.global_memory.access().compressed_history,
                    "messages": [msg.to_json() for msg in self.global_memory.access().messages],
                },
                "global_emotion": {
                    "valence": self.global_emotion.valence,
                    "arousal": self.global_emotion.arousal,
                    "dominance": self.global_emotion.dominance,
                },
                "chat_summary": self.chat_summary,
                "profiles": {
                    user_id: {
                        "user_id": profile.user_id,
                        "emotion": {
                            "valence": profile.emotion.valence,
                            "arousal": profile.emotion.arousal,
                            "dominance": profile.emotion.dominance,
                        },
                        # interactions 是一个 deque，直接序列化
                        "interactions": pickle.dumps(profile.interactions).hex(),
                    }
                    for user_id, profile in self.profiles.items()
                },
                "last_response": [
                    {"time": msg.time.isoformat(), "user_name": msg.user_name, "content": msg.content}
                    for msg in self.last_response
                ],
                "chatting_state": self.__chatting_state.value,
            }

            # 写入文件
            with open(self.get_session_file_path(), "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"[Session {self.id}] 会话状态已保存")
        except Exception as e:
            logger.debug(f"[Session {self.id}] 保存会话状态失败: {e}")

    def load_session(self):
        """
        从文件加载会话状态
        """
        file_path = self.get_session_file_path()
        if not os.path.exists(file_path):
            logger.debug(f"[Session {self.id}] 会话文件不存在，使用默认状态")
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                session_data = json.load(f)

            # 恢复会话状态
            self.__name = session_data.get("name", self.__name)
            self.__role = session_data.get("role", self.__role)

            # 恢复全局情绪状态
            emotion_data = session_data.get("global_emotion", {})
            self.global_emotion.valence = emotion_data.get("valence", 0.0)
            self.global_emotion.arousal = emotion_data.get("arousal", 0.0)
            self.global_emotion.dominance = emotion_data.get("dominance", 0.0)

            # 恢复全局短时记忆
            if "global_memory" in session_data:
                try:
                    self.global_memory = Memory(
                        compressed_message=session_data["global_memory"].get("compressed_history", ""),
                        messages=[Message.from_json(msg) for msg in session_data["global_memory"].get("messages", [])],
                        llm_client=LLMClient(
                            client=OpenAI(
                                api_key=plugin_config.nyaturingtest_siliconflow_api_key,
                                base_url="https://api.siliconflow.cn/v1",
                            )
                        ),
                    )
                except Exception as e:
                    logger.error(f"[Session {self.id}] 恢复全局短时记忆失败: {e}")
                    self.global_memory = Memory(
                        llm_client=LLMClient(
                            client=OpenAI(
                                api_key=plugin_config.nyaturingtest_siliconflow_api_key,
                                base_url="https://api.siliconflow.cn/v1",
                            )
                        )
                    )

            # 恢复聊天总结
            self.chat_summary = str(session_data.get("chat_summary", ""))

            # 恢复用户档案
            self.profiles = {}
            for user_id, profile_data in session_data.get("profiles", {}).items():
                profile = PersonProfile(user_id=profile_data.get("user_id", user_id))

                # 设置情绪
                emotion_data = profile_data.get("emotion", {})
                profile.emotion.valence = emotion_data.get("valence", 0.0)
                profile.emotion.arousal = emotion_data.get("arousal", 0.0)
                profile.emotion.dominance = emotion_data.get("dominance", 0.0)

                # 恢复交互记录
                if "interactions" in profile_data:
                    try:
                        profile.interactions = pickle.loads(bytes.fromhex(profile_data["interactions"]))
                        if not isinstance(profile.interactions, deque):
                            profile.interactions = deque(profile.interactions)
                    except Exception as e:
                        logger.error(f"[Session {self.id}] 恢复用户 {user_id} 交互记录失败: {e}")

                self.profiles[user_id] = profile

            # 恢复最后一次回复
            self.last_response = []
            for msg_data in session_data.get("last_response", []):
                try:
                    time = datetime.fromisoformat(msg_data.get("time"))
                except ValueError:
                    time = datetime.now()

                self.last_response.append(
                    Message(time=time, user_name=msg_data.get("user_name", ""), content=msg_data.get("content", ""))
                )

            # 恢复对话状态
            self.__chatting_state = _ChattingState(session_data.get("chatting_state", _ChattingState.ILDE.value))

            logger.info(f"[Session {self.id}] 会话状态已加载")
        except Exception as e:
            logger.error(f"[Session {self.id}] 加载会话状态失败: {e}")
            # 加载失败时使用默认状态，不需要额外操作

    def presets(self) -> list[str]:
        """
        获取可选预设
        """
        return [f"{filename}: {preset.name} {preset.role}" for filename, preset in PRESETS.items() if not preset.hidden]

    def load_preset(self, filename: str) -> bool:
        """
        加载预设
        """
        if filename not in PRESETS.keys():
            logger.error(f"不存在的预设：{filename}")
            return False
        preset = PRESETS[filename]
        self.reset()
        self.set_role(preset.name, preset.role)
        self.long_term_memory.add_texts(preset.knowledges)
        self.long_term_memory.add_texts(preset.relationships)
        self.long_term_memory.add_texts(preset.events)
        self.long_term_memory.add_texts(preset.bot_self)
        self.long_term_memory.index()
        logger.info(f"加载预设：{filename} 成功")
        return True

    def status(self) -> str:
        """
        获取机器人状态
        """

        recent_messages = self.global_memory.access().messages
        recent_messages_str = (
            "\n".join([f"{msg.user_name}: {msg.content}" for msg in recent_messages]) if recent_messages else "没有消息"
        )

        return f"""
名字：
{self.__name}

设定：
{self.__role}

情感状态：
愉悦度：{self.global_emotion.valence}
唤醒度：{self.global_emotion.arousal}
支配度：{self.global_emotion.dominance}

最近的消息：
{recent_messages_str}

对过去的总结：
{self.global_memory.access().compressed_history}

对现状的认识：{self.chat_summary}
"""

    # 我们将对话分为三个阶段：
    # 1. 检索阶段：在这个阶段，从hipporag中搜索聊天记录相关信息
    # 2. 反馈阶段：在这个阶段，llm从检索阶段得到相关信息，然后llm结合当前的对话进行反馈分析，得出场景总结和情感反馈，并
    #    进行长期记忆更新，评估自身要不要加入对话
    # 3. 对话阶段：在这个阶段，llm从内存，检索阶段，反馈阶段中得到相关信息，以发送信息

    def __search_stage(self, messages_chunk: list[Message]) -> _SearchResult:
        """
        检索阶段
        """
        logger.debug("检索阶段开始")
        # 搜索 全部新消息 + 短期聊天记录 + 历史总结 + 环境总结
        retrieve_messages = (
            [f"'{msg.user_name}':'{msg.content}'" for msg in self.global_memory.access().messages]
            + [self.global_memory.access().compressed_history]
            + [msg.content for msg in messages_chunk]
            + [self.chat_summary]
        )
        try:
            long_term_memory = self.long_term_memory.retrieve(retrieve_messages, k=3)
            logger.debug(f"搜索到的相关记忆：{long_term_memory}")
        except Exception as e:
            logger.error(f"回忆失败: {e}")
            traceback.print_exc()
            long_term_memory = []

        logger.debug("检索阶段结束")

        return _SearchResult(
            mem_history=long_term_memory,
        )

    def __feedback_stage(
        self, messages_chunk: list[Message], search_stage_result: _SearchResult, llm: Callable[[str], str]
    ):
        """
        反馈总结阶段
        """
        logger.debug("反馈阶段开始")
        reaction_users = self.global_memory.related_users()
        related_profiles = [profile for profile in self.profiles.values() if profile.user_id in reaction_users]
        related_profiles_json = json.dumps(
            [
                {
                    "user_name": profile.user_id,
                    "emotion_tends_to_user": profile.emotion.__dict__,
                }
                for profile in related_profiles
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = f"""
你是QQ群用户 {self.__name}，不是 AI，而是一个有自我认知的真实用户，（你称自己为 "{self.__name}"），你的人设(身份认知)如
下:

{self.__role}

现在你正在回顾聊天信息，以客观视角分析“你的最新情绪”，整理信息保存，并对聊天内容做出总结，最后评估自己要不要加入对话

---

## 1. 任务目标
- 基于“新输入消息”的内容和“历史聊天”的背景，结合你之前的情绪，还有检索到的相关记忆，评估你当前的情绪
  - 情绪采用 VAD 模型，三个维度取值范围：
    - valence (愉悦度)：[-1.0, 1.0]
    - arousal (唤醒度)：[0.0, 1.0]
    - dominance (支配度)：[-1.0, 1.0]
- 基于“新输入消息”的内容和“历史聊天”的背景，结合你之前的情绪，你对相关人物的情绪倾向，还有检索到的相关记忆，评估你对“新
  输入消息”中**每条**消息的情感倾向
  - 如果消息和你完全无关，或你不感兴趣，那么给出的每个情感维度的值总是 0.0
  - 输出按照“新输入消息”的顺序
- 基于“历史聊天”的背景，“你在上次对话做出的总结”，还有检索到的相关记忆，用简短的语言总结聊天内容，总结注重于和上次对话的
  连续性，包括相关人物，简要内容。
  - 特别的，如果“历史聊天”，检索到的信息中不包含“你在上次对话做出的总结”的人物，那么在这次总结就不保留
  - 注意：要满足连续性需求，不能简单的只总结“新输入消息”的内容，还要结合上次总结和“历史聊天”的内容，并且不能因为这次的消
    息没有上次总结的内容的人物就不保留上次总结的内容，只有“历史聊天”，检索到的信息中不包含“你在上次对话做出的总结”的人物时，才
    不保留上次总结的内容
  - 例子A(断裂重启型):
    “你在上次对话做出的总结”
    小明，小红：讨论 AI 的道德问题。

    “新输入消息”
    小明：“我们来玩猜谜游戏吧！”
    小红：“好啊，我来第一个出题！”

    “总结”
    小明，小红：讨论的话题发生了明显转变，由 AI 的道德问题转变到了玩猜谜游戏。
  - 例子B(主题转移型):
    “你在上次对话做出的总结”
    小明，小红：讨论 AI 的道德问题。

    “新输入消息”
    小明：“我觉得 AI 应该有道德标准。”
    小红：“我同意！但是我们应该如何定义这些标准呢？”

    “总结”
    小明，小红：讨论 AI 的道德问题，继续深入探讨如何定义道德标准。

  - 例子C(无意义话题型):
    “你在上次对话做出的总结”
    小明，小红：讨论 AI 的道德问题。

    “新输入消息”
    小明：“awhnofbonog”
    小红：“2388y91ry9h”

    “总结”
    小明，小红：之前在讨论 AI 的道德问题。

  - 例子D(话题回归型):
    “你在上次对话做出的总结”
    小明，小红：讨论的话题发生了明显转变，由 AI 的道德问题转变到了玩猜谜游戏。

    “新输入消息”
    小明：“但是我还是想讨论 AI 是否需要道德”
    小红：“我觉得 AI 应该有道德标准。”

    “总结”
    小明，小红：讨论的话题由玩猜谜游戏回归到 AI 的道德问题。

  - 例子E(混合型):
    “你在上次对话做出的总结”
    小明，小红：讨论 AI 的道德问题。

    “新输入消息”
    小亮：“我们来玩猜谜游戏吧！”
    小明：“我觉得 AI 应该有道德标准。”
    小圆：“@小亮 好呀”
    小红：“我同意！但是我们应该如何定义这些标准呢？”

    “总结”
    小明，小红：讨论 AI 的道德问题，继续深入探讨如何定义道德标准。
    小亮，小圆：讨论玩猜谜游戏。

- 基于“新输入消息”的内容和“历史聊天”的背景，结合检索到的相关记忆进行分析，整理信息保存，要整理的信息和要求如下
  ## 要求：
  - 不能重复，即不能和下面提供的检索到的相关记忆已有内容重复
  ## 要整理的信息：
  - 无论信息是什么类别，都放到`analyze_result`字段
  - 事件类：
    - 如果包含事件类信息，则保存为事件信息，内容是对事件进行简要叙述
  - 资料类：
    - 如果包含资料类信息，则保存为知识信息，内容为资料的关键内容（如果很短也可以全文保存）及其可信度[0%-100%]，如：“ipho
    ne是由apple发布的智能手机系列产品，可信度99%”
  - 人物关系类
    - 如果包含人物关系类信息，则保存为人物关系信息，内容是对人物关系进行简要叙述（如：小明 是 小红 的 朋友）
  - 自我认知类
    - 如果你对自己有新的认知，则保存为自我认知信息，自我认知信息需要经过慎重考虑，主要参照你自己发送的消息，次要参照别人
      发送的消息，内容是对自我的认知（如：我喜欢吃苹果、我身上有纹身）

- 评估你改变对话状态的意愿，规则如下：
  - 意愿范围是[0.0, 1.0]
  - 对话状态分为三种：
    - 0：潜水状态
    - 1：冒泡状态
    - 2：对话状态
  - 如果你在状态0，那么分别评估你转换到状态1，2的意愿，其它意愿设0.0为默认值即可
  - 如果你在状态1，那么分别评估你转换到状态0，2的意愿，其它意愿设0.0为默认值即可
  - 如果你在状态2，那么评估你转换到状态0的意愿，其它意愿设0.0为默认值即可
  - 以下条件会影响转换到状态0的意愿：
    - 你进行这个话题的时间，太久了会让你疲劳，更容易转变到状态0
    - 是否有人回应你
    - 你是否对这个话题感兴趣
    - 你是否有足够的“检索到的相关记忆”了解
  - 以下条件会影响转换到状态1的意愿：
    - 你刚刚加入群聊（特征是“历史聊天”-“最近的聊天记录”只有0-3条消息)，提升
    - 你很久没有发言(特征是“历史聊天”-“最近的聊天记录”和“历史聊天”-“过去历史聊天总结”没有你的参与)，提升
  - 以下条件会影响转换到状态2的意愿：
    - 讨论的内容你是否有足够的“检索到的相关记忆”了解
    - 你是否对讨论的内容感兴趣
    - 你自身的情感状态
    - 你对相关人物的情感倾向

## 2. 输入信息

- 之前的对话状态

  - 状态{self.__chatting_state.value}

- 历史聊天

  - 过去历史聊天总结：

  {self.global_memory.access().compressed_history}

  - 最近的聊天记录：

    {self.global_memory.access().messages}

- 新输入消息

  {[f"{msg.user_name}: '{msg.content}'" for msg in messages_chunk]}

- 你之前的情绪

  valence: {self.global_emotion.valence}
  arousal: {self.global_emotion.arousal}
  dominance: {self.global_emotion.dominance}

- 你对相关人物的情绪倾向

  ```json
  {related_profiles_json}
  ```

- 检索到的相关记忆

  {search_stage_result.mem_history}

- 你在上次对话做出的总结

  {self.chat_summary}

---

请严格遵守以上说明，输出符合以下格式的纯 JSON（数组长度不是格式要求），不要添加任何额外的文字或解释。

```json
{{
  "emotion_tends": [
    {{
      "valence": 0.0≤float≤1.0,
      "arousal": 0.0≤float≤1.0,
      "dominance": -1.0≤float≤1.0,
    }},
    {{
      "valence": 0.0≤float≤1.0,
      "arousal": 0.0≤float≤1.0,
      "dominance": -1.0≤float≤1.0,
    }},
    {{
      "valence": 0.0≤float≤1.0,
      "arousal": 0.0≤float≤1.0,
      "dominance": -1.0≤float≤1.0,
    }}
  ]
  "new_emotion": {{
    "valence": 0.0≤float≤1.0,
    "arousal": 0.0≤float≤1.0,
    "dominance": -1.0≤float≤1.0
  }},
  "summary": "对聊天内容的总结",
  "analyze_result": ["事件类信息", "资料类信息", "人物关系类信息", "自我认知类信息"],
  "willing": {{
    0: 0.0≤float≤1.0,
    1: 0.0≤float≤1.0,
    2: 0.0≤float≤1.0
  }}
}}
```
"""
        response = llm(prompt)
        response = re.sub(r"^```json\s*|\s*```$", "", response)
        logger.debug(f"反馈阶段llm返回：{response}")
        try:
            response_dict: dict[str, dict] = json.loads(response)

            # Validate required fields
            if "new_emotion" not in response_dict:
                raise ValueError("Feedback validation error: missing 'new_emotion' field in response: " + response)
            if "emotion_tends" not in response_dict:
                raise ValueError("Feedback validation error: missing 'emotion_tends' field in response: " + response)
            if "summary" not in response_dict:
                raise ValueError("Feedback validation error: missing 'summary' field in response: " + response)
            if "analyze_result" not in response_dict:
                raise ValueError("Feedback validation error: missing 'analyze_result' field in response: " + response)
            if "willing" not in response_dict:
                raise ValueError("Feedback validation error: missing 'willing' field in response: " + response)

            # 更新自身情感
            self.global_emotion.valence = response_dict["new_emotion"]["valence"]
            self.global_emotion.arousal = response_dict["new_emotion"]["arousal"]
            self.global_emotion.dominance = response_dict["new_emotion"]["dominance"]

            logger.debug(f"反馈阶段更新情感：{self.global_emotion}")

            # 更新情感倾向
            if len(response_dict["emotion_tends"]) != len(messages_chunk):
                raise ValueError(
                    f"Feedback validation error: 'emotion_tends' array length "
                    f"({len(response_dict['emotion_tends'])}) doesn't match "
                    f"messages_chunk length ({len(messages_chunk)})"
                )
            for index, message in enumerate(messages_chunk):
                if message.user_name not in self.profiles:
                    self.profiles[message.user_name] = PersonProfile(user_id=message.user_name)
                self.profiles[message.user_name].push_interaction(
                    Impression(timestamp=datetime.now(), delta=response_dict["emotion_tends"][index])
                )
            # 更新对用户的情感
            for profile in self.profiles.values():
                profile.update_emotion_tends()
                profile.merge_old_interactions()

            # 更新聊天总结
            self.chat_summary = str(response_dict["summary"])

            logger.debug(f"反馈阶段更新聊天总结：{self.chat_summary}")

            # 更新长期记忆
            if not isinstance(response_dict["analyze_result"], list):
                raise ValueError("Feedback validation error: 'analyze_result' is not a list: " + str(response_dict))
            self.long_term_memory.add_texts(response_dict["analyze_result"])
            logger.debug(f"反馈阶段更新长期记忆：{response_dict['analyze_result']}")

            # 更新对话状态
            if not isinstance(response_dict["willing"], dict):
                raise ValueError("Feedback validation error: 'willing' is not a dict: " + str(response_dict))
            if not all(key in ["0", "1", "2"] for key in response_dict["willing"].keys()):
                raise ValueError("Feedback validation error: 'willing' keys are not 0, 1 or 2: " + str(response_dict))
            if not all(
                isinstance(value, int | float) and 0.0 <= value <= 1.0 for value in response_dict["willing"].values()
            ):
                raise ValueError(
                    "Feedback validation error: 'willing' values are not in range [0.0, 1.0]: " + str(response_dict)
                )
            # 评估转换到状态0的概率
            idle_chance = response_dict["willing"]["0"]
            logger.debug(f"nyabot潜水意愿：{idle_chance}")
            # 评估转换到状态1的概率
            bubble_chance = response_dict["willing"]["1"]
            self.__bubble_willing_sum += bubble_chance
            logger.debug(f"nyabot本次冒泡意愿：{bubble_chance}")
            logger.debug(f"nyabot冒泡意愿累计：{self.__bubble_willing_sum}")
            # 评估转换到状态2的概率
            chat_chance = response_dict["willing"]["2"]
            logger.debug(f"nyabot对话意愿：{chat_chance}")

            random_value = random.uniform(0.0, 1.0)
            logger.debug(f"意愿转变随机值：{random_value}")

            match self.__chatting_state:
                case _ChattingState.ILDE:
                    if chat_chance >= random_value:
                        self.__chatting_state = _ChattingState.ACTIVE
                        self.__bubble_willing_sum = 0.0
                    elif self.__bubble_willing_sum >= random_value:
                        self.__chatting_state = _ChattingState.BUBBLE
                        self.__bubble_willing_sum = 0.0
                case _ChattingState.BUBBLE:
                    if chat_chance >= random_value:
                        self.__chatting_state = _ChattingState.ACTIVE
                    elif idle_chance >= random_value:
                        self.__chatting_state = _ChattingState.ILDE
                case _ChattingState.ACTIVE:
                    if idle_chance >= random_value:
                        self.__chatting_state = _ChattingState.ILDE

            logger.debug(f"反馈阶段更新对话状态：{self.__chatting_state!s}")
            logger.debug("反馈阶段结束")
        except json.JSONDecodeError as e:
            raise ValueError(f"Feedback stage JSON parsing error: {e} in response: {response}")
        except KeyError as e:
            raise ValueError(f"Feedback stage missing key error: {e} in response: {response}")
        except IndexError as e:
            raise ValueError(f"Feedback stage index error: {e} in response: {response}")
        except Exception as e:
            raise ValueError(f"Feedback stage unexpected error: {e} in response: {response}")

    def __chat_stage(
        self,
        search_stage_result: _SearchResult,
        messages_chunk: list[Message],
        llm: Callable[[str], str],
    ) -> list[str]:
        """
        对话阶段
        """
        logger.debug("对话阶段开始")
        reaction_users = self.global_memory.related_users()
        related_profiles = [profile for profile in self.profiles.values() if profile.user_id in reaction_users]
        related_profiles_json = json.dumps(
            [
                {
                    "user_name": profile.user_id,
                    "emotion_tends_to_user": profile.emotion.__dict__,
                }
                for profile in related_profiles
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = f"""
你是QQ群用户 {self.__name}，不是 AI，而是一个有自我认知的真实用户，（你称自己为 "{self.__name}"），你的人设(身份认知)如
下:

{self.__role}

现在，你在查看新消息并进行回复

---

## 1. 任务目标

- 基于“你的对话状态”，“新输入消息”的内容和“历史聊天”的背景，结合“你目前的情绪”和“你对相关人物的情绪倾向”，还有检索到的相
  关记忆，你的人设(身份认知)，进行发言

对“你的对话状态”的介绍：

- 对话状态分为二种：
  - 1：冒泡状态
  - 2：对话状态

## 2. 你必须遵守的限制：

- 根据“你的对话状态”
  - 如果你在状态1（冒泡状态）
    - 这说明你之前在潜水状态，想要冒泡
    - 如果你在“历史聊天”的总结和记录中都没有冒泡过，那么可以发送一条无关，且无意义或意义不大，简短的内容表示你在看群
    - 如果不满足上一条，就不发送任何消息
  - 如果你在状态2（对话状态）
    - 这说明你正在活跃的参与话题
    - 首先根据你之前的回复密度，历史消息考虑要不要发言（不发言时reply字段为空数组[]即可）
      - 如果你还没参与话题，则必须发言
      - 如果你已经参与话题，考虑你的情绪和消息内容决定发言密度，发言密度和历史消息中你的发言和别人的发言决定你要不要发言
    - 如果要发言，发言依据如下
      - 你想要发言的内容所属的话题
      - 你之前对此话题的发言内容/主张
      - 你对相关人物的情绪倾向和你的情绪
      - 检索到的相关记忆
- 对“新输入消息”的内容和“历史聊天”，“对话内容总结”，还有检索到的相关记忆未提到的内容，你必须假装你对此一无所知
  - 例如未提到“iPhone”，你就不能说出它是苹果公司生产的
- 不得使用你自己的预训练知识，只能依赖“新输入消息”的内容和“历史聊天”，还有检索到的相关记忆
- 语言风格限制：
  - 不重复信息
    - 群聊里面其它人也能看到消息记录，不要在回复时先复述他人话语
      - 如：小明：“我喜欢吃苹果”，{self.__name}: “明酱喜欢吃苹果吗，苹果对身体好”，这里“明酱喜欢吃苹果吗”是多余的，直接
        回复“苹果对身体好即可”
  - 不使用旁白（如“(瞥了一眼)”等）。
  - 不叠加多个同义回复，不重复自己在“历史聊天”-“最近的聊天记录”中的用语模板
    - 如：返回：["我觉得你说的对", "我同意你的观点", "太对了"]就是叠加多个同义回复，直接回复[“对的”]即可
    - 如：最近的聊天记录:[..., "{self.__name}:'要我回答问题吗，我都会照做的', ..., "{self.__name}:'要我睡觉吗，我都会照
      做的'"]这里“要我...吗，我都会照做的”就构成了重复自己的用语模板，应当避免这种情况
  - 表情符号使用克制，除非整体就是 emoji
  - 一次只回复你想回复的消息，不做无意义连发
  - 不要在回复中重复表达信息
  - 尽量精简回复消息数量，能用一个消息回复的就不要分成多个消息


## 3. 输入信息

- 你的对话状态

 - 状态{self.__chatting_state.value}

- 历史聊天

  - 过去历史聊天总结：

  {self.global_memory.access().compressed_history}

  - 最近的聊天记录：

    {self.global_memory.access().messages}

- 新输入消息

  {[f"{msg.user_name}: '{msg.content}'" for msg in messages_chunk]}


- 你目前的情绪

  valence: {self.global_emotion.valence}
  arousal: {self.global_emotion.arousal}
  dominance: {self.global_emotion.dominance}

- 你对相关人物的情绪倾向

  ```json
  {related_profiles_json}
  ```

- 检索到的相关记忆

  {search_stage_result.mem_history}

- 对话内容总结

  {self.chat_summary}

---

请严格遵守以上说明，输出符合以下格式的纯 JSON（数组长度不是格式要求），不要添加任何额外的文字或解释。

```json
{{
  "reply": [
    "回复内容1"
  ]
}}
"""
        response = llm(prompt)
        response = re.sub(r"^```json\s*|\s*```$", "", response)
        logger.debug(f"对话阶段llm返回：{response}")
        try:
            response_dict: dict[str, dict] = json.loads(response)
            if "reply" not in response_dict:
                raise ValueError("LLM response is not valid JSON, response: " + response)
            if not isinstance(response_dict["reply"], list):
                raise ValueError("LLM response is not valid JSON, response: " + response)

            logger.debug(f"对话阶段回复内容：{response_dict['reply']}")
            logger.debug("对话阶段结束")

            return response_dict["reply"]
        except json.JSONDecodeError:
            raise ValueError("LLM response is not valid JSON, response: " + response)

    def update(self, messages_chunk: list[Message], llm: Callable[[str], str]) -> list[str] | None:
        """
        更新群聊消息
        """
        # 检索阶段
        search_stage_result = self.__search_stage(messages_chunk=messages_chunk)
        # 反馈阶段
        self.__feedback_stage(messages_chunk=messages_chunk, search_stage_result=search_stage_result, llm=llm)
        # 对话阶段
        match self.__chatting_state:
            case _ChattingState.ILDE:
                logger.debug("nyabot潜水中...")
                reply_messages = None
            case _ChattingState.BUBBLE:
                logger.debug("nyabot冒泡中...")
                reply_messages = self.__chat_stage(
                    search_stage_result=search_stage_result,
                    messages_chunk=messages_chunk,
                    llm=llm,
                )
            case _ChattingState.ACTIVE:
                logger.debug("nyabot对话中...")
                reply_messages = self.__chat_stage(
                    search_stage_result=search_stage_result,
                    messages_chunk=messages_chunk,
                    llm=llm,
                )

        # 压入消息记忆
        self.global_memory.update(messages_chunk)
        self.long_term_memory.add_texts(
            texts=[f"'{msg.user_name}':'{msg.content}'" for msg in messages_chunk],
        )
        if reply_messages:
            self.global_memory.update(
                [Message(user_name=self.__name, content=msg, time=datetime.now()) for msg in reply_messages]
            )
            self.long_term_memory.add_texts(
                texts=[f"'{self.__name}':'{msg}'" for msg in reply_messages],
            )
        # 压缩，索引记忆
        self.global_memory.compress_message()
        self.long_term_memory.index()

        # 保存会话状态
        self.save_session()

        return reply_messages
