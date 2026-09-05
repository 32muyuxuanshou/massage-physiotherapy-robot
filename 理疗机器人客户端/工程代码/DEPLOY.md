# 颐本智能理疗系统部署指南

- 版本：第一阶段本机演示版
- 更新日期：2026-08-11
- 当前权威进度：`部署步骤记录.md`
- Windows 傻瓜式操作：`Docker傻瓜式操作教程.md`
- 数据库备份与演练：`Docker备份恢复教程.md`

## 1. 当前部署边界

当前容器方案用于这台 Windows 11 电脑的本机第一阶段演示：

- 前端：Vue 3/Vite 构建后由 Nginx 提供；
- 后端：FastAPI/Uvicorn；
- 数据库：SQLite，保存在 Docker 命名数据卷；
- 容器后端：Docker Desktop + WSL 2；
- 主机仅监听 `127.0.0.1:8080`；
- 后端 8000 端口不直接发布到 Windows 网卡；
- Docker 数据位于 `E:\Docker\wsl`。

2026-08-10 本机验收：一键部署全链路退出码为 0，前后端容器均为 `healthy`，首页和 `/health` 均返回 HTTP 200。

2026-08-11 前端依赖安全升级：Axios 升至 1.19.0、Vite 升至 6.4.3，移除未配置且未使用的 ESLint 8；`npm audit` 和 Docker `npm ci` 均报告 0 个漏洞，生产构建、登录及用户资料 API 回归通过。

这不是公网生产部署。真实机器人 SDK/协议、安全联锁、HTTPS、正式账号、异机备份策略和公网安全审查尚未完成。

## 2. Windows 推荐部署方式

在项目根目录双击：

`Docker_One_Click.cmd`

第一次部署或代码修改后重建选择菜单 `1`。保持 FlClash 已连接；脚本会自动尝试直连和本机 `127.0.0.1:7890` 代理，直到窗口显示：

`DEPLOYMENT PASSED`

当前电脑已通过这条代理路线完成实际构建和健康验证。详细步骤和错误处理见 `Docker傻瓜式操作教程.md`。

菜单还提供：

| 选项 | 操作 |
|---|---|
| `1` | 第一次构建或重建 |
| `2` | 启动现有容器 |
| `3` | 停止容器并保留数据 |
| `4` | 查看状态和健康检查 |
| `5` | 打开网页 |
| `6` | 查看最近日志 |

## 3. 访问地址

| 功能 | 地址 |
|---|---|
| 系统首页 | `http://127.0.0.1:8080` |
| 健康检查 | `http://127.0.0.1:8080/health` |
| API | 由同源路径 `http://127.0.0.1:8080/api/v1/...` 转发 |

Docker 方案没有把后端 8000 端口直接暴露给主机，因此本机 Python 版的 `http://127.0.0.1:8000/docs` 不等于 Docker 版入口。

第一阶段演示账号：

- 手机号：`13800138000`
- 密码：`123456`

演示账号仅用于本机验证，禁止用于公网生产。

## 4. 配置和密钥

Compose 使用项目根目录的 `.env.docker`：

| 变量 | 当前用途 |
|---|---|
| `SECRET_KEY` | JWT 本机随机密钥，必填 |
| `APP_BIND_ADDRESS` | 默认 `127.0.0.1` |
| `APP_PORT` | 默认 `8080` |

一键脚本在文件不存在时自动生成随机 `SECRET_KEY`，不会把真实值打印到窗口或日志。

规则：

- 不要把 `.env.docker` 发给别人或截图；
- 不要把 `.env.docker.example` 的占位值直接用于运行；
- 删除或更换 `SECRET_KEY` 会使已有登录令牌失效；
- `backend\.env` 用于本机 Python 版，不会复制进 Docker 镜像。

## 5. 手动命令（仅供排障）

日常使用优先选择一键菜单。需要手动操作时，在项目根目录运行：

