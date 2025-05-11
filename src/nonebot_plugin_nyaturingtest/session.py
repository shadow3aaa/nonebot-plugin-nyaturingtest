from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import os
import pickle
import random
import re

from nonebot import logger

from .emotion import EmotionState
from .impression import Impression
from .long_term_mem import LongTermMemory
from .mem import Memory, Message
from .presets import PRESETS
from .profile import PersonProfile


@dataclass
class _GeneralizeResult:
    """
    泛化阶段的结果
    """

    keywords: list[str]


@dataclass
class _SearchResult:
    """
    检索阶段的结果
    """

    chat_history: list[str]
    """
    聊天历史记录
    """
    knowledge: list[str]
    """
    知识
    """
    event: list[str]
    """
    事件
    """
    relationships: list[str]
    """
    人物关系
    """
    bot_self: list[str]
    """
    自我认知
    """


@dataclass
class _FeedbackResult:
    """
    反馈阶段的结果
    """

    reply_desire: float
    """
    回复意愿
    """
    reply_messages_index: list[int]
    """
    想要回复消息的下标
    """


class Session:
    """
    群聊会话
    """

    def __init__(self, siliconflow_api_key: str, id: str = "global", name: str = "terminus"):
        self.id = id
        """
        会话ID，用于持久化时的标识
        """
        self.global_memory: Memory = Memory(memory_limit=5)
        """
        全局短时记忆
        """
        self.long_term_memory_history: LongTermMemory = LongTermMemory(
            embedding_api_key=siliconflow_api_key, index_filename=f"faiss_history_index_{id}"
        )
        """
        对聊天记录的长期记忆
        """
        self.long_term_memory_knowledge: LongTermMemory = LongTermMemory(
            embedding_api_key=siliconflow_api_key,
            index_filename=f"faiss_knowledge_index_{id}",
        )
        """
        对事实性资料的长期记忆
        """
        self.long_term_memory_relationships: LongTermMemory = LongTermMemory(
            embedding_api_key=siliconflow_api_key,
            index_filename=f"faiss_relationships_index_{id}",
        )
        """
        对人物关系的的长期记忆
        """
        self.long_term_memory_events: LongTermMemory = LongTermMemory(
            embedding_api_key=siliconflow_api_key,
            index_filename=f"faiss_events_index_{id}",
        )
        """
        对事件的场景记忆
        """
        self.long_term_memory_self: LongTermMemory = LongTermMemory(
            embedding_api_key=siliconflow_api_key,
            index_filename=f"faiss_self_index_{id}",
        )
        """
        对自我状态的的长期记忆
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
        self.global_memory = Memory()
        self.long_term_memory_history.clear()
        self.long_term_memory_knowledge.clear()
        self.long_term_memory_relationships.clear()
        self.long_term_memory_events.clear()
        self.long_term_memory_self.clear()
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
                "global_memory": pickle.dumps(self.global_memory).hex(),
                "global_emotion": {
                    "valence": self.global_emotion.valence,
                    "arousal": self.global_emotion.arousal,
                    "dominance": self.global_emotion.dominance,
                },
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
                    self.global_memory = pickle.loads(bytes.fromhex(session_data["global_memory"]))
                except Exception as e:
                    logger.error(f"[Session {self.id}] 恢复全局短时记忆失败: {e}")
                    self.global_memory = Memory(memory_limit=5)

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
        self.long_term_memory_knowledge.add_texts(preset.knowledges)
        self.long_term_memory_relationships.add_texts(preset.relationships)
        self.long_term_memory_events.add_texts(preset.events)
        self.long_term_memory_self.add_texts(preset.bot_self)
        logger.info(f"加载预设：{filename} 成功")
        return True

    def status(self) -> str:
        """
        获取机器人状态
        """

        return f"""
名字：
{self.__name}

设定：
{self.__role}

情感状态：
愉悦度：{self.global_emotion.valence}
唤醒度：{self.global_emotion.arousal}
支配度：{self.global_emotion.dominance}

