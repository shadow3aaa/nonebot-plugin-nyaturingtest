from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import math

from .emotion import EmotionState
from .impression import Impression


@dataclass
class PersonProfile:
    """
    对人物的记忆与情感
    """

    user_id: str
    """
    "你叫什么名字？"
    """
    emotion: EmotionState = field(default_factory=EmotionState)
    """
    对你的情感倾向
    """
    interactions: deque[Impression] = field(default_factory=deque)
    """
    交互的记录
    """

    def push_interaction(self, impression: Impression):
        """
        添加交互记录
        """
        self.interactions.appendleft(impression)

    def merge_old_interactions(self):
        # 合并过于久远的印象
        # 5小时之前的印象会被合并
        old_interactions = [
            interaction
            for interaction in self.interactions
            if (datetime.now() - interaction.timestamp).total_seconds() / 3600 > 5
        ]
        if len(old_interactions) > 0:
            # 总印象
            valence = 0.0
            valence_negative = 0.0
            arousal = 0.0
            arousal_negative = 0.0
            dominance = 0.0
            dominance_negative = 0.0

            now = datetime.now()
            merged_impression_time: datetime | None = None

            # 从印象中计算得出对这个人的情感倾向
            for impression in self.interactions:
                # 将最近的印象时间作为合并印象的时间
                if merged_impression_time is None or impression.timestamp < merged_impression_time:
                    merged_impression_time = impression.timestamp

                # 计算距离印象的时间
                elapsed_time = now - impression.timestamp
                elapsed_hours = elapsed_time.seconds / 3600.0

                # 衰减印象的愉悦度，无论好坏
                # 愉悦总是短暂的，厌恶却会在心中挥之不去
                decayed_valence = decay_valence(elapsed_hours, impression.delta.get("valence", 0.0))

                # 衰减印象的激活度
                # 在疯狂降临之前，无论是极度恐惧还是极度兴奋，都会很快平复
                decayed_arousal = decay_arousal(elapsed_hours, impression.delta.get("arousal", 0.0))

                # 衰减印象的支配度
                # 支配度在日积月累中形成，不会轻易改变
                decayed_dominance = decay_dominance(elapsed_hours, impression.delta.get("dominance", 0.0))

                # 计算出的情感也是情感
                if decayed_valence > 0:
                    valence = max(valence, decayed_valence)
                else:
                    valence_negative = min(valence_negative, decayed_valence)
                if decayed_arousal > 0:
                    arousal = max(arousal, decayed_arousal)
                else:
                    arousal_negative = min(arousal_negative, decayed_arousal)
                if decayed_dominance > 0:
                    dominance = max(dominance, decayed_dominance)
                else:
                    dominance_negative = min(dominance_negative, decayed_dominance)

            # 合并为一个印象
            if merged_impression_time is None:
                return

            merged_impression = Impression(
                delta={
                    "valence": valence + valence_negative,
                    "arousal": arousal + arousal_negative,
                    "dominance": dominance + dominance_negative,
                },
                timestamp=merged_impression_time,
            )

            # 清除过期的印象
            self.interactions = deque(
                [
                    interaction
                    for interaction in self.interactions
                    if (datetime.now() - interaction.timestamp).total_seconds() / 3600 < 5
                ]
            )
            # 添加合并的印象
            self.interactions.append(merged_impression)

    def update_emotion_tends(self):
        """
        更新情感倾向
        """

        # 从相识到现在，已经经过了多少岁月？时间恒久流动着，不会停下
        now = datetime.now()

        # 总印象
        valence = 0.0
        valence_negative = 0.0
        arousal = 0.0
        arousal_negative = 0.0
        dominance = 0.0
        dominance_negative = 0.0

        # 从印象中计算得出对这个人的情感倾向
        for impression in self.interactions:
            # 计算距离印象的时间
            elapsed_time = now - impression.timestamp
            elapsed_hours = elapsed_time.seconds / 3600.0

            # 衰减印象的愉悦度，无论好坏
            # 愉悦总是短暂的，厌恶却会在心中挥之不去
            decayed_valence = decay_valence(elapsed_hours, impression.delta.get("valence", 0.0))

            # 衰减印象的激活度
            # 在疯狂降临之前，无论是极度恐惧还是极度兴奋，都会很快平复
            decayed_arousal = decay_arousal(elapsed_hours, impression.delta.get("arousal", 0.0))

            # 衰减印象的支配度
            # 支配度在日积月累中形成，不会轻易改变
            decayed_dominance = decay_dominance(elapsed_hours, impression.delta.get("dominance", 0.0))

            # 计算出的情感也是情感
            if decayed_valence > 0:
                valence = max(valence, decayed_valence)
            else:
                valence_negative = min(valence_negative, decayed_valence)

            if decayed_arousal > 0:
                arousal = max(arousal, decayed_arousal)
            else:
                arousal_negative = min(arousal_negative, decayed_arousal)

            if decayed_dominance > 0:
                dominance = max(dominance, decayed_dominance)
            else:
                dominance_negative = min(dominance_negative, decayed_dominance)

        # 于第七日赐以尊严
        self.emotion = EmotionState(
            valence=valence + valence_negative,
            arousal=arousal + arousal_negative,
            dominance=dominance + dominance_negative,
        )


def decay_valence(
    elapsed_hours: float, valence: float, decay_rate_positive: float = 0.15, decay_rate_negative: float = 0.05
) -> float:
    """
    愉悦度随时间衰减，负面情绪恢复更慢。

    参数:
        elapsed_hours (float): 距离事件过去的时间，单位小时
        valence (float): 当前愉悦度，范围 [-1, 1]
        decay_rate_positive (float): 正向情绪衰减速度（越大衰减越快）
        decay_rate_negative (float): 负向情绪衰减速度（越小衰减越慢）

    返回:
        float: 经过衰减后的 valence
    """
    if valence > 0:
        rate = decay_rate_positive
    elif valence < 0:
        rate = decay_rate_negative
    else:
        return 0.0
    return valence * math.exp(-rate * elapsed_hours)


def decay_arousal(elapsed_hours: float, arousal: float, target: float = 0.3, decay_rate: float = 0.2) -> float:
    """
    激活度随时间逐渐恢复到 target 的过程。

    参数:
        elapsed_hours (float): 距离事件过去的时间（单位小时）
        arousal (float): 当前 arousal 值（范围 0.0 ~ 1.0）
        target (float): arousal 的恢复目标值（默认 0.3）
        decay_rate (float): 恢复速度（越大恢复越快）

    返回:
        float: 经过衰减后的 arousal 值
    """
    decay = math.exp(-decay_rate * elapsed_hours)
    return arousal * decay + target * (1 - decay)


def decay_dominance(elapsed_hours: float, dominance: float, target: float = 0.5, decay_rate: float = 0.03) -> float:
    """
    支配度随时间缓慢回归中性

    参数:
        elapsed_hours (float): 距离事件的时间（小时）
        dominance (float): 当前支配度
        target (float): 恢复目标
        decay_rate (float): 趋于中性的速度

    返回:
        float: 衰减后的 dominance 值
    """
    decay = math.exp(-decay_rate * elapsed_hours)
    return dominance * decay + target * (1 - decay)
