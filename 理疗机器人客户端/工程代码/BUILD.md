# 颐本智能理疗系统 - 打包与使用说明（Linux）

**版本**: 0.1.0
**日期**: 2026-07-05

---

## 目录

1. [概述](#1-概述)
2. [产物说明](#2-产物说明)
3. [打包流程](#3-打包流程)
4. [用户使用指南](#4-用户使用指南)
5. [构建环境要求](#5-构建环境要求)
6. [常见问题](#6-常见问题)
7. [故障排查](#7-故障排查)
8. [进阶配置](#8-进阶配置)
9. [附录](#9-附录)

---

## 1. 概述

本文档介绍如何把 **颐本智能理疗系统**（FastAPI + Vue3 + SQLite）打包成可在 Linux 上独立运行的可执行文件。

打包后用户**无需安装** Python、Node、数据库或任何依赖，下载文件后只需执行一条命令即可启动整套系统。

### 1.1 打包方案

| 工具 | 作用 |
|------|------|
| **PyInstaller --onefile** | 把 Python 解释器、后端代码、依赖打包成单文件 ELF 可执行 |
| **appimagetool** | 把 ELF 进一步包装为 AppImage 单文件（双击即用） |
| **前端 dist 嵌入** | 把 `frontend/dist/` 复制到 `backend/static/`，由 FastAPI 统一提供 |

### 1.2 架构示意

```
┌──────────────── 颐本智能理疗系统-x86_64.AppImage ────────────────┐
│  AppRun (bash 入口)                                              │
│    └─▶ 内嵌 ELF: physiotherapy-client (PyInstaller --onefile)    │
│           ├─ 解压 bundle 到 /tmp (~3 秒)                         │
│           ├─ 启动 uvicorn (127.0.0.1:8000)                       │
│           └─ 打开系统默认浏览器访问 http://127.0.0.1:8000         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 产物说明

打包完成后，`dist/` 目录下会生成：

| 文件 | 大小 | 用途 |
|------|------|------|
| `physiotherapy-client` | ~120 MB | PyInstaller 原始 ELF 可执行，命令行 `./physiotherapy-client` 运行 |
| `颐本智能理疗系统-x86_64.AppImage` | ~120 MB | AppImage 单文件，**双击即用**，推荐交付 |

> 体积估算已包含 Python 3.11 解释器、FastAPI + uvicorn + SQLAlchemy + aiosqlite + bcrypt + python-jose 等全部后端依赖。

---

## 3. 打包流程

### 3.1 一次性准备（仅首次）

#### 3.1.1 系统依赖

```bash
# Ubuntu 22.04+ / Debian 12+
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
                    nodejs npm \
                    build-essential \
                    libfuse2     # AppImage 运行所需
```

#### 3.1.2 后端虚拟环境

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ..
```

#### 3.1.3 前端构建

```bash
cd frontend
npm install
npm run build      # 产物输出到 frontend/dist/
cd ..
```

#### 3.1.4 下载 appimagetool（可选，仅需生成 AppImage 时）

```bash
mkdir -p ~/bin
cd ~/bin
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
mv appimagetool-x86_64.AppImage appimagetool
# 或直接从 AppImage 提取（无需 FUSE）
./appimagetool-x86_64.AppImage --appimage-extract
sudo ln -sf $(pwd)/squashfs-root/AppRun /usr/local/bin/appimagetool
```

### 3.2 一键打包

```bash
cd /path/to/physiotherapy-client
chmod +x build.sh
./build.sh
```

`build.sh` 自动完成：
1. 把 `frontend/dist/` 嵌入到 `backend/static/`
2. 在 `backend/.venv` 中安装 `pyinstaller`
3. 调用 PyInstaller `--onefile` 打包 `launcher.py`
4. 调用 `appimagetool` 生成 AppImage
5. 输出到 `dist/`

#### 3.2.1 高级选项

```bash
./build.sh --skip-frontend   # 跳过前端复制（前端 dist 已就位时用）
./build.sh --skip-appimage   # 只生成 ELF，不打 AppImage
./build.sh --help            # 查看帮助
```

### 3.3 分发产物

```bash
# 把这两个文件发给最终用户
dist/physiotherapy-client
dist/颐本智能理疗系统-x86_64.AppImage
```

---

## 4. 用户使用指南

### 4.1 准备工作

**最低系统要求**：
- 任意现代 Linux 发行版（Ubuntu 22.04+ / Debian 12+ / Arch / Fedora 38+ / openSUSE Leap 15.5+ 等）
- 已安装任意浏览器（Firefox / Chromium / Chrome 任一）
- 800 MB 可用磁盘空间

**零依赖**：不需要 Python、Node、数据库、Docker、Nginx 等任何额外组件。

### 4.2 启动应用（推荐方式：AppImage）

```bash
# 1. 下载文件
wget https://your-server/颐本智能理疗系统-x86_64.AppImage

# 2. 添加可执行权限
chmod +x 颐本智能理疗系统-x86_64.AppImage

# 3. 双击运行（文件管理器）
#    或命令行运行：
./颐本智能理疗系统-x86_64.AppImage
```

启动后自动完成：
1. ⏳ 解压 bundle 到临时目录（首次约 5-10 秒，之后秒开）
2. 🚀 启动 FastAPI 后端，监听 `127.0.0.1:8000`
3. 🌐 打开系统默认浏览器访问 `http://127.0.0.1:8000`
4. 🔑 默认测试账号：`13800138000` / `123456`

### 4.3 启动应用（备选：纯 ELF）

```bash
./physiotherapy-client
```

行为完全一致，区别仅在于不是 AppImage 格式。

### 4.4 关闭应用

- 在终端窗口按 `Ctrl+C`
- 或直接关闭终端窗口
- 后端进程会被自动清理

### 4.5 数据存放位置

首次运行时，应用会在以下位置创建用户数据目录（数据库、日志）：

| 系统 | 路径 |
|------|------|
| Linux / macOS | `~/.local/share/physiotherapy-client/` |
| Windows | `%APPDATA%\physiotherapy-client\` |

可通过环境变量 `PHYSIOTHERAPY_DATA_DIR` 自定义：

```bash
export PHYSIOTHERAPY_DATA_DIR=/path/to/your/data
./颐本智能理疗系统-x86_64.AppImage
```

---

## 5. 构建环境要求

### 5.1 操作系统

- 推荐：Ubuntu 22.04 LTS 或 Debian 12（bookworm）
- 其它：任何 x86_64 Linux 发行版

### 5.2 软件版本

| 软件 | 最低版本 | 推荐版本 | 检查命令 |
|------|---------|---------|---------|
| Python | 3.10 | 3.11+ | `python3 --version` |
| Node.js | 18 | 20 LTS | `node --version` |
| npm | 9 | 10+ | `npm --version` |
| pip | 23 | 最新 | `pip --version` |

### 5.3 磁盘空间

- 源码 + 依赖：~2 GB
- 打包中临时产物：~1.5 GB
- 最终产物：~250 MB（两个文件合计）

---

## 6. 常见问题

### 6.1 Q: AppImage 双击没反应？

**A**: 大概率是缺 FUSE。解决方法：

```bash
# Ubuntu 22.04+
sudo apt install libfuse2

# Ubuntu 24.04+（默认无 FUSE）
sudo apt install libfuse2t64

# 或提取后直接运行
./颐本智能理疗系统-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

或直接用 ELF 版：`./physiotherapy-client`

### 6.2 Q: 浏览器没有自动打开？

**A**: launcher 默认延迟 0.5 秒打开浏览器。如被弹窗拦截，请手动访问终端显示的地址：

```
✓ 后端已就绪: http://127.0.0.1:8000
```

或在终端看到提示后手动复制打开。

### 6.3 Q: 端口 8000 被占用？

**A**: launcher 会自动等待 60 秒。如端口被其他进程占用且不释放：

```bash
# 查找占用进程
sudo lsof -i :8000
# 或
sudo fuser 8000/tcp

# 杀掉占用进程
sudo kill -9 <PID>
```

如频繁冲突，可修改 `launcher.py` 顶部的 `PORT = 8000` 为其他端口。

### 6.4 Q: 打包后体积太大（> 200 MB）？

**A**: PyInstaller 已默认排除 `tkinter / matplotlib / numpy / pandas / scipy / PIL / pytest / IPython / jupyter` 等大模块。

如仍偏大，可检查 `backend/requirements.txt` 是否引入多余依赖。

### 6.5 Q: 启动报错 `ModuleNotFoundError`？

**A**: 通常是 PyInstaller 漏掉了某个动态导入包。在 `build.sh` 的 `HIDDEN_IMPORTS` 数组中添加对应模块，然后重新打包。

### 6.6 Q: 启动报错 `Could not find backend/static`？

**A**: `backend/static` 未生成或被前端构建未执行。重新跑：

```bash
cd frontend && npm run build && cd ..
./build.sh
```

### 6.7 Q: 数据库初始化失败？

**A**: 检查首次运行时 `~/.local/share/physiotherapy-client/` 目录的写权限：

```bash
ls -la ~/.local/share/physiotherapy-client/
# 应包含 physiotherapy.db 和可能的 logs 子目录
```

---

## 7. 故障排查

### 7.1 启用详细日志

```bash
# 在终端直接运行而非双击，可以看到完整后端日志：
./颐本智能疗系统-x86_64.AppImage
```

### 7.2 常见错误对照

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `错误：找不到后端目录 backend` | PyInstaller bundle 损坏 | 重新执行 `./build.sh` |
| `后端在 60 秒内未就绪` | 端口冲突或依赖缺失 | 检查 6.3 + 6.5 |
| `ModuleNotFoundError: aiosqlite` | 隐藏导入不全 | 已在 `build.sh` 中 `--collect-all=aiosqlite`，重新打包 |
| `sqlite3.OperationalError: unable to open database file` | 数据目录无写权限 | 检查 6.7 |
| `OSError: [Errno 98] Address already in use` | 8000 端口被占用 | 见 6.3 |

### 7.3 查看打包过程的日志

```bash
bash -x build.sh 2>&1 | tee build.log
```

### 7.4 重置用户数据

```bash
# ⚠️ 会清空所有用户数据，仅排错时使用
rm -rf ~/.local/share/physiotherapy-client/
# 下次启动时会重新生成
```

---

## 8. 进阶配置

### 8.1 改端口

编辑 [launcher.py](file:///d:/coder/physiotherapy-client/launcher.py) 顶部：

```python
HOST = "127.0.0.1"
PORT = 8000          # 改成你想要的端口
URL = f"http://{HOST}:{PORT}"
```

### 8.2 改后端绑定地址（允许局域网访问）

修改 `launcher.py` 中 uvicorn 启动命令的 `--host` 参数：

```python
cmd = [
    sys.executable, "-m", "uvicorn", "app.main:app",
    "--host", "0.0.0.0",     # 改成 0.0.0.0 监听所有网卡
    "--port", str(PORT),
]
```

### 8.3 改应用名称 / 图标

编辑 [build.sh](file:///d:/coder/physiotherapy-client/build.sh) 顶部：

```bash
APP_NAME="physiotherapy-client"        # ELF 文件名
DISPLAY_NAME="颐本智能理疗系统"        # AppImage 文件名
ICON_PNG="app_icon.png"                # 图标路径（替换成你的 PNG）
```

### 8.4 关闭自动打开浏览器

编辑 [launcher.py](file:///d:/coder/physiotherapy-client/launcher.py)，注释掉：

```python
# _open_browser_later(URL, delay=0.5)
```

### 8.5 启用后端热重载（开发模式）

直接 `python launcher.py` 跑即可，无需打包。改动代码后重启 launcher。

### 8.6 跨架构打包

当前默认输出 x86_64。如要在 ARM64（如 Apple Silicon、树莓派）机器上跑：

```bash
# 在 ARM64 Linux 机器上重新打包
./build.sh
```

PyInstaller **不支持** 跨架构编译，必须在目标架构上打包。

---

## 9. 附录

### 9.1 项目结构（打包相关）

```
physiotherapy-client/
├── launcher.py                   # 打包入口（PyInstaller 入口）
├── build.sh                      # 一键打包脚本
├── BUILD.md                      # 本文档
├── 颐本智能理疗系统.desktop       # 桌面文件描述
├── app_icon.png                  # 应用图标
├── backend/
│   ├── app/
│   │   ├── main.py               # 已适配打包路径
│   │   └── database.py           # 已适配打包路径
│   ├── data/physiotherapy.db     # 数据库模板（首次启动会复制到用户目录）
│   └── .venv/                    # Python 虚拟环境
├── frontend/
│   └── dist/                     # 构建产物（打包时复制到 backend/static）
└── dist/                         # 打包输出
    ├── physiotherapy-client
    └── 颐本智能理疗系统-x86_64.AppImage
```

### 9.2 关键文件说明

| 文件 | 作用 |
|------|------|
| [launcher.py](file:///d:/coder/physiotherapy-client/launcher.py) | PyInstaller 入口；启动后端 + 浏览器 + 信号处理 |
| [build.sh](file:///d:/coder/physiotherapy-client/build.sh) | 一键打包；前端嵌入 + PyInstaller + AppImage |
| [backend/app/main.py](file:///d:/coder/physiotherapy-client/backend/app/main.py) | FastAPI 入口；新增 `get_base_dir()` 支持 `_MEIPASS` |
| [backend/app/database.py](file:///d:/coder/physiotherapy-client/backend/app/database.py) | 数据库初始化；新增打包模式下的用户数据目录 + 模板复制 |

### 9.3 技术栈一览

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Axios + SCSS |
| 后端 | FastAPI + Uvicorn + SQLAlchemy (async) + aiosqlite |
| 数据库 | SQLite（嵌入式） |
| 鉴权 | JWT (python-jose) + bcrypt |
| 打包 | PyInstaller 6.x + appimagetool |
| 目标 | x86_64 Linux（理论可移植到 ARM64，需在目标平台重打包） |

### 9.4 默认账号

| 手机号 | 密码 | 说明 |
|--------|------|------|
| `13800138000` | `123456` | 测试用户 |

### 9.5 相关链接

- PyInstaller 文档：<https://pyinstaller.org/en/stable/>
- AppImage 规范：<https://docs.appimage.org/>
- FastAPI 文档：<https://fastapi.tiangolo.com/>

---

**维护者**: 颐本智能理疗系统开发团队
**最后更新**: 2026-07-05