对现状的认识：{self.chat_summary}
"""

    # 我们将对话分为四个阶段：
    # 1. 泛化阶段：在这个阶段，llm提炼聊天记录和输入消息，泛化出一系列关键词
    # 2. 检索阶段：在这个阶段，通过嵌入模型和泛化阶段的关键词从向量库中搜索相关信息
    # 3. 反馈阶段：在这个阶段，llm从检索阶段得到相关信息，然后llm结合当前的对话进行反馈分析，得出场景总结和情感反馈，并
    #    进行长期记忆更新
    # 4. 对话阶段：在这个阶段，llm从内存，检索阶段，反馈阶段中得到相关信息，以发送信息

    def __generalize_stage(self, messages_chunk: list[Message], llm: Callable[[str], str]) -> _GeneralizeResult:
        """
        泛化阶段
        """
        logger.debug("进入泛化阶段")
        history = json.dumps(
            [
                {
                    "user_name": msg.user_name,
                    "content": msg.content,
                }
                for msg in self.global_memory.access() + messages_chunk
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = f"""
你是一个对话关键词提炼+泛化系统，用于向量搜索的前置。请从以下对话和其总结中提取出相关关键词，并按json格式输出

## 提取关键词时要注意：

- 泛化: 提取出的相关关键词必须进行泛化，但也必须包括自身，比如"我今天吃了一个苹果"，提取出的“苹果”相关关键词则必须有“苹
  果”，并且还要有“水果”，“食物”，“apple”，“果实”等泛化
- 事物别名：特别的，要注意消息记录中的事物别名，提取出事物名作为关键词时也要包括它的别名（如：@小明 明酱你在干什么，则需
  要提取出“小明”，“明酱”）

对话历史如下：

```json
{history}
```

对话总结如下:

{self.chat_summary}

