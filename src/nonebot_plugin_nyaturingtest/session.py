from collections import deque
from collections.abc import Callable
from datetime import datetime
import json
import os
import pickle
import random
import re

from nonebot import logger

from .emotion import EmotionState
from .impression import Impression
from .knowledge_mem import KnowledgeMemory
from .long_term_mem import LongTermMemory
from .mem import Memory, Message
from .profile import PersonProfile


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
        self.global_long_term_memory: LongTermMemory = LongTermMemory(
            api_key=siliconflow_api_key, index_filename=f"faiss_index_{id}"
        )
        """
        全局长期记忆
        """
        self.global_knowledge_memory: KnowledgeMemory = KnowledgeMemory(
            api_key=siliconflow_api_key,
            index_filename=f"faiss_knowledge_index_{id}",
        )
        """
        全局知识记忆
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
        self.__role = "一个男性人类"

        # 从文件加载会话状态（如果存在）
        self.load_session()

    def set_role(self, name: str, role: str):
        """
        设置角色
        """
        self.__role = role
        self.__name = name
        self.reset()
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
        self.global_memory = Memory()
        self.global_long_term_memory.clear()
        self.global_knowledge_memory.clear()
        self.profiles = {}
        self.global_emotion = EmotionState()
        self.last_response = []
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

            logger.trace(f"[Session {self.id}] 会话状态已保存")
        except Exception as e:
            logger.trace(f"[Session {self.id}] 保存会话状态失败: {e}")

    def load_session(self):
        """
        从文件加载会话状态
        """
        file_path = self.get_session_file_path()
        if not os.path.exists(file_path):
            logger.trace(f"[Session {self.id}] 会话文件不存在，使用默认状态")
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

    def __emotion_feedback(self, knowledges: list[str], long_term_memory: list[str], llm: Callable[[str], str]):
        if len(self.last_response) == 0:
            return
        history = json.dumps(
            [
                {
                    "user_name": msg.user_name,
                    "content": msg.content,
                }
                for msg in self.global_memory.access()
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = f"""
你是QQ群用户 {self.__name}（你称自己为 "{
            self.__name
        }"），正在回顾刚刚自己在群里的发言，以客观视角分析“你的最新情绪”，并输出新的 VAD 值。

---

## 1. 任务目标
- 基于“上次发言”的内容和“历史聊天”的背景，评估你当前的情绪变化。
- 情绪采用 VAD 模型，三个维度取值范围：
  - valence (愉悦度)：[-1.0, 1.0]
  - arousal (唤醒度)：[0.0, 1.0]
  - dominance (支配度)：[-1.0, 1.0]

---

## 2. 输入信息

1. **历史聊天（仅供参考，无需打分）**
```json
{history}
````

2. **之前的情绪状态**

```json
{json.dumps(self.global_emotion.__dict__, ensure_ascii=False, indent=2)}
```

3. 🧠 从记忆中联想到的过去聊天内容（不一定准确）：

```
{long_term_memory}
```

4. 📚 从记忆中联想到的相关知识（知识库中明确定义的内容）：

```
{knowledges}
```

5. **上次你发送的消息（需分析此部分）**

```json
{
            json.dumps(
                [{"user_name": msg.user_name, "content": msg.content} for msg in self.last_response],
                ensure_ascii=False,
                indent=2,
            )
        }
