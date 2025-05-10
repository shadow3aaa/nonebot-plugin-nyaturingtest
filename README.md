<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-nyaturingtest ✨

#### **N**ot**Y**et**A**notherTuringTest

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
- 具有基于向量搜索的长期记忆和知识
- 能够从聊天信息中自主提取知识记忆
- 能够考虑自身的情感状态和记忆自行选择要不要回复和回复内容，比较拟人
- 能够对每个人类用户进行情感记忆
- ~~不似人类~~

## 💿 安装

> [!IMPORTANT]
> 要使用本插件, 你至少需要
>
> - 一个有效的 openai 规范接口 api key (根据你的 base_url，可以不是 openai 的)
> - 如果你的 openai api key 是从 google cloud 或者 azure, deepseek, 硅基流动，自己架设的 llm 服务等而非在 openai 申请的, 你需要在 `.env` 文件中配置 `nyaturingtest_chat_openai_base_url` 为对应的 api 地址
> - 一个有效的硅基流动 api key 用于嵌入模型请求 (https://siliconflow.com/)

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

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

- [ ] 权限控制
- [ ] 更多可选的语言模型供应商
- [ ] 更多可选的嵌入模型供应商
- [ ] 支持更多平台(目前支持: Onebot v11)
- [ ] 优化机器人效果
  - [ ] 让回复机制更加拟人
  - [ ] 让回复欲望更加拟人
  - [ ] 优化情感反馈机制
  - [ ] 支持视觉模型
  - [ ] 优化记忆模块
    - [ ] 优化长期记忆检索
    - [ ] 优化遗忘机制
    - [ ] 对话时进行场景感知性总结
  - [ ] 支持多种语言

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的配置

|                   配置项                    |             必填             |                    默认值                    |                   说明                   |
| :-----------------------------------------: | :--------------------------: | :------------------------------------------: | :--------------------------------------: |
|      nyaturingtest_chat_openai_api_key      |              是              |                      无                      |        openai api 接口的 api key         |
|       nyaturingtest_chat_openai_model       |              否              |               "gpt-3.5-turbo"                |      openai api 接口请求的 模型名称      |
|     nyaturingtest_chat_openai_base_url      |              否              | "https://api.openai.com/v1/chat/completions" |          openai 接口请求的 url           |
|      nyaturingtest_chat_gemini_api_key      |              否              |                      无                      |        gemini api 接口的 api key         |
| nyaturingtest_embedding_siliconflow_api_key |              是              |                      无                      | siliconflow(硅基流动) api 接口的 api key |
|        nyaturingtest_enabled_groups         | 否(但是不填写此插件就无意义) |                `[]`\(空列表\)                |          仅在这些群组中启用插件          |

## 🎉 使用

### 指令表

|             指令             |  权限  | 范围 |            说明            |
| :--------------------------: | :----: | :--: | :------------------------: |
| set_role <角色名> <角色设定> | 所有人 | 群聊 |          设置角色          |
|             role             | 所有人 | 群聊 |        获取当前角色        |
|             calm             | 所有人 | 群聊 |     冷静(强制归零情绪)     |
|            reset             | 所有人 | 群聊 |          重置会话          |
|            status            | 所有人 | 群聊 |          获取状态          |
|           provider           | 所有人 | 群聊 |       获取当前提供商       |
|    set_provider <提供者>     | 所有人 | 群聊 | 设置提供商 (gemini/openai) |
|    set_preset <预设名称>     | 所有人 | 群聊 |          设置预设          |
|           presets            | 所有人 | 群聊 |        获取可用预设        |
|             help             | 所有人 | 群聊 |        显示帮助信息        |

### 🎨 效果图

别急
