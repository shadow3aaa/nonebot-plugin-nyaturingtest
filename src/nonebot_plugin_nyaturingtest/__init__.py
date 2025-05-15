import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
import random
import re
import ssl
import traceback

import anyio
import httpx
from nonebot import logger, on_command, on_message
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from openai import OpenAI

from .client import LLMClient
from .config import Config, plugin_config
from .image_manager import IMAGE_CACHE_DIR, image_manager
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


async def is_private_message(event: Event) -> bool:
    return isinstance(event, PrivateMessageEvent)


@dataclass
class GroupState:
    event: Event | None = None
    bot: Bot | None = None
    session: Session = field(
        default_factory=lambda: Session(siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
    )
    messages_chunk: list[MMessage] = field(default_factory=list)
    client = LLMClient(
        client=OpenAI(
            api_key=plugin_config.nyaturingtest_chat_openai_api_key,
            base_url=plugin_config.nyaturingtest_chat_openai_base_url,
        )
    )
    lock = asyncio.Lock()


_tasks: set[asyncio.Task] = set()


async def spawn_state(state: GroupState):
    """
    启动后台任务循环检查是否要回复
    """
    while True:
        await asyncio.sleep(random.uniform(5.0, 10.0))  # 随机等待5-10秒模拟人类查看消息和理解，并且避免看不到连续消息
        async with state.lock:
            if state.bot is None or state.event is None:
                continue
            if len(state.messages_chunk) == 0:
                continue
            logger.debug(f"Processing message chunk: {state.messages_chunk}")
            messages_chunk = state.messages_chunk.copy()
            state.messages_chunk.clear()
            try:
                responses = state.session.update(
                    messages_chunk=messages_chunk, llm=lambda x: llm_response(state.client, x)
                )
            except Exception as e:
                logger.error(f"Error: {e}")
                traceback.print_exc()
                continue
            if responses:
                for response in responses:
                    await state.bot.send(message=response, event=state.event)


group_states: dict[int, GroupState] = {}

help = on_command(rule=is_group_message, permission=SUPERUSER, cmd="help", aliases={"帮助"}, priority=0, block=True)
help_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="help", aliases={"帮助"}, priority=0, block=True
)
get_status = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="status", aliases={"状态"}, priority=0, block=True
)
get_status_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="status", aliases={"状态"}, priority=0, block=True
)
auto_chat = on_message(rule=is_group_message, priority=1, block=False)
set_role = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="set_role", aliases={"设置角色"}, priority=0, block=True
)
set_role_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="set_role", aliases={"设置角色"}, priority=0, block=True
)
get_role = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="role", aliases={"当前角色"}, priority=0, block=True
)
get_role_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="role", aliases={"当前角色"}, priority=0, block=True
)
calm_down = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="calm", aliases={"冷静"}, priority=0, block=True
)
calm_down_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="calm", aliases={"冷静"}, priority=0, block=True
)
reset = on_command(rule=is_group_message, permission=SUPERUSER, cmd="reset", aliases={"重置"}, priority=0, block=True)
reset_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="reset", aliases={"重置"}, priority=0, block=True
)
get_presets = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="presets", aliases={"preset"}, priority=0, block=True
)
get_presets_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="presets", aliases={"preset"}, priority=0, block=True
)
set_presets = on_command(
    rule=is_group_message, permission=SUPERUSER, cmd="set_preset", aliases={"set_presets"}, priority=0, block=True
)
set_presets_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="set_preset", aliases={"set_presets"}, priority=0, block=True
)
list_groups_pm = on_command(
    rule=is_private_message, permission=SUPERUSER, cmd="list_groups", aliases={"群组列表"}, priority=0, block=True
)


@get_presets.handle()
async def handle_get_presets(event: GroupMessageEvent):
    await do_get_presets(get_presets, event.group_id)


@get_presets_pm.handle()
async def handle_get_presets_pm(args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg == "":
        await get_presets_pm.finish("请提供<qq群号>")
    group_id = int(arg)
    await do_get_presets(get_presets_pm, group_id)


async def do_get_presets(matcher: type[Matcher], group_id: int):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)

    async with group_states[group_id].lock:
        state = group_states[group_id]
        presets = state.session.presets()
    msg = "可选的预设:\n"
    for preset in presets:
        msg += f"- {preset}\n"
    msg += "使用方法: set_presets <预设名称>\n"
    await matcher.finish(msg)


