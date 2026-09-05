# 理疗机器人客户端协作规则

本目录是理疗机器人客户端第一阶段工程：Vue 3/Vite 前端、FastAPI 后端和 SQLite 数据库，目前以本机演示部署为主。

## 如何运行

- PyCharm：使用共享运行配置 `.run\第一阶段-FastAPI.run.xml`。
- 命令行：在 `backend` 目录运行 `.venv\Scripts\python.exe run_first_stage.py`。
- 验证：访问 `http://127.0.0.1:8000/health`、首页和 `/docs`。
- Docker 傻瓜路线：保持 FlClash 已连接，双击 `Docker_One_Click.cmd`；首次构建或重建选 `1`，脚本会自动检测 `127.0.0.1:7890`。
- Docker 验证地址：`http://127.0.0.1:8080/health`；未经运行证据不得标为完成。

## 目录与约定

- `backend\`：FastAPI、SQLite 数据及本地 Python 虚拟环境。
- `frontend\`：Vue 3/Vite 源码。
- `运维脚本\`：本机安装脚本与日志。
- `DEPLOY.md`：产品部署说明；`部署步骤记录.md`：这台电脑的唯一实际进度账本。
- `Docker傻瓜式操作教程.md`：无需 Codex 的 Windows 操作手册；菜单日志写入 `logs\docker-easy-menu-*.log`。
- 数据库备份：双击 `Docker_Backup_Restore.cmd`；操作边界和恢复步骤见 `Docker备份恢复教程.md`。
- 修改文件使用小范围补丁；保留用户已有配置和数据，不擅自删除工作区残留。
- 数据库迁移或覆盖前先备份；账号、令牌、密钥和真实密码不得写进文档。
- Docker 数据应放在 E 盘；公网端口、安全策略及生产密钥需单独审查。

## 当前状态与下一步

- 已完成：Windows 11 Pro 25H2、本地 Python 3.11 演示、PyCharm 运行配置。
- 已完成：WSL 2.7.11 与 Ubuntu 24.04（WSL 2，数据在 `E:\WSL\Ubuntu-24.04`）。
- 已完成：Docker Desktop 4.86.0（WSL 2 后端，数据在 `E:\Docker\wsl`）。
- 已完成：Dockerfile、Compose、密钥生成、数据库初始化和 FlClash 代理自检；一键菜单静态自检通过。
- 已完成：第一阶段 Docker 镜像构建和本机运行验证；前后端容器健康，入口为 `127.0.0.1:8080`。
- 已完成：SQLite 在线备份和隔离 Docker 卷恢复演练；备份保存在 `backups\docker-sqlite`。
- 已完成：前端依赖安全升级，`npm audit`、Docker 生产构建、登录和资料 API 回归均通过。
- 已完成：当前用户登录时启动 Docker、每天 20:00 自动备份；两个 Windows 计划任务均已试跑通过。
- 已完成：Windows 实际重启后 Docker Desktop 与前后端容器自动恢复，健康检查和重新登录通过。
- 下一步：接入独立物理盘或网络存储后补异盘副本；再决定局域网和防火墙开放范围。
- 未完成：真实机器人 SDK/协议与安全联锁；异盘备份与断电测试；局域网开放；Secure Boot 当前关闭。
