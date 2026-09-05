# Docker 傻瓜式操作教程

> 适用电脑：当前 Windows 11 主机。Docker Desktop、WSL 2 和 Ubuntu 已安装完成。本教程不需要 Codex，也不需要打开 PyCharm。

## 最重要的使用原则

南科大校园网直接访问 Docker Hub 时会得到错误 DNS 结果，但本机 FlClash 的 HTTP 代理 `127.0.0.1:7890` 已实际验证可用。因此采用下面的固定顺序：

1. 打开 FlClash，连接一个可用节点，并保持 FlClash 运行。
2. 双击 `Docker_One_Click.cmd`。
3. 选择菜单 `1`，脚本会先试校园网直连，再自动试 FlClash `127.0.0.1:7890`。
4. 直到窗口显示绿色的 `DEPLOYMENT PASSED` 才算完成。
5. 日常选择菜单 `2` 启动已有容器，通常不需要重新下载或构建。

不需要关闭 FlClash，也不需要拔校园网线。只有 FlClash 节点和 `7890` 代理都不可用时，才考虑手机热点。

## 第一次部署或代码修改后重建

1. 在资源管理器打开：

   `E:\项目-按摩理疗机器人\理疗机器人客户端\工程代码`

2. 双击：

   `Docker_One_Click.cmd`

3. 在黑色菜单窗口输入 `1`，按回车。

4. 保持 FlClash 已连接。脚本会自动检查直连和 `127.0.0.1:7890`，不需要手工改 DNS。

5. 脚本会自动完成：

   - 清理 DNS 缓存；
   - 检查 Docker Hub 是否真的可访问；
   - 必要时启动 Docker Desktop；
   - 拉取 Python、Node 和 Nginx 官方基础镜像；
   - 检查或生成 `.env.docker` 随机密钥；
   - 构建前端和后端镜像；
   - 初始化 SQLite 演示数据库；
   - 启动容器并等待健康检查；
   - 自动打开浏览器。

6. 只有出现绿色文字 `DEPLOYMENT PASSED` 才算成功。访问地址：

   `http://127.0.0.1:8080`

7. 成功后保持当前设置即可；已有镜像的日常启动通常可以离线完成。

第一次构建通常最慢。中途不要关闭黑色窗口、Docker Desktop 或电脑。

## 日常使用菜单

每次都双击 `Docker_One_Click.cmd`，然后选择：

| 选项 | 用途 | 网络要求 |
|---|---|---|
| `1` | 第一次部署，或代码修改后重建 | 保持 FlClash 已连接 |
| `2` | 启动已经构建好的容器 | 通常不需要网络 |
| `3` | 停止容器 | 不需要；数据库会保留 |
| `4` | 查看容器状态和健康检查 | 不需要 |
| `5` | 打开系统网页 | 不需要 |
| `6` | 查看最近 100 行日志 | 不需要 |
| `0` | 退出菜单 | 不需要 |

菜单的“停止”只停止容器，不会删除 SQLite 数据库和 Docker 数据卷。

当前 Windows 用户登录时，计划任务会自动启动 Docker Desktop；Compose 的 `restart: unless-stopped` 会恢复项目容器。如果开机后网页暂时打不开，先等待 Docker Desktop 启动，再用菜单 `4` 检查；不需要因此选择菜单 `1` 重建。

这条开机链路已在 2026-08-11 通过一次真实 Windows 重启验证：Docker Desktop、前后端容器、健康检查和登录均自动恢复。

## 数据库备份

Docker Desktop 和后端容器运行时，双击 `Docker_Backup_Restore.cmd`，选择菜单 `1`。看到 `BACKUP PASSED` 和 `RESTORE DRILL PASSED` 后，备份和隔离恢复演练才算完成。

备份保存在 `backups\docker-sqlite`。备份含有账号和业务数据，不要发给别人或上传公共网盘。详细说明见 `Docker备份恢复教程.md`。

每天 20:00 已有计划任务自动备份；手工选择备份菜单 `1` 主要用于修改数据库前或重要演示前。

## 账号与地址

- 系统首页：`http://127.0.0.1:8080`
- 健康检查：`http://127.0.0.1:8080/health`
- 第一阶段演示账号：`13800138000`
- 第一阶段演示密码：`123456`

演示账号只适用于本机第一阶段验证，不得用于公网生产。

## 常见错误怎么处理

### 1. `Docker Hub authentication endpoint: FAILED`

说明直连和 FlClash 代理都没有通过 Docker Hub HTTPS 检查。

1. 打开 FlClash，确认已连接可用节点。
2. 确认 `FlClashCore` 正在运行；本机代理端口应为 `7890`。
3. 在脚本窗口输入 `R` 重试。
4. 仍失败时换 FlClash 节点；最后才切换手机热点。
5. 不要反复修改 Windows DNS；脚本只认实际 HTTPS 检查结果。

如果错误是 `curl: (28) Connection timed out`，含义是网络检查等待 10 秒后仍无法连接 Docker Hub，并不是项目代码出错。

### 2. `Could not pull ...`

基础镜像下载失败。保持 FlClash 已连接，确认 Docker Desktop 仍在运行，再重新选择菜单 `1`。已经下载的部分会被 Docker 缓存，安全重试不会删除数据库。

### 3. 构建在 `pip` 或 `npm` 阶段失败

这表示 Python 或前端依赖网站在当前网络不可达。保持 FlClash 已连接并尝试更换节点，然后重新选择菜单 `1`。

### 4. `Docker Engine did not become ready`

1. 手动打开 Docker Desktop。
2. 等左下角或托盘图标显示 Engine running。
3. 重新双击脚本并选择原操作。

### 5. 打不开 `127.0.0.1:8080`

先选择菜单 `4` 看状态：

- 如果容器没有运行，选择 `2`。
- 如果健康检查失败，选择 `6` 查看日志。
- 如果刚修改过代码，保持 FlClash 已连接并选择 `1` 重建。

### 6. 完全退出 FlClash 后其他软件不能联网

菜单 `1` 会在确认 `7890` 可用后，把当前 Windows 用户的系统代理指向 `127.0.0.1:7890`，让 Docker Desktop 使用同一代理。如果以后完全退出 FlClash，应重新打开 FlClash；或者在 Windows“设置 → 网络和 Internet → 代理”中关闭“使用代理服务器”。本机 `127.0.0.1:8080` 不受影响。

## 文件和数据在哪里

- 一键菜单：`docker_easy_menu.ps1`
- 双击入口：`Docker_One_Click.cmd`
- 备份与演练入口：`Docker_Backup_Restore.cmd`
- 本机密钥：`.env.docker`（不要发给别人，不要截图）
- Docker 数据：`E:\Docker\wsl`
- Ubuntu 数据：`E:\WSL\Ubuntu-24.04`
- 每次菜单运行日志：项目根目录 `logs\docker-easy-menu-日期时间.log`
- 实际部署进度：`部署步骤记录.md`

## 明确不要做的事

- 不要删除 `.env.docker`，除非你明确要让所有登录令牌失效。
- 不要执行 `docker compose down -v`；`-v` 会删除数据库数据卷。
- 不要删除 `E:\Docker\wsl`。
- 不要把端口从 `127.0.0.1` 改成 `0.0.0.0` 后直接联网。
- 不要把演示账号当作正式生产账号。
