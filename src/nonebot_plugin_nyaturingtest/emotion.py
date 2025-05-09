from dataclasses import dataclass


@dataclass
class EmotionState:
    """
    情感状态:
    情感状态使用VAD模型表示, 包含三个维度: 愉悦度(valence)、唤醒度(arousal)和支配度(dominance)。
    - 愉悦度(valence): 表示情感的正负向程度，范围为[-1.0, 1.0]。
    - 唤醒度(arousal): 表示情感的激活程度，范围为[0.0, 1.0]。
    - 支配度(dominance): 表示情感的控制程度，范围为[-1.0, 1.0]。
    """

    valence: float = 0.0
    """
    愉悦度(valence): 表示情感的正负向程度，范围为[-1.0, 1.0]。
    """

    arousal: float = 0.0
    """
    唤醒度(arousal): 表示情感的激活程度，范围为[0.0, 1.0]。
    """

    dominance: float = 0.0
    """
    支配度(dominance): 表示情感的控制程度，范围为[-1.0, 1.0]。
    """
