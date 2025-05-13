from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    nyaturingtest_chat_openai_api_key: str
    nyaturingtest_chat_openai_model: str = "gpt-3.5-turbo"
    nyaturingtest_chat_openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    nyaturingtest_siliconflow_api_key: str
    nyaturingtest_enabled_groups: list[int] = []


plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config