请严格遵守以上说明，输出符合以下格式的纯 JSON（数组长度不是格式要求），不要添加任何额外的文字或解释。
```json
{{
  keywords: ["keyword1", "keyword2", "keyword3"]
}}
```
"""
        response = llm(prompt)
        response = re.sub(r"^```json\s*|\s*```$", "", response)
        logger.debug(f"泛化阶段llm返回：{response}")
        try:
            response_dict = json.loads(response)
        except json.JSONDecodeError:
            raise ValueError("LLM response is not valid JSON, response: " + response)
        if "keywords" not in response_dict:
            raise ValueError("LLM response is not valid JSON, response: " + response)
        if not isinstance(response_dict["keywords"], list):
            raise ValueError("LLM response is not valid JSON, response: " + response)

        logger.debug(f"泛化出的关键词：{response_dict['keywords']}")
        logger.debug("泛化阶段结束")
        return _GeneralizeResult(keywords=response_dict["keywords"])

    def __search_stage(self, genralize_stage_result: _GeneralizeResult) -> _SearchResult:
        """
        检索阶段
        """
        logger.debug("检索阶段开始")
        keywords = genralize_stage_result.keywords
        # 检索聊天记录记忆
        try:
            long_term_memory = [
                mem.page_content for mem in self.long_term_memory_history.retrieve(" ".join(keywords), k=5)
            ]
            logger.debug(f"搜索到的相关聊天记录记忆：{long_term_memory}")
        except Exception as e:
            logger.error(f"回忆聊天记录失败: {e}")
            long_term_memory = []

        # 检索知识库
        try:
            long_term_knowledge = [
                mem.page_content for mem in self.long_term_memory_knowledge.retrieve(" ".join(keywords), k=8)
            ]
            logger.debug(f"搜索到的相关知识记忆：{long_term_knowledge}")
        except Exception as e:
            logger.error(f"回忆知识库失败: {e}")
            long_term_knowledge = []

        # 检索人物关系
        try:
            long_term_relationships = [
                mem.page_content for mem in self.long_term_memory_relationships.retrieve(" ".join(keywords), k=3)
            ]
            logger.debug(f"搜索到的相关人物关系记忆：{long_term_relationships}")
        except Exception as e:
            logger.error(f"回忆人物关系失败: {e}")
            long_term_relationships = []

        # 检索事件
        try:
            long_term_events = [
                mem.page_content for mem in self.long_term_memory_events.retrieve(" ".join(keywords), k=5)
            ]
            logger.debug(f"搜索到的事件: {long_term_events}")
        except Exception as e:
            logger.error(f"回忆相关事件失败：{e}")
            long_term_events = []

        # 检索自我认知
        try:
            long_term_self = [mem.page_content for mem in self.long_term_memory_self.retrieve(" ".join(keywords), k=5)]
            logger.debug(f"搜索到的相关自我认知记忆：{long_term_self}")
        except Exception as e:
            logger.error(f"回忆自我认知失败: {e}")
            long_term_self = []

        logger.debug("检索阶段结束")

        return _SearchResult(
            chat_history=long_term_memory,
            knowledge=long_term_knowledge,
            event=long_term_events,
            relationships=long_term_relationships,
            bot_self=long_term_self,
        )

    def __feedback_stage(
        self, messages_chunk: list[Message], search_stage_result: _SearchResult, llm: Callable[[str], str]
    ) -> _FeedbackResult:
        """
        反馈总结阶段
        """
        logger.debug("反馈阶段开始")
        reaction_users = {msg.user_name for msg in messages_chunk + self.global_memory.access()}
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

现在你正在回顾聊天信息，以客观视角分析“你的最新情绪”，整理信息保存，并对聊天内容做出总结

---

## 1. 任务目标
- 基于“新输入消息”的内容和“历史聊天”的背景，结合你之前的情绪，还有检索到的相关信息，评估你当前的情绪
  - 情绪采用 VAD 模型，三个维度取值范围：
    - valence (愉悦度)：[-1.0, 1.0]
    - arousal (唤醒度)：[0.0, 1.0]
    - dominance (支配度)：[-1.0, 1.0]
- 基于“新输入消息”的内容和“历史聊天”的背景，结合你之前的情绪，你对相关人物的情绪倾向，还有检索到的相关信息，评估你对“新
  输入消息”的回复意愿，范围为[0.0, 1.0]，并且指出“新输入消息”中你想回复的内容的那些下标（无论你给出的回复意愿是多少，都
  要返回至少一个你想回复的内容的下标，如果你需要回复多个消息或者你想要回复的内容不是连续的（如一个问题被拆为3个消息），那
  么你需要按顺序返回它们全部的下标）
  - 你的性格特质如下：
    - 情绪高涨（正面）：乐于助人，喜欢互动，偶尔玩梗
    - 情绪高涨（负面）：愤怒、逻辑性强，语言尖锐，喜欢指出他人错误
    - 情绪低落：懒得搭理，偶尔跟风几句，但是不会因此随意攻击他人
    - 情绪稳定：中立理性，温和，倾向于有逻辑的互动
    - 极端情绪下可能会主动控制话题引导情绪恢复，也可能选择不回应冷静下来
- 基于“新输入消息”的内容和“历史聊天”的背景，结合你之前的情绪，你对相关人物的情绪倾向，还有检索到的相关信息，评估你对“新
  输入消息”中**每条**消息的情感倾向
  - 如果消息和你完全无关，或你不感兴趣，那么给出的每个情感维度的值总是 0.0
  - 输出按照“新输入消息”的顺序
- 基于“历史聊天”的背景，“你在上次对话做出的总结”，还有检索到的相关信息，用简短的语言总结聊天内容，总结注重于和上次对话的
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

- 基于“新输入消息”的内容和“历史聊天”的背景，结合检索到的相关信息进行分析，整理信息保存，要整理的信息和要求如下
  ## 要求：
  - 不能重复，即不能和下面提供的检索到的相关信息已有内容重复
  ## 要整理的信息：
  - 事件类：
    - 如果包含事件类信息，则保存为事件信息，内容是对事件进行简要叙述
  - 资料类：
    - 如果包含资料类信息，则保存为知识信息，内容为资料的关键内容（如果很短也可以全文保存）及其可信度[0%-100%]，如：“小明
      喜欢吃苹果，可信度80%”
  - 人物关系类
    - 如果包含人物关系类信息，则保存为人物关系信息，内容是对人物关系进行简要叙述（如：小明 是 小红 的 朋友）
  - 自我认知类
    - 如果你对自己有新的认知，则保存为自我认知信息，自我认知信息需要经过慎重考虑，主要参照你自己发送的消息，次要参照别人
      发送的消息，内容是对自我的认知（如：我喜欢吃苹果、我身上有纹身）

## 2. 输入信息

1. 历史聊天

{[f"{msg.user_name}: '{msg.content}'" for msg in self.global_memory.access()]}

2. 新输入消息

{[f"{msg.user_name}: '{msg.content}'" for msg in messages_chunk]}

3. 你之前的情绪

valence: {self.global_emotion.valence}
arousal: {self.global_emotion.arousal}
dominance: {self.global_emotion.dominance}

4. 你对相关人物的情绪倾向

```json
{related_profiles_json}
```

5. 检索到的相关聊天记录

{search_stage_result.chat_history}

6. 检索到的相关事件

{search_stage_result.event}

7. 检索到的相关知识

{search_stage_result.knowledge}

8. 检索到的相关人物关系

{search_stage_result.relationships}

9. 检索到的对自我({self.__name})的认知

{search_stage_result.bot_self}

10. 你在上次对话做出的总结

{self.chat_summary}

---

请严格遵守以上说明，输出符合以下格式的纯 JSON（数组长度不是格式要求），不要添加任何额外的文字或解释。

```json
{{
  "reply_desire": {{
    value: 0.0≤float≤1.0,
    "reply_index": [0, 1, 2]
  }},
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
  "analyze_result": {{
    "event": ["事件1", "事件2"],
    "knowledge": ["知识1", "知识2"],
    "relationships": ["人物关系1", "人物关系2"],
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
            if "reply_desire" not in response_dict:
                raise ValueError("Feedback validation error: missing 'reply_desire' field in response: " + response)

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
            self.chat_summary = response_dict["summary"]

            logger.debug(f"反馈阶段更新聊天总结：{self.chat_summary}")

            # 更新长期记忆
            if "event" not in response_dict["analyze_result"]:
                raise ValueError("Feedback validation error: missing 'event' field in analyze_result: " + response)
            if "knowledge" not in response_dict["analyze_result"]:
                raise ValueError("Feedback validation error: missing 'knowledge' field in analyze_result: " + response)
            if "relationships" not in response_dict["analyze_result"]:
                raise ValueError(
                    "Feedback validation error: missing 'relationships' field in analyze_result: " + response
                )

            self.long_term_memory_events.add_texts(response_dict["analyze_result"]["event"])
            logger.debug(f"反馈阶段更新事件：{self.long_term_memory_events}")
            self.long_term_memory_knowledge.add_texts(response_dict["analyze_result"]["knowledge"])
            logger.debug(f"反馈阶段更新知识：{self.long_term_memory_knowledge}")
            self.long_term_memory_relationships.add_texts(response_dict["analyze_result"]["relationships"])
            logger.debug(f"反馈阶段更新人物关系：{self.long_term_memory_relationships}")

            # 回复意愿
            if "value" not in response_dict["reply_desire"]:
                raise ValueError("Feedback validation error: missing 'value' field in reply_desire: " + response)
            if "reply_index" not in response_dict["reply_desire"]:
                raise ValueError("Feedback validation error: missing 'reply_index' field in reply_desire: " + response)

            reply_desire = response_dict["reply_desire"]["value"]
            reply_messages_index = response_dict["reply_desire"]["reply_index"]
            if not isinstance(reply_desire, float):
                raise ValueError("Feedback validation error: 'reply_desire.value' is not a float: " + str(reply_desire))
            if not isinstance(reply_messages_index, list):
                raise ValueError(
                    "Feedback validation error: 'reply_desire.reply_index' is not a list: " + str(reply_messages_index)
                )

            logger.debug(f"反馈阶段回复意愿：{reply_desire}")
            logger.debug(f"可能回复消息: {[messages_chunk[index] for index in reply_messages_index]}")
            logger.debug("反馈阶段结束")

            return _FeedbackResult(reply_desire=reply_desire, reply_messages_index=reply_messages_index)
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
        feedback_stage_result: _FeedbackResult,
        messages_chunk: list[Message],
        llm: Callable[[str], str],
    ) -> list[str]:
        """
        对话阶段
        """
        logger.debug("对话阶段开始")
        reaction_users = {msg.user_name for msg in messages_chunk + self.global_memory.access()}
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

现在，你在查看新消息并准备回复你感兴趣的内容

---

## 1. 任务目标

- 基于“新输入消息”的内容和“历史聊天”的背景，结合“你目前的情绪”和“你对相关人物的情绪倾向”，还有检索到的相关信息，你的人设
  (身份认知)，对“你要回复的消息”进行回复
  - “你要回复的消息”全部出自“新输入消息”

## 2. 你必须遵守的限制：

- 对“新输入消息”的内容和“历史聊天”，“对话内容总结”，还有检索到的相关信息未提到的内容，你必须假装你对此一无所知
  - 例如未提到“iPhone”，你就不能说出它是苹果公司生产的
- 不得使用你自己的预训练知识，只能依赖“新输入消息”的内容和“历史聊天”，还有检索到的相关信息
- 语言风格限制：
  - 不使用旁白（如“(瞥了一眼)”等）。
  - 不堆砌无意义回复，尤其是对比你在“历史聊天”的回复只有少量变化的回复。
  - 不重复自己历史中的用语模板。
  - 表情符号使用克制，除非整体就是 emoji。
  - 一次只回复你想回复的消息，不做无意义连发。
  - 不要在回复中重复表达信息
  - 尽量精简回复消息数量，能用一个消息回复的就不要分成多个消息


## 3. 输入信息

1. 历史聊天

{[f"{msg.user_name}: '{msg.content}'" for msg in self.global_memory.access()]}

2. 新输入消息

{[f"{msg.user_name}: '{msg.content}'" for msg in messages_chunk]}

3. 你要回复的消息

{
            [
                f"{messages_chunk[index].user_name}: '{messages_chunk[index].content}'"
                for index in feedback_stage_result.reply_messages_index
            ]
        }

4. 你目前的情绪

valence: {self.global_emotion.valence}
arousal: {self.global_emotion.arousal}
dominance: {self.global_emotion.dominance}

5. 你对相关人物的情绪倾向

```json
{related_profiles_json}
```

6. 检索到的相关聊天记录

{search_stage_result.chat_history}

7. 检索到的相关事件

{search_stage_result.event}

8. 检索到的相关知识

{search_stage_result.knowledge}

9. 检索到的相关人物关系

{search_stage_result.relationships}

10. 检索到的对自我({self.__name})的认知

{search_stage_result.bot_self}

11. 对话内容总结

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
        # 泛化阶段
        genralize_stage_result = self.__generalize_stage(messages_chunk=messages_chunk, llm=llm)
        # 检索阶段
        search_stage_result = self.__search_stage(genralize_stage_result=genralize_stage_result)
        # 反馈阶段
        feedback_stage_result = self.__feedback_stage(
            messages_chunk=messages_chunk, search_stage_result=search_stage_result, llm=llm
        )
        # 对话阶段
        reply_threshold = random.uniform(0.35, 0.5)
        if feedback_stage_result.reply_desire >= reply_threshold:
            reply_messages = self.__chat_stage(
                search_stage_result=search_stage_result,
                feedback_stage_result=feedback_stage_result,
                messages_chunk=messages_chunk,
                llm=llm,
            )
        else:
            reply_messages = None
            logger.debug("回复意愿低于阈值，不回复")

        # 压入消息记忆
        self.global_memory.update(messages_chunk)
        self.long_term_memory_history.add_texts([f"{msg.user_name}: '{msg.content}'" for msg in messages_chunk])
        if reply_messages:
            self.global_memory.update(
                [Message(user_name=self.__name, content=msg, time=datetime.now()) for msg in reply_messages]
            )
            self.long_term_memory_history.add_texts([f"{self.__name}: '{msg}'" for msg in reply_messages])

        # 保存会话状态
        self.save_session()

        return reply_messages