```

---

## 3. 输出格式

* **只输出**下面的 JSON，不要任何额外文字、注释或格式标记：

```json
{{
  "new_emotion": {{
    "valence": 0.0≤float≤1.0,
    "arousal": 0.0≤float≤1.0,
    "dominance": -1.0≤float≤1.0
  }}
}}
```

> 例如：
>
> ```json
> {{
>   "new_emotion": {{
>     "valence": 0.5,
>     "arousal": 0.3,
>     "dominance": -0.2
>   }}
> }}
> ```

---

## 4. 行为说明

* **仅分析上次自己发的那条消息对情绪的即时影响**，不需要对历史消息打分。
* 若上次发言让你感到正向刺激，valence ↑；若遭遇质疑或负面反馈，valence ↓。
* 若上次内容引发紧张或兴奋，arousal ↑；若较平淡或无感，arousal 接近 0。
* 若上次发言让你感到更受控制，dominance ↑；若失去掌控感，dominance ↓。

---

请严格遵守以上说明，输出符合格式的纯 JSON，不要添加任何额外的文字或解释。
"""
        score_response = llm(prompt)
        logger.trace(f"LLM reply response: {score_response}")
        score_response = re.sub(r"^```json\s*|\s*```$", "", score_response)
        try:
            score_response_dict: dict[str, dict] = json.loads(score_response)
        except json.JSONDecodeError:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)
        if "new_emotion" not in score_response:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)
        if "valence" not in score_response_dict["new_emotion"]:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)
        if "arousal" not in score_response_dict["new_emotion"]:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)
        if "dominance" not in score_response_dict["new_emotion"]:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)

        self.global_emotion.valence = score_response_dict["new_emotion"]["valence"]
        self.global_emotion.arousal = score_response_dict["new_emotion"]["arousal"]
        self.global_emotion.dominance = score_response_dict["new_emotion"]["dominance"]

    def __core(
        self,
        message_chunk: list[Message],
        knowledges: list[str],
        long_term_memory: list[str],
        llm: Callable[[str], str],
    ) -> list[str]:
        self.__emotion_feedback(knowledges=knowledges, long_term_memory=long_term_memory, llm=llm)

        history = json.dumps(
            [
                {
                    "user_name": msg.user_name,
                    "content": msg.content,
                }
                for msg in self.global_memory.access()
            ],
            ensure_ascii=False,
            indent=2,
        )
        new_messages = json.dumps(
            [
                {
                    "user_name": msg.user_name,
                    "content": msg.content,
                }
                for msg in message_chunk
            ],
            ensure_ascii=False,
            indent=2,
        )

        # 获取对相关用户的情感
        reaction_users = {msg.user_name for msg in message_chunk + self.global_memory.access()}
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

        score_prompt = f"""
你是一个群聊用户「{self.__name}」，你将根据最新的聊天内容和你当前的情绪状态，做出主观判断，分析这段对话对你的情绪有何影响，并评估你此刻的回复意愿。

你具有三维度的情绪状态，使用 VAD 模型表示，三个维度为：

- 愉悦度 (valence)：[-1.0, 1.0]，情绪正负向
- 唤醒度 (arousal)：[0.0, 1.0]，情绪激活程度
- 支配度 (dominance)：[-1.0, 1.0]，控制感程度

你还将输出你对每条消息的「reply_desire」（回复欲望），范围为 [0.0, 1.0]。

---

## 🎭 你的角色人格特质如下：
- 情绪高涨（正面）：乐于助人，喜欢互动，偶尔玩梗
- 情绪高涨（负面）：愤怒、逻辑性强，语言尖锐，喜欢指出他人错误
- 情绪低落：懒得搭理，偶尔跟风几句
- 情绪稳定：中立理性，温和，倾向于有逻辑的互动
- 极端情绪下可能会主动控制话题引导情绪恢复，也可能选择不回应冷静下来

---

## 📌 回复欲望计算规则（reply_desire）：

- 空消息或乱码：必为 0.0
- 与你无关的内容：0.0 ~ 0.15
- 根据上下文和你有关、明确@你或直接要求你回应：只要不冲突你的情绪，一般 0.5 ~ 0.6
- 兴趣话题或挑战你认知的内容：0.3 ~ 0.7，取决于你的主观态度

---

## 🧠 你拥有的信息：

1. 🧍 你自己的情绪状态（VAD）如下：
```json
{self.global_emotion.__dict__}
````

2. 👤 你对各个用户的主观情绪如下（VAD 倾向）：

```json
{related_profiles_json}
```

3. 📜 最近的聊天历史如下：

```json
{history}
```

4. 💬 当前收到的新消息如下：

```json
{new_messages}
```

5. 🧠 从记忆中联想到的过去聊天内容（不一定准确）：

```
{long_term_memory}
```

6. 📚 从记忆中联想到的相关知识（知识库中明确定义的内容）：

```
{knowledges}
```

---

## ❗你必须遵守的限制：

* 若知识库中没有提到某个概念，你必须假装你对此一无所知

  * 例如知识库未提到“iPhone”，你就不能说出它是苹果公司生产的
* 不得使用你自己的预训练知识，只能依赖提供的知识库内容
* 若知识库没有相关内容，或者你认为此内容应该记录（比如你现在的状态，两个人物之间的关系）但是提供的知识中没有，你应总结并补充为新的知识记录在末尾

---

## ✅ 输出格式（只返回下列 JSON）输出按照新的输入消息的顺序来：

## ⚠ 输出要求

* 格式参考下面的 JSON，不要任何额外文字、注释或格式标记
* 反应数量与输入消息数量一致
* 反应顺序与输入消息顺序一致

