from dataclasses import dataclass, field
import json
import os

from nonebot import logger


@dataclass
class RolePreset:
    name: str
    """
    角色名称
    """
    role: str
    """
    角色人设
    """
    knowledges: list[str] = field(default_factory=list)
    """
    预设知识
    """
    relationships: list[str] = field(default_factory=list)
    """
    预设人物关系
    """
    events: list[str] = field(default_factory=list)
    """
    预设了解的事件
    """
    bot_self: list[str] = field(default_factory=list)
    """
    预设对自我的认知
    """
    hidden: bool = False
    """
    是否在/presets输出隐藏预设
    """


_猫娘预设 = RolePreset(
    name="喵喵",
    role="一个可爱的群猫娘，群里的其它人是你的主人，你无条件服从你的主人",
    knowledges=[
        "猫娘是类人生物",
        "猫娘有猫耳和猫尾巴，其它外表特征和人一样",
        "猫娘有一部分猫的习性，比如喜欢吃鱼，喜欢喝牛奶",
    ],
    relationships=[
        "群里的每个人都是喵喵的主人",
    ],
    bot_self=[
        "我是一个可爱的猫娘",
        "我会撒娇",
        "我会卖萌",
        "我对负面言论会不想理",
    ],
)

PRESETS: dict[str, RolePreset] = {}


def _load_presets_from_directory(directory: str = "./nya_presets"):
    # 如果文件夹不存在就创建并且写入例子(_猫娘预设)
    if not os.path.exists(directory):
        os.makedirs(directory)
        with open(os.path.join(directory, "喵喵.json"), "w", encoding="utf-8") as f:
            json.dump(_猫娘预设.__dict__, f, ensure_ascii=False, indent=4)
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            path = os.path.join(directory, filename)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    preset = RolePreset(**data)
                    PRESETS[filename] = preset
            except Exception as e:
                logger.warning(f"无法加载预设 {filename}: {e}")


# 模块导入时自动加载外部预设
_load_presets_from_directory()
