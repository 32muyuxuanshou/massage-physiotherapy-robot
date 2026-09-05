#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
颐本智能理疗系统 - 打包后的启动器（PyInstaller 入口）

职责：
1. 以子进程方式启动 uvicorn（FastAPI 后端），监听 127.0.0.1:8000
2. 等待后端就绪后，用系统默认浏览器打开 http://127.0.0.1:8000
3. 监听 Ctrl+C / SIGTERM，关闭时干净地杀掉后端进程
4. 兼容开发模式（直接 python launcher.py 也能跑）
"""
import os
import sys
import signal
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

# Windows 终端默认 GBK，打印中文/特殊符号会炸；强制 UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _project_root() -> Path:
    """解析项目根目录。

    - 打包模式：取 PyInstaller 解压目录（_MEIPASS），里面放了 backend/ 和 frontend/dist/
    - 开发模式：取 launcher.py 的父目录
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """轮询等待端口可用。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _open_browser_later(url: str, delay: float = 1.5) -> None:
    """延迟一点再打开浏览器，避免后端刚起但前端还没就绪时白屏。"""
    def _worker():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _stream_output(stream, label: str) -> None:
    """把后端子进程的 stdout/stderr 转发到当前终端（带前缀），方便排错。"""
    for line in iter(stream.readline, b""):
        try:
            text = line.decode("utf-8", errors="replace").rstrip()
        except Exception:
            text = str(line)
        print(f"[backend:{label}] {text}", flush=True)
    try:
        stream.close()
    except Exception:
        pass


def main() -> int:
    root = _project_root()
    backend_dir = root / "backend"
    if not backend_dir.is_dir():
        print(f"错误：找不到后端目录 {backend_dir}", file=sys.stderr)
        return 1

    # 打包模式下，把 cwd 切到 backend/，这样 .env / 相对路径都正常工作
    os.chdir(backend_dir)

    print("=" * 60)
    print("  颐本智能理疗系统")
    print("  版本: 0.1.0  |  模式: " + ("打包" if getattr(sys, "frozen", False) else "开发"))
    print("=" * 60)
    print(f"后端目录: {backend_dir}")
    print(f"启动后端: {URL}")
    print("首次启动可能需要 5-10 秒（PyInstaller 解压 bundle）...")
    print("按 Ctrl+C 退出\n")

    # 启动 uvicorn 子进程
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]

    env = os.environ.copy()

    proc = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    # 转发后端日志到当前终端
    t_out = threading.Thread(target=_stream_output, args=(proc.stdout, "out"), daemon=True)
    t_err = threading.Thread(target=_stream_output, args=(proc.stderr, "err"), daemon=True)
    t_out.start()
    t_err.start()

    # 等后端就绪
    if not _wait_for_port(HOST, PORT, timeout=60.0):
        print(f"\n错误：后端在 60 秒内未就绪，请查看上方日志。", file=sys.stderr)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 1

    print(f"\n✓ 后端已就绪: {URL}")
    _open_browser_later(URL, delay=0.5)
    print("已请求打开默认浏览器。如未自动打开，请手动访问上面的地址。\n")

    # 优雅退出：捕获 SIGINT / SIGTERM
    stop_event = threading.Event()

    def _shutdown(signum, frame):
        print(f"\n收到退出信号 ({signum})，正在关闭后端...")
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    except (ValueError, OSError):
        # 某些环境（如子线程）无法注册信号，忽略
        pass

    # 主循环：等待子进程退出 或 收到停止信号
    try:
        while not stop_event.is_set():
            ret = proc.poll()
            if ret is not None:
                print(f"\n后端进程已退出 (code={ret})")
                return ret
            time.sleep(0.5)
    finally:
        # 关闭后端
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception as e:
                print(f"关闭后端时出错: {e}", file=sys.stderr)

    print("已退出。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(0)