```powershell
# 校验 Compose
docker compose --env-file .env.docker config --quiet

# 构建并启动
docker compose --env-file .env.docker up -d --build

# 查看状态
docker compose --env-file .env.docker ps

# 查看日志
docker compose --env-file .env.docker logs --tail 100

# 停止但保留数据库卷
docker compose --env-file .env.docker down
```

不要执行下面的命令：

```powershell
docker compose down -v
```

其中 `-v` 会删除包含 SQLite 数据库的命名数据卷。

## 6. 容器启动顺序

1. 后端容器启动；
2. `python -m app.scripts.init_db` 创建表并按 `SEED_DEMO_DATA=true` 初始化本机演示数据；
3. 后端 `/health` 返回成功；
4. 前端容器启动；
5. Nginx 将 `/api/` 和 `/health` 转发给后端；
6. Windows 通过 `127.0.0.1:8080` 访问前端。

数据库、上传文件和日志分别使用命名数据卷：

- `backend-data`
- `backend-uploads`
- `backend-logs`

## 7. 网络故障处理

若出现 `Docker Hub authentication endpoint: FAILED`、`failed to fetch anonymous token` 或 `Could not pull`：

1. 打开 FlClash 并连接可用节点；
2. 确认本机 HTTP 代理仍为 `127.0.0.1:7890`；
3. 保持一键脚本窗口运行并输入 `R` 重试；
4. 仍失败时更换 FlClash 节点；
5. 手机热点只作为最后的备用路线。

已确认校园网直连会错误解析 Docker Hub；FlClash `127.0.0.1:7890` 已实测能访问认证端点并完成镜像、pip 和 npm 下载。

每次一键操作日志位于：

`logs\docker-easy-menu-日期时间.log`

## 8. 数据备份原则

2026-08-11 已完成一次真实在线备份和隔离 Docker 卷恢复演练。双击项目根目录：

`Docker_Backup_Restore.cmd`

选择菜单 `1` 会创建一致性 SQLite 备份、SHA-256 清单，并将备份恢复到临时 Docker 卷验证；现役数据库卷不会被覆盖。只有同时显示 `BACKUP PASSED` 和 `RESTORE DRILL PASSED` 才算成功。

备份位于 `backups\docker-sqlite`，完整操作见 `Docker备份恢复教程.md`。备份文件包含账号和业务数据，不得外发或提交到 Git。

当前已证明本机恢复链路可用；进入局域网或生产阶段前，仍需补充定期执行计划、异机/离线副本、保留周期和断电测试。不要手工删除 Docker 数据卷或 `E:\Docker\wsl`。

当前电脑已注册两个仅对当前 Windows 用户生效的计划任务：

- `Physiotherapy Client - Start Docker at Logon`：登录时启动 Docker Desktop；
- `Physiotherapy Client - Daily Database Backup`：每天 20:00 执行在线备份，错过时间时在电脑下次可用后补跑。

两个任务均已手动试跑且返回 0。自动备份不会删除旧备份。C、D、E 都位于同一块物理 NVMe，因此当前自动备份仍不能替代移动硬盘、NAS 或其他机器上的异机副本。

2026-08-11 实际重启验收：Windows 在 15:15:36 完成重启，登录启动任务在 15:15:44 返回 0；Docker Desktop 状态为 `running`，前后端容器自动恢复为 `healthy`，首页、`/health` 和演示账号登录均通过。

## 9. 本机 Python/PyCharm 回退路线

Docker 网络不可用时，本机第一阶段演示仍可使用：

```powershell
cd backend
.\.venv\Scripts\python.exe .\run_first_stage.py
```

访问：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

PyCharm 操作见 `PYCHARM使用教程.md`。

## 10. 进入生产前的必做项

- 关闭 `SEED_DEMO_DATA` 并移除演示账号；
- 接入真实机器人 SDK/协议和安全联锁；
- 建立正式用户与密码策略；
- 配置 HTTPS 和证书；
- 建立定期及异机备份，并完成断电测试；
- 明确局域网地址、防火墙白名单和最小端口；
- 开启并复查 Secure Boot；
- 做安全审计后再考虑对外联网。
