# 颐本智能理疗系统：PyCharm 使用教程

## 1. 已完成的配置

工程目录：

```text
E:\项目-按摩理疗机器人\理疗机器人客户端\工程代码
```

当前已经准备好：

- Python 3.11.9；
- 后端虚拟环境 `backend\.venv`；
- FastAPI 及全部后端依赖；
- 已构建的 Vue 前端，位于 `backend\static`；
- 已初始化的 SQLite 数据库；
- PyCharm 共享运行配置“第一阶段-FastAPI”；
- PyCharm 启动入口 `backend\run_first_stage.py`。

第一阶段不需要 Docker、WSL、Node.js 或 MCP。

## 2. 打开工程

在 PyCharm 选择 **File → Open**，打开：

```text
E:\项目-按摩理疗机器人\理疗机器人客户端\工程代码
```

不要只打开 `backend` 子目录，否则共享运行配置中的工程路径可能无法正确解析。

## 3. 检查 Python 解释器

首次打开后，查看 PyCharm 右下角的解释器，或者打开：

```text
File → Settings → Python → Interpreter
```

解释器应当是：

```text
E:\项目-按摩理疗机器人\理疗机器人客户端\工程代码\backend\.venv\Scripts\python.exe
```

如果没有自动选中：

1. 点击解释器列表旁的 **Add Interpreter**；
2. 选择 **Add Local Interpreter**；
3. 选择 **Existing**；
4. 指向上面的 `python.exe`；
5. 点击 **OK**。

不要新建第二个虚拟环境，现有 `.venv` 已安装全部依赖。

## 4. 启动系统

1. 在 PyCharm 顶部运行配置列表中选择 **第一阶段-FastAPI**；
2. 点击绿色运行按钮，或按 `Shift+F10`；
3. 等待 Run 窗口出现以下信息：

```text
Uvicorn running on http://127.0.0.1:8000
```

4. 浏览器访问：

```text
系统首页：http://127.0.0.1:8000
API 文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/health
```

测试账号：

```text
手机号：13800138000
密码：123456
```

## 5. 调试后端代码

1. 在 Python 代码行号左侧点击，设置红色断点；
2. 选择 **第一阶段-FastAPI**；
3. 点击虫子形状的 Debug 按钮，或按 `Shift+F9`；
4. 在浏览器操作相应功能；
5. 请求执行到断点时，可查看变量、单步执行和调用栈。

推荐断点位置：

```text
backend\app\api\v1\auth.py
backend\app\services\device_service.py
backend\app\services\therapy_service.py
backend\app\services\ai_service.py
```

运行配置默认关闭自动重载，以保证断点调试稳定。修改 Python 后，点击 PyCharm 的重新运行按钮或按 `Ctrl+F5`。

## 6. 停止服务

在 PyCharm 的 Run/Debug 窗口点击红色停止按钮，或按 `Ctrl+F2`。

同一时间只能运行一个使用 8000 端口的服务。如果出现“端口已被占用”，先检查：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000 |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

确认是本项目进程后，再从 PyCharm 的运行窗口停止它。不要随意终止来源不明的进程。

## 7. 修改前端

当前前端已经构建完成，所以只修改 `frontend\src` 不会立即改变页面。前端开发需要另外安装 Node.js，然后在项目根目录运行：

```powershell
.\sync_frontend.ps1
```

该脚本会重新构建前端并同步到 `backend\static`。如果只调试后端，不需要安装 Node.js。

## 8. 数据库和备份

数据库位置：

```text
backend\data\physiotherapy.db
```

备份前先停止 PyCharm 中的服务，然后复制该文件。不要在服务运行、正在写入数据时直接覆盖数据库。

重新执行初始化脚本是幂等的，不会重复创建已有的测试数据：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.scripts.init_db
```

## 9. 常见问题

### PyCharm 提示找不到 FastAPI 或 uvicorn

通常是解释器选错。确认解释器指向 `backend\.venv\Scripts\python.exe`。

### 首页返回 JSON 而不是登录页

确认 `backend\static\index.html` 存在。当前工程已经生成该文件。

### 登录返回 500

项目已经在 `requirements.txt` 中固定 `bcrypt==4.0.1`。如果重新创建过虚拟环境，请再次执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 想让局域网其他电脑访问

需要把运行配置中的 `PHYSIOTHERAPY_HOST` 改成 `0.0.0.0`，并单独配置 Windows 防火墙。开放端口会扩大网络访问范围，演示阶段默认保持 `127.0.0.1` 更安全。

## 10. MCP 是否需要

本地开发、运行、断点调试和数据库文件访问都不需要 MCP。只有需要连接 GitHub、云数据库、任务系统或其他外部服务时，才需要考虑相应 MCP/插件。
