<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="./.docs/NoneBotPlugin.svg" width="300" alt="logo"></a>
</div>

<div align="center">

## ✨ nonebot-plugin-template ✨

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/owner/nonebot-plugin-template.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-template">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-template.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">
<a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json" alt="ruff">
</a>
<a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
</a>
</div>

## 📖 介绍

这里是插件的详细介绍部分

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-template --upgrade
使用 **pypi** 源安装

    nb plugin install nonebot-plugin-template --upgrade -i "https://pypi.org/simple"
使用**清华源**安装

    nb plugin install nonebot-plugin-template --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"


</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-template
安装仓库 master 分支

    uv add git+https://github.com/owner/nonebot-plugin-template@master
</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-template
安装仓库 master 分支

    pdm add git+https://github.com/owner/nonebot-plugin-template@master
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-template
安装仓库 master 分支

    poetry add git+https://github.com/owner/nonebot-plugin-template@master
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_template"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项  | 必填  | 默认值 |   说明   |
| :-----: | :---: | :----: | :------: |
| 配置项1 |  是   |   无   | 配置说明 |
| 配置项2 |  否   |   无   | 配置说明 |

## 🎉 使用
### 指令表
| 指令  | 权限  | 需要@ | 范围  |   说明   |
| :---: | :---: | :---: | :---: | :------: |
| 指令1 | 主人  |  否   | 私聊  | 指令说明 |
| 指令2 | 群员  |  是   | 群聊  | 指令说明 |

### 🎨 效果图
如果有效果图的话