```json
{{
  "reactions": [
      {{
        "user_name": "xxx",
        "valence": 0.1,
        "arousal": 0.3,
        "dominance": -0.2,
        "reply_desire": 0.4
      }},
      {{
        "user_name": "yyy",
        "valence": 0.1,
        "arousal": 0.3,
        "dominance": -0.2,
        "reply_desire": 0.4
      }},
    ],
    "new_knowledge": [
      "xxx 是一款游戏",
      "{self.__name} 曾经和 xxx 有过争执"
    ]
}}
```
"""  # noqa: E501
        score_response = llm(score_prompt)
        logger.trace(f"LLM reply response: {score_response}")
        score_response = re.sub(r"^```json\s*|\s*```$", "", score_response)
        try:
            score_response_dict: dict[str, dict] = json.loads(score_response)
        except json.JSONDecodeError:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)

        if "new_knowledge" in score_response_dict:
            if not isinstance(score_response_dict["new_knowledge"], list):
                raise ValueError("LLM response is not valid JSON, response: " + score_response)
            for knowledge in score_response_dict["new_knowledge"]:
                self.global_knowledge_memory.add_knowledge(knowledge)
                knowledges.append(knowledge)  # 新增的知识要求也能被使用

        if "reactions" not in score_response_dict:
            raise ValueError("LLM response is not valid JSON, response: " + score_response)

        if len(score_response_dict["reactions"]) != len(message_chunk):
            raise ValueError("LLM response is not valid JSON, response: " + score_response)

        # 根据回复意愿标记要回复的消息
        new_messages_with_reply_tag: list[dict] = []

        for index, reaction in enumerate(score_response_dict["reactions"]):
            msg = message_chunk[index]
            new_messages_with_reply_tag.append(
                {"user_name": msg.user_name, "content": msg.content, "want_reply": False}
            )
            if (
                "user_name" not in reaction
                or "valence" not in reaction
                or "arousal" not in reaction
                or "dominance" not in reaction
                or "reply_desire" not in reaction
            ):
                raise ValueError("LLM response is not valid JSON, response: " + score_response)
            else:
                if self.profiles.get(reaction["user_name"]) is None:
                    self.profiles[reaction["user_name"]] = PersonProfile(user_id=reaction["user_name"])

                self.profiles[reaction["user_name"]].push_interaction(
                    impression=Impression(
                        timestamp=message_chunk[index].time,
                        delta={
                            "valence": reaction["valence"],
                            "arousal": reaction["arousal"],
                            "dominance": reaction["dominance"],
                        },
                    ),
                )

                # 回复阈值随机浮动在0.15-0.3之间
                reply_threshold = random.uniform(0.15, 0.3)
                logger.trace(f"Reply threshold: {reply_threshold}, reply desire: {reaction['reply_desire']}")
                if reaction["reply_desire"] >= reply_threshold:
                    new_messages_with_reply_tag[index]["want_reply"] = True

        # 更新对用户的情感
        for profile in self.profiles.values():
            profile.update_emotion_tends()
            profile.merge_old_interactions()

        self.global_long_term_memory.add_texts([f"{msg.user_name}: '{msg.content}'" for msg in message_chunk])

        # 如果没有要回复的消息，则返回空列表
        if not any(msg["want_reply"] for msg in new_messages_with_reply_tag):
            return []

        reply_prompt = f"""
你是QQ群用户 {self.__name}，不是 AI，而是一个有自我认知的真实用户，你在查看新消息并准备回复你感兴趣的内容。

---

你的身份认知是：
`{self.__role}`

