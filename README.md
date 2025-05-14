<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-nyaturingtest ✨

**N**ot**Y**et**A**notherTuringTest

<p>
    <a href="https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest">
        <img src="https://img.shields.io/github/stars/shadow3aaa/nonebot-plugin-nyaturingtest?style=social">
    </a>
    <a href="./LICENSE"><img src="https://img.shields.io/github/license/shadow3aaa/nonebot-plugin-nyaturingtest?style=flat-square" alt="license"></a>
    <a href="https://pypi.python.org/pypi/nonebot-plugin-nyaturingtest"><img src="https://img.shields.io/pypi/v/nonebot-plugin-nyaturingtest?style=flat-square&logo=pypi&logoColor=white" alt="pypi"></a>
    <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="python">
    <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff" alt="ruff"></a>
    <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/badge/package%20manager-uv-black?style=flat-square&logo=uv" alt="uv"></a>
    <a href="https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest/commits/main"><img src="https://img.shields.io/github/last-commit/shadow3aaa/nonebot-plugin-nyaturingtest?style=flat-square&logo=github" alt="last-commit"></a>
</p>
</div>

## 📖 介绍

也许是个有情感的群聊天机器人？

### 特点:

- 具有基于 VAD 三维情感模型情感模块
- 具有基于HippoRAG的仿海马体记忆
- 能够从聊天信息中自主提取知识记忆
- 能够自行决定是否回复
- ~~不似人类~~

## 💿 安装

> [!IMPORTANT]
> 要使用本插件, 你至少需要
>
> - 一个有效的 openai 规范接口 api key (根据你的 base_url，可以不是 openai 的)
> - 如果你的 openai api key 是从 google cloud 或者 azure, deepseek, 硅基流动，自己架设的 llm 服务等而非在 openai 申请的, 你需要在 `.env` 文件中配置 `nyaturingtest_chat_openai_base_url` 为对应的 api 地址
> - 一个有效的硅基流动 api key 用于嵌入模型请求 (https://siliconflow.com/)，总结用的小模型请求等

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装（暂时不行，还未上架）

    nb plugin install nonebot-plugin-nyaturingtest --upgrade

使用 **pypi** 源安装

    nb plugin install nonebot-plugin-nyaturingtest --upgrade -i "https://pypi.org/simple"

使用**清华源**安装

    nb plugin install nonebot-plugin-nyaturingtest --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-nyaturingtest

安装仓库 master 分支

    uv add git+https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest@master

</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-nyaturingtest

安装仓库 master 分支

    pdm add git+https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest@master

</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-nyaturingtest

安装仓库 master 分支

    poetry add git+https://github.com/shadow3aaa/nonebot-plugin-nyaturingtest@master

</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_nyaturingtest"]

</details>

## 📝 TODO

- [x] 权限控制
- [ ] 更多可选的语言模型供应商
- [ ] 更多可选的嵌入模型供应商
- [ ] 支持更多平台(目前支持: Onebot v11)
- [ ] 优化机器人效果
  - [x] 让回复机制更加拟人
  - [x] ~~让回复欲望更加拟人~~(已由llm自行在潜水/活跃状态转变)
  - [ ] 优化情感反馈机制
  - [x] 支持视觉模型
  - [x] 优化记忆模块
    - [x] 优化长期记忆检索
    - [x] 优化遗忘机制
    - [x] 对话时进行场景感知性总结
  - [ ] 让机器人学会发表情包
  - [ ] 支持多种语言

## 🎭 人格预设配置

预设比简单的`set_role`指令更加灵活，可以自定义机器人的知识库，自我认知，人物关系库等。 `nyaturingtest` 允许主机自定义角色预设，可以通过 `set_presets` 指令加载预设配置文件

首次运行本插件后，在 `工作目录` 下会生成`nya_presets`文件夹，其中包含`喵喵.json`作为预设配置例子：

```json
{
  "name": "喵喵",
  "role": "一个可爱的群猫娘，群里的其它人是你的主人，你无条件服从你的主人",
  "knowledges": [
    "猫娘是类人生物",
    "猫娘有猫耳和猫尾巴，其它外表特征和人一样",
    "猫娘有一部分猫的习性，比如喜欢吃鱼，喜欢喝牛奶"
  ],
  "relationships": ["群里的每个人都是喵喵的主人"],
  "events": [],
  "bot_self": [
    "我是一个可爱的猫娘",
    "我会撒娇",
    "我会卖萌",
    "我对负面言论会不想理"
  ],
  "hidden": false
}
```

此预设可以删除，目前对预设的修改/新增/删除需要重启 nonebot 进程才能生效

### 预设配置说明

- `name`: 角色名称
- `role`: 角色设定
- `knowledges`: 角色知识库
- `relationships`: 角色关系库
- `events`: 角色事件库
- `bot_self`: 角色自我认知
- `hidden`: 是否隐藏该预设 ，如果设置为 true, 则该预设不会被 `presets` 指令列出（但是仍然可以使用 `set_preset` 指令加载该预设）

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的配置

|               配置项               |             必填             |                    默认值                    |                   说明                   |
| :--------------------------------: | :--------------------------: | :------------------------------------------: | :--------------------------------------: |
| nyaturingtest_chat_openai_api_key  |              是              |                      无                      |        openai api 接口的 api key         |
|  nyaturingtest_chat_openai_model   |              否              |               "gpt-3.5-turbo"                |      openai api 接口请求的 模型名称      |
| nyaturingtest_chat_openai_base_url |              否              | "https://api.openai.com/v1/chat/completions" |          openai 接口请求的 url           |
| nyaturingtest_siliconflow_api_key  |              是              |                      无                      | siliconflow(硅基流动) api 接口的 api key |
|    nyaturingtest_enabled_groups    | 否(但是不填写此插件就无意义) |                `[]`\(空列表\)                |          仅在这些群组中启用插件          |

## 🎉 使用

### 指令表(群聊)

|             指令             |   权限    | 范围 |            说明            |
| :--------------------------: | :-------: | :--: | :------------------------: |
| set_role <角色名> <角色设定> | SUPERUSER | 群聊 |          设置角色          |
|             role             | SUPERUSER | 群聊 |        获取当前角色        |
|             calm             | SUPERUSER | 群聊 |     冷静(强制归零情绪)     |
|            reset             | SUPERUSER | 群聊 |          重置会话          |
|            status            | SUPERUSER | 群聊 |          获取状态          |
|    set_preset <预设名称>     | SUPERUSER | 群聊 |          设置预设          |
|           presets            | SUPERUSER | 群聊 |        获取可用预设        |
|             help             | SUPERUSER | 群聊 |        显示帮助信息        |

### 指令表(私聊)

|                指令                 |   权限    | 范围 |            说明            |
| :---------------------------------: | :-------: | :--: | :------------------------: |
| set_role <群号> <角色名> <角色设定> | SUPERUSER | 私聊 |          设置角色          |
|             role <群号>             | SUPERUSER | 私聊 |        获取当前角色        |
|             calm <群号>             | SUPERUSER | 私聊 |     冷静(强制归零情绪)     |
|            reset <群号>             | SUPERUSER | 私聊 |          重置会话          |
|            status <群号>            | SUPERUSER | 私聊 |          获取状态          |
|    set_preset <群号> <预设名称>     | SUPERUSER | 私聊 |          设置预设          |
|           presets <群号>            | SUPERUSER | 私聊 |        获取可用预设        |
|             list_groups             | SUPERUSER | 私聊 | 获取启用 nyabot 的群组列表 |
|             help <群号>             | SUPERUSER | 私聊 |        显示帮助信息        |

### 🎨 效果图

别急