@set_presets.handle()
async def handle_set_presets(event: GroupMessageEvent, args: Message = CommandArg()):
    file = args.extract_plain_text().strip()
    if file == "":
        await set_presets.finish("请提供<预设文件名>")
    group_id = event.group_id
    await do_set_presets(set_presets, group_id, file)


@set_presets_pm.handle()
async def handle_set_presets_pm(args: Message = CommandArg()):
    preset_args = args.extract_plain_text().strip().split(" ", 1)
    if len(preset_args) != 2:
        await set_presets_pm.finish("请提供<qq群号> <预设文件名>")
    group_id = int(preset_args[0])
    file = preset_args[1]

    await do_set_presets(set_presets_pm, group_id, file)


async def do_set_presets(matcher: type[Matcher], group_id: int, file: str):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
        if state.session.load_preset(filename=file):
            await matcher.finish(f"预设已加载: {file}")
        else:
            await matcher.finish(f"不存在的预设: {file}")


@help.handle()
async def handle_help():
    help_message = """
可用命令:
1. set_role <角色名> <角色设定> - 设置角色
2. role - 获取当前角色
3. calm - 冷静
4. reset - 重置会话
5. status - 获取状态
6. presets - 获取可用预设
7. help - 显示本帮助信息
",
"""
    await help.finish(help_message)


@help_pm.handle()
async def handle_help_pm():
    help_message = """
可用命令:
1. set_role <群号> <角色名> <角色设定> - 设置角色
2. role <群号> - 获取当前角色
3. calm <群号> - 冷静
4. reset <群号> - 重置会话
5. status <群号> - 获取状态
6. presets <群号> - 获取可用预设
7: list_groups - 获取启用nyabot的群组列表
8. help - 显示本帮助信息
",
"""
    await help_pm.finish(help_message)


@set_role.handle()
async def handle_set_role(event: GroupMessageEvent, args: Message = CommandArg()):
    role_args = args.extract_plain_text().strip().split(" ")
    if len(role_args) != 2:
        await set_role.finish("请提供<角色名> <角色设定>")
    group_id = event.group_id
    name = role_args[0]
    role = role_args[1]
    await do_set_role(set_role, group_id, name, role)


@set_role_pm.handle()
async def handle_set_role_pm(args: Message = CommandArg()):
    role_args = args.extract_plain_text().strip().split(" ")
    if len(role_args) != 3:
        await set_role_pm.finish("请提供<群号> <角色名> <角色设定>")
    group_id = int(role_args[0])
    name = role_args[1]
    role = role_args[2]
    await do_set_role(set_role_pm, group_id, name, role)


async def do_set_role(matcher: type[Matcher], group_id: int, name: str, role: str):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
        state.session.set_role(name=name, role=role)
    await matcher.finish(f"角色已设为: {name}\n设定: {role}")


@get_role.handle()
async def handle_get_role(event: GroupMessageEvent):
    group_id = event.group_id
    await do_get_role(get_role, group_id)