你当前的情绪状态（VAD 模型）如下：
```json
{json.dumps(self.global_emotion.__dict__, ensure_ascii=False, indent=2)}
````

你对其他用户的情感态度（VAD）如下：

```json
{related_profiles_json}
```

---

你接收到的新消息列表如下（注意：只有 `want_reply=true` 的消息是你决定要回复的）：

```json
{json.dumps(new_messages_with_reply_tag, ensure_ascii=False, indent=2)}
```

这些消息与之前的聊天连续。为你要回复的消息提供完整语境，比如一个问题可能拆成多段，而你只选择了最后一段回答，那么依旧需要参考前面的信息得到完整问题，下面是之前的消息历史（无需回复）：

```json
{history}
```

---

你还可以参考：

* 你的联想记忆（非真实记录，只是你对历史的模糊回忆）：

```
{long_term_memory}
```

* 联想到的“已知知识”（⚠只能依赖这部分回答事实性问题）：

```
{knowledges}
```

---

❗你必须遵守的限制：

* 若知识库中没有提到某个概念，你必须假装你对此一无所知

  * 例如知识库未提到“iPhone”，你就不能说出它是苹果公司生产的
* 不得使用你自己的预训练知识，只能依赖提供的知识库内容
* 不要解释这些限制本身

---

在回复时，请综合考虑：

* 你当前的情绪
* 你对各个用户的情绪
* 联想和知识内容
* 以下你的行为风格：

情绪状态对行为的影响：

* **稳定**：友好、乐于助人、轻微嘲讽、正常长度、偶尔长段落。
* **低落**：冷漠、少言、不主动、短回复、跟风。
* **高涨（正向）**：热情、活跃、偶尔玩梗（不过度）、积极互动。
* **高涨（负向）**：愤怒、逻辑性强、讽刺、单条长回复、攻击性语言、爱指出逻辑错误。
* **极端情绪**：主动缓和、回避、尝试引导情绪恢复，例如反问或沉默。

⚠ 语言风格限制：

* 不使用旁白（如“(瞥了一眼)”等）。
* 不堆砌无意义回复。
* 不重复自己历史中的用语模板。
* 表情符号使用克制，除非整体就是 emoji。
* 一次只回复你想回复的消息，不做无意义连发。

---

请用以下格式作答，仅输出你想发送的回复内容（顺序按你要发的消息顺序）：

```json
{{
  "messages": [
    "（你的回复1）",
    "（你的回复2）"
  ]
}}
```

"""
        reply_response = llm(reply_prompt)
        reply_response = re.sub(r"^```json\s*|\s*```$", "", reply_response)
        try:
            reply_response_dict: dict[str, list[str]] = json.loads(reply_response)
            logger.trace(f"LLM reply response: {reply_response}")
        except json.JSONDecodeError:
            raise ValueError("LLM response is not valid JSON, response: " + reply_response)

        if "messages" not in reply_response:
            raise ValueError("LLM response is not valid JSON, response: " + reply_response)

        self.global_long_term_memory.add_texts([f"{self.__name}: '{msg}'" for msg in reply_response_dict["messages"]])

        return reply_response_dict["messages"]

    def update(self, message_chunk: list[Message], llm: Callable[[str], str]) -> list[str]:
        """
        更新会话
        - message_chunk: 消息块
        - llm: 调用llm的函数，接受消息输入并返回输出，不要手动保存消息历史
        """

        # 从知识库检索相关片段
        chunk_texts = [f"{msg.user_name}: '{msg.content}'" for msg in message_chunk]
        try:
            knowledges = [mem.page_content for mem in self.global_knowledge_memory.retrieve(" ".join(chunk_texts), k=8)]
        except Exception as e:
            logger.error(f"Error: {e}")
            knowledges = []
        # 从长期记忆检索相关片段
        try:
            long_term_memory = [
                mem.page_content for mem in self.global_long_term_memory.retrieve(" ".join(chunk_texts), k=8)
            ]
        except Exception as e:
            logger.trace(f"Error: {e}")
            long_term_memory = []

        logger.trace(f"搜索到的相关记忆：{long_term_memory}")
        logger.trace(f"搜索到的相关知识：{knowledges}")

        result = self.__core(
            message_chunk=message_chunk, knowledges=knowledges, long_term_memory=long_term_memory, llm=llm
        )
        result_messages = [Message(time=datetime.now(), user_name=f"{self.__name}", content=msg) for msg in result]
        self.last_response = result_messages
        # 更新全局短时记忆
        self.global_memory.update(message_chunk=message_chunk + result_messages)
        self.save_session()  # 保存更新后的状态
        return result

    def add_knowledge(self, knowledge: str):
        """
        添加知识
        """

        self.global_knowledge_memory.add_knowledge(knowledge)
        self.save_session()  # 保存添加知识后的状态

    def status(self) -> str:
        """
        获取会话状态
        """

        return json.dumps(
            {
                "short_term": [{"user_name": m.user_name, "content": m.content} for m in self.global_memory.access()],
                "long_term": [f"{e.page_content}" for e in self.global_long_term_memory.list_all()[:5]],
                "knowledge": [f"{e.page_content}" for e in self.global_knowledge_memory.list_all()[:5]],
                "profiles": [{"user_name": p.user_id, "emotion": p.emotion.__dict__} for p in self.profiles.values()],
                "global_emotion": self.global_emotion.__dict__,
            },
            ensure_ascii=False,
            indent=2,
        )
