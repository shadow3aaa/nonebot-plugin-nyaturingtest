import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import random

from google import genai
from nonebot import logger, on_command, on_message
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    GroupMessageEvent,
)
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from openai import OpenAI

from .client import LLMClient
from .config import Config, plugin_config
from .mem import Message as MMessage
from .session import Session

__plugin_meta__ = PluginMetadata(
    name="NYATuringTest",
    description="群聊特化llm聊天机器人，具有长期记忆和情绪模拟能力",
    usage="群聊特化llm聊天机器人，具有长期记忆和情绪模拟能力",
    type="application",
    homepage="https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "shadow3aaa <shadow3aaaa@gmail.com>"},
)


async def is_group_message(event: Event) -> bool:
    return isinstance(event, GroupMessageEvent)


@dataclass
class GroupState:
    event: Event | None = None
    bot: Bot | None = None
    session: Session = field(
        default_factory=lambda: Session(siliconflow_api_key=plugin_config.nyaturingtest_embedding_siliconflow_api_key)
    )
    messages_chunk: list[MMessage] = field(default_factory=list)
    client = LLMClient(
        client=OpenAI(
            api_key=plugin_config.nyaturingtest_chat_openai_api_key,
            base_url=plugin_config.nyaturingtest_chat_openai_base_url,
        )
    )


_tasks: set[asyncio.Task] = set()


async def spawn_state(state: GroupState):
    """
    启动后台任务循环检查是否要回复
    """
    while True:
        await asyncio.sleep(random.uniform(5.0, 10.0))  # 随机等待5-10秒模拟人类查看消息和理解，并且避免看不到连续消息
        if state.bot is None or state.event is None:
            continue
        if len(state.messages_chunk) == 0:
            continue

        logger.debug(f"Processing message chunk: {state.messages_chunk}")
        messages_chunk = state.messages_chunk.copy()
        state.messages_chunk.clear()
        try:
            responses = state.session.update(messages_chunk=messages_chunk, llm=lambda x: llm_response(state.client, x))
        except Exception as e:
            logger.error(f"Error: {e}")
            responses = ["发生错误，请稍后再试。"]
        if responses:
            for response in responses:
                await state.bot.send(message=response, event=state.event)


group_states: dict[int, GroupState] = {}

help = on_command(rule=is_group_message, cmd="help", aliases={"帮助"}, priority=0, block=True)
get_status = on_command(rule=is_group_message, cmd="status", aliases={"状态"}, priority=0, block=True)
auto_chat = on_message(rule=is_group_message, priority=1, block=False)
set_role = on_command(rule=is_group_message, cmd="set_role", aliases={"设置角色"}, priority=0, block=True)
get_role = on_command(rule=is_group_message, cmd="role", aliases={"当前角色"}, priority=0, block=True)
calm_down = on_command(rule=is_group_message, cmd="calm", aliases={"冷静"}, priority=0, block=True)
reset = on_command(rule=is_group_message, cmd="reset", aliases={"重置"}, priority=0, block=True)
get_provider = on_command(rule=is_group_message, cmd="provider", priority=0, block=True)
set_provider = on_command(rule=is_group_message, cmd="set_provider", priority=0, block=True)
get_presets = on_command(rule=is_group_message, cmd="presets", priority=0, block=True)
set_presets = on_command(rule=is_group_message, cmd="set_presets", priority=0, block=True)


