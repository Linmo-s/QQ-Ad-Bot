# QQ-Ad-Bot

基于 NoneBot2 + NapCat 的 QQ 群关键词计数广告自动发送机器人。监控群聊消息中的关键词，达到随机触发阈值后自动延迟发送广告图文消息，内置 Web 管理面板。

## 功能特性

- **关键词检测** — 监控群聊消息，匹配预设关键词（如"场照"、"接妆"、"接单"等）
- **随机阈值触发** — 每次发送后随机生成下一次触发阈值（默认 5-15 条），避免固定规律
- **延迟发送** — 触发后 30-90 秒随机延迟，模拟自然行为
- **模拟打字** — 发送前加入高斯分布的打字延迟（3-6 秒）
- **冷却时间** — 同一群最少间隔 2 小时才能再次发送
- **安静时段** — 默认凌晨 2:00-7:00 不发送消息
- **图文分开发送** — 支持文字和图片合并或分两条消息发送
- **Web 管理面板** — 可视化配置系统设置、群组管理、状态监控、NapCat 控制

## 技术栈

- Python 3.12 + NoneBot2（FastAPI 驱动）
- NapCat（QQ NT 协议适配，提供 OneBot v11 接口）
- FastAPI（管理面板 API）
- Pydantic（配置数据模型）
- APScheduler（延迟任务调度）

## 项目结构

```
QQ-Ad-Bot/
├── bot.py                              # 主入口，NoneBot2 启动与 NapCat 管理
├── requirements.txt                    # Python 依赖
├── resources/image/jd/jdt.jpg          # 广告图片
├── massages_image_massage/             # NoneBot2 插件（核心逻辑）
│   ├── __init__.py                     # 插件注册，挂载 FastAPI 路由
│   ├── config.py                       # 配置模型与持久化（Pydantic）
│   ├── handler.py                      # 群消息监听与关键词计数
│   ├── sender.py                       # 延迟发送逻辑（安静时段/冷却/模拟打字）
│   ├── web.py                          # 管理面板 REST API
│   ├── data/config.json                # 运行时配置文件
│   └── templates/index.html            # 管理面板前端页面
└── NapCat.Shell/                       # 内置 NapCat QQ 协议适配器
    ├── launcher.bat                    # NapCat 启动脚本
    └── config/                         # NapCat 配置文件
```

## 安装与运行

### 快速开始（新机器部署）

#### 前置要求
- Windows 10/11（64 位）
- Python 3.12+（安装时勾选"Add to PATH"）

#### 自动安装
1. 克隆或复制项目到本地
2. 双击 `setup.bat` 初始化环境（自动创建虚拟环境、安装依赖、生成配置）
3. 双击 `start.bat` 启动机器人
4. 打开 http://127.0.0.1:8080/adbot/ 配置和管理

### 手动安装

```bash
pip install -r requirements.txt
python bot.py
```

启动后程序会：
1. 读取 `massages_image_massage/data/config.json` 配置
2. 自动检测 `NapCat.Shell/` 目录并生成 OneBot v11 配置
3. 根据 `napcat_auto_start` 设置决定是否自动启动 NapCat
4. 在 `127.0.0.1:8080` 启动 NoneBot2

### NapCat QQ 登录

首次运行需通过管理面板扫码登录 QQ：
1. 打开管理面板（见下方）
2. 点击 NapCat 控制区的扫码登录按钮
3. 使用手机 QQ 扫描二维码

## Web 管理面板

- **地址**：`http://127.0.0.1:8080/adbot/`
- **默认账号**：`admin`
- **默认密码**：`admin123`

面板功能：
- 初始化向导（首次配置）
- 系统设置（端口、OneBot 连接方式、NapCat 参数）
- 全局插件设置（关键词、延迟范围、触发阈值、安静时段）
- 群组管理（启用/禁用、设置广告文案和图片、调整触发参数）
- 状态监控（群计数、发送日志、连接状态）

## 配置说明

所有运行时配置存储在 `massages_image_massage/data/config.json`，可通过管理面板修改。

### 系统配置

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `host` | NoneBot2 监听地址 | `127.0.0.1` |
| `port` | NoneBot2 监听端口 | `8080` |
| `connection_type` | OneBot 连接方式 | `reverse_ws` |
| `napcat_auto_start` | 是否自动启动 NapCat | `false` |
| `napcat_qq` | NapCat 绑定的 QQ 号 | — |

### 全局设置

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `keywords` | 监控关键词列表 | — |
| `schedule_delay_range` | 触发后延迟发送范围（秒） | `[30, 90]` |
| `typing_delay_range` | 模拟打字延迟范围（秒） | `[3, 6]` |
| `message_limit_range` | 触发阈值随机范围（条） | `[5, 15]` |
| `quiet_hours` | 安静时段 | `2:00 - 7:00` |

### 群组配置

每个群可独立配置：

| 字段 | 说明 |
|------|------|
| `enabled` | 是否启用 |
| `messages` | 广告文案列表（随机选择） |
| `image_path` | 广告图片路径 |
| `message_limit` | 触发阈值（覆盖全局） |
| `min_interval` | 最小发送间隔（秒） |
| `split_send` | 是否图文分开发送 |
