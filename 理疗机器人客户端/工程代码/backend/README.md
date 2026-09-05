# 颐本智能理疗系统后端

- 状态：第一阶段本机演示版已实现并通过本机 Python 冒烟测试
- 运行环境：Python 3.11
- 框架：FastAPI、SQLAlchemy 2、Pydantic 2、SQLite、JWT
- 当前限制：设备和理疗接口主要操作本地状态；AI 分析为演示逻辑；真实机器人通信尚未接入

## 本机 Python 运行

当前电脑已配置虚拟环境 `backend\.venv`。在本目录运行：

```powershell
.\.venv\Scripts\python.exe .\run_first_stage.py
```

也可从项目根目录使用 PyCharm 共享运行配置：

`.run\第一阶段-FastAPI.run.xml`

访问地址：

- 首页：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`
- Swagger：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`

数据库文件：

`backend\data\physiotherapy.db`

## Docker 运行

`backend` 目录不再保留独立 Compose 文件；当前完整部署入口只在项目根目录。

返回项目根目录，双击：

`Docker_One_Click.cmd`

第一次构建选择菜单 `1`，并保持 FlClash 已连接；脚本会自动使用本机 `127.0.0.1:7890` 代理。Docker 版统一入口：

`http://127.0.0.1:8080`

Docker 版后端 8000 端口只在 Compose 内部网络开放，通过 Nginx 的 `/api/` 和 `/health` 转发。完整说明见根目录：

- `Docker傻瓜式操作教程.md`
- `DEPLOY.md`
- `部署步骤记录.md`

## 演示账号

| 手机号 | 密码 | 范围 |
|---|---|---|
| `13800138000` | `123456` | 仅限本机第一阶段演示 |

进入局域网或生产前必须关闭演示数据初始化并替换正式账号策略。

## 主要接口

接口统一前缀：`/api/v1`

- `/auth`：登录和令牌相关接口
- `/users`：用户资料
- `/devices`：设备列表、详情和连接状态
- `/therapy`：理疗方法和理疗会话
- `/analysis`：第一阶段 AI 分析演示接口

本机 Python 版可在 Swagger 中查看当前代码实际暴露的完整 schema。

## 环境变量

配置由 `app/config.py` 的 Pydantic Settings 读取，本机默认读取 `backend\.env`。

| 变量 | 作用 | 当前默认/说明 |
|---|---|---|
| `ENV` | 环境名称 | `development` |
| `DEBUG` | 调试输出 | 本机默认开启，Docker 关闭 |
| `DATABASE_URL` | 数据库连接 | `sqlite:///./data/physiotherapy.db` |
| `SECRET_KEY` | JWT 密钥 | 正式运行必须使用随机值 |
| `REDIS_ENABLED` | Redis 开关 | 当前关闭 |
| `CORS_ORIGINS` | 允许来源 | 逗号分隔字符串 |
| `SEED_DEMO_DATA` | 是否写入演示账号和设备 | 默认关闭，第一阶段 Docker 显式开启 |

不要把真实 `.env` 或 `.env.docker` 复制进镜像、文档或聊天记录。

## 数据库初始化

创建表并按配置决定是否写入演示数据：

```powershell
.\.venv\Scripts\python.exe -m app.scripts.init_db
```

应用启动时也会创建缺失的表。数据库覆盖或迁移前必须先备份。

## 目录

```text
backend/
├── app/
│   ├── api/v1/       API 路由
│   ├── core/         安全等核心工具
│   ├── crud/         数据访问
│   ├── models/       SQLAlchemy 模型
│   ├── schemas/      Pydantic schema
│   ├── scripts/      数据库初始化脚本
│   ├── services/     业务逻辑
│   ├── config.py     环境配置
│   ├── database.py   数据库连接
│   └── main.py       FastAPI 入口
├── data/             本机 SQLite 数据
├── .venv/            当前本机 Python 虚拟环境
├── Dockerfile
├── requirements.txt
└── run_first_stage.py
```

`doc/` 下的长篇搭建提示词和开发稿保留为历史设计参考，不是当前部署操作手册。