@get_presets.handle()
async def handle_get_presets(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await get_presets.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        presets = state.session.presets()
        msg = "可选的预设:\n"
        for preset in presets:
            msg += f"- {preset}\n"
        msg += "使用方法: set_presets <预设名称> <预设内容>\n"
        await get_presets.finish(msg)


@set_presets.handle()
async def handle_set_presets(event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = event.group_id
    if group_id not in group_states:
        await set_presets.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        if arg := args.extract_plain_text().strip():
            if state.session.load_preset(arg):
                await set_presets.finish(f"预设已加载: {arg}")
            else:
                await set_presets.finish(f"不存在的预设: {arg}")
        else:
            await set_presets.finish("请提供预设名称")


@get_provider.handle()
async def handle_get_provider(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await get_provider.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        provider = state.client.type
        await get_provider.finish(f"当前提供者: {provider}")


@set_provider.handle()
async def handle_set_provider(event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = event.group_id
    if group_id not in group_states:
        await set_provider.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        provider = args.extract_plain_text().strip()
        if provider in ["gemini", "openai"]:
            if provider == "gemini":
                state.client = LLMClient(client=genai.Client(api_key=plugin_config.nyaturingtest_chat_gemini_api_key))
            elif provider == "openai":
                state.client = LLMClient(
                    client=OpenAI(
                        api_key=plugin_config.nyaturingtest_chat_openai_api_key,
                        base_url=plugin_config.nyaturingtest_chat_openai_base_url,
                    )
                )
            await set_provider.finish(f"已设置提供者为: {provider}")
        else:
            await set_provider.finish("无效的提供者，请选择 'gemini' 或 'openai'")


@help.handle()
async def handle_help(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        return
    else:
        help_message = """
可用命令:
1. set_role <角色名> <角色设定> - 设置角色
2. role - 获取当前角色
3. calm - 冷静
4. reset - 重置会话
5. status - 获取状态
6. provider - 获取当前提供商
7. set_provider <提供者> - 设置提供商 (gemini/openai)
8. set_presets <预设名称> <预设内容> - 设置预设
9. presets - 获取可用预设
9. help - 显示本帮助信息
",
"""
        await help.finish(help_message)


@set_role.handle()
async def handle_set_role(event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = event.group_id
    if group_id not in group_states:
        await set_role.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        if arg := args.extract_plain_text().strip():
            role_rags = arg.split(" ", 1)
            if len(role_rags) == 2:
                state.session.set_role(role_rags[0], role_rags[1])
                await set_role.finish(f"角色已设为: {role_rags[0]}\n设定: {role_rags[1]}")
            else:
                await set_role.finish("请提供角色名和角色设定")
        else:
            await set_role.finish("请提供角色描述")


@get_role.handle()
async def handle_get_role(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await get_role.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        role = state.session.role()
        await get_role.finish(f"当前角色: {role}")


@calm_down.handle()
async def handle_calm_down(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await calm_down.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        state.session.calm_down()
        await calm_down.finish("已老实")


@reset.handle()
async def handle_reset(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await reset.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        state.session.reset()
        await reset.finish("已重置会话")


@get_status.handle()
async def handle_status(event: GroupMessageEvent):
    group_id = event.group_id
    if group_id not in group_states:
        await get_status.finish("No active session found for this group.")
    else:
        state = group_states[group_id]
        await get_status.finish(state.session.status())


def llm_response(client: LLMClient, message: str) -> str:
    try:
        result = client.generate_response(message)
        if result:
            return result
        else:
            return ""
    except Exception as e:
        logger.error(f"Error: {e}")
        return "Error occurred while processing the message."


@auto_chat.handle()
async def handle_auto_chat(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id

    # 暂时只在这些群测试
    allowed_groups = plugin_config.nyaturingtest_enabled_groups
    if group_id not in allowed_groups:
        return

    # 如果第一次创建会话，拉起循环处理线程
    if group_id not in group_states:
        group_states[group_id] = GroupState(
            session=Session(
                id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_embedding_siliconflow_api_key
            )
        )
        global _tasks
        task = asyncio.create_task(spawn_state(state=group_states[group_id]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)

    user_id = event.get_user_id()
    message_content = event.get_plaintext()
    if event.to_me:
        message_content = f"@{group_states[group_id].session.name()} {message_content}"

    # 获取用户的昵称
    try:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(user_id))
        nickname = user_info.get("card") or user_info.get("nickname") or str(user_id)
    except Exception:
        nickname = str(user_id)

    # 获取该群的状态
    group_states[group_id].event = event
    group_states[group_id].bot = bot
    group_states[group_id].messages_chunk.append(
        MMessage(
            time=datetime.now(),
            user_name=nickname,
            content=message_content,
        )
    )