@get_role_pm.handle()
async def handle_get_role_pm(args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg == "":
        await get_role_pm.finish("请提供<群号>")
    group_id = int(arg)
    await do_get_role(get_role_pm, group_id)


async def do_get_role(matcher: type[Matcher], group_id: int):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
        role = state.session.role()
    await matcher.finish(f"当前角色: {role}")


@calm_down.handle()
async def handle_calm_down(event: GroupMessageEvent):
    group_id = event.group_id
    await do_calm_down(calm_down, group_id)


@calm_down_pm.handle()
async def handle_calm_down_pm(args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg == "":
        await calm_down_pm.finish("请提供<群号>")
    group_id = int(arg)
    await do_calm_down(calm_down_pm, group_id)


async def do_calm_down(matcher: type[Matcher], group_id: int):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
        state.session.calm_down()
    await matcher.finish("已老实")


@reset.handle()
async def handle_reset(event: GroupMessageEvent):
    group_id = event.group_id
    await do_reset(reset, group_id)


@reset_pm.handle()
async def handle_reset_pm(args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg == "":
        await reset_pm.finish("请提供<群号>")
    group_id = int(arg)
    await do_reset(reset_pm, group_id)


async def do_reset(matcher: type[Matcher], group_id: int):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
        state.session.reset()
    await matcher.finish("已重置会话")


@get_status.handle()
async def handle_status(event: GroupMessageEvent):
    group_id = event.group_id
    await do_status(get_status, group_id)


@get_status_pm.handle()
async def handle_status_pm(args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg == "":
        await get_status_pm.finish("请提供<群号>")
    group_id = int(arg)
    await do_status(get_status_pm, group_id)


async def do_status(matcher: type[Matcher], group_id: int):
    if group_id not in group_states:
        allowed_groups = plugin_config.nyaturingtest_enabled_groups
        if group_id not in allowed_groups:
            return

        # 如果第一次创建会话，拉起循环处理线程
        if group_id not in group_states:
            group_states[group_id] = GroupState(
                session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
            )
            global _tasks
            task = asyncio.create_task(spawn_state(state=group_states[group_id]))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    async with group_states[group_id].lock:
        state = group_states[group_id]
    await matcher.finish(state.session.status())


@list_groups_pm.handle()
async def handle_list_groups_pm():
    allowed_groups = plugin_config.nyaturingtest_enabled_groups
    if not allowed_groups:
        await list_groups_pm.finish("没有启用的群组")
    msg = "启用的群组:\n"
    for group_id in allowed_groups:
        msg += f"- {group_id}\n"
    await list_groups_pm.finish(msg)


def llm_response(client: LLMClient, message: str) -> str:
    try:
        result = client.generate_response(prompt=message, model=plugin_config.nyaturingtest_chat_openai_model)
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
            session=Session(id=f"{group_id}", siliconflow_api_key=plugin_config.nyaturingtest_siliconflow_api_key)
        )
        global _tasks
        task = asyncio.create_task(spawn_state(state=group_states[group_id]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)

    user_id = event.get_user_id()
    async with group_states[group_id].lock:
        message_content = await message2BotMessage(
            bot_name=group_states[group_id].session.name(), group_id=group_id, message=event.original_message, bot=bot
        )
    if not message_content:
        return

    # 获取用户的昵称
    try:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(user_id))
        nickname = user_info.get("card") or user_info.get("nickname") or str(user_id)
    except Exception:
        nickname = str(user_id)

    # 获取该群的状态
    async with group_states[group_id].lock:
        group_states[group_id].event = event
        group_states[group_id].bot = bot
        group_states[group_id].messages_chunk.append(
            MMessage(
                time=datetime.now(),
                user_name=nickname,
                content=message_content,
            )
        )


async def message2BotMessage(bot_name: str, group_id: int, message: Message, bot: Bot) -> str:
    """
    将消息转换为机器人可读的消息
    """
    message_content = ""

    for seg in message:
        if seg.type == "text":
            message_content += f"{seg.data.get('text', '')}"
        elif seg.type == "image" or seg.type == "emoji":
            try:
                url = seg.data.get("url", "")
                logger.debug(f"Image URL: {url}")

                # 缓存临时目录
                cache_path = IMAGE_CACHE_DIR.joinpath("raw")
                cache_path.mkdir(parents=True, exist_ok=True)

                key = re.search(r"[?&]fileid=([a-zA-Z0-9_-]+)", url)
                if key:
                    key = key.group(1)
                    logger.debug(f"Image cache key: {key}")
                else:
                    key = None
                    logger.warning("URL中没有找到rkey参数，无法缓存图片")

                if key and cache_path.joinpath(key).exists():
                    async with await anyio.open_file(cache_path.joinpath(key), "rb") as f:
                        image_bytes = await f.read()
                else:
                    # 哈基qq欠安全了
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                    ssl_context.set_ciphers("ALL:@SECLEVEL=1")
                    async with httpx.AsyncClient(verify=ssl_context) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                        image_bytes = response.content
                    # 缓存
                    if key:
                        async with await anyio.open_file(cache_path.joinpath(key), "wb") as f:
                            await f.write(image_bytes)

                is_sticker = seg.data.get("sub_type") == 1
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                description = image_manager.get_image_description(image_base64=image_base64, is_sticker=is_sticker)
                if description:
                    if is_sticker:
                        message_content += f"\n[表情包] [情感:{description.emotion}] [内容:{description.description}]\n"
                    else:
                        message_content += f"\n[图片] {description.description}\n"
            except Exception as e:
                logger.error(f"Error: {e}")
                message_content += "\n[图片/表情，网卡了加载不出来]\n"
        elif seg.type == "at":
            id = seg.data.get("qq")
            if not id:
                continue
            if id == str(bot.self_id):
                # 由于机器人名并不等于qq群名，这里覆盖为设定名(bot_name)
                message_content += f" @{bot_name} "
            else:
                user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(id))
                nickname = user_info.get("card") or user_info.get("nickname") or str(id)
                message_content += f" @{nickname} "
        elif seg.type == "reply":
            # TODO: 处理回复消息
            message_content += ""
        else:
            logger.warning(f"Unknown message type: {seg.type}")

    return message_content.strip()
