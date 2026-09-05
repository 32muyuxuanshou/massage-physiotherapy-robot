import sys
import os
import subprocess
import signal
import platform
import time
import urllib.request
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import threading

try:
    import webview
except ImportError as e:
    print(f"错误: 无法导入 webview: {e}")
    print("请安装 pywebview:")
    print("  pip install pywebview")
    sys.exit(1)


def setup_logging(project_root):
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "app.log"
    error_log_file = log_dir / "error.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '[%(levelname)s] %(message)s'
    ))

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console_handler)

    return logger


class WindowAPI:
    def __init__(self, app):
        self.app = app
    
    def close_window(self):
        self.app.stop_backend()
        if self.app.window:
            self.app.window.destroy()

class Application:
    def __init__(self, logger):
        self.server_process = None
        self.running = False
        self.project_root = Path(__file__).parent
        self.window_width = 1024
        self.window_height = 768
        self.window = None
        self.logger = logger

    def _wait_for_port(self, port, timeout=30):
        """等待端口可用"""
        self.logger.info(f"等待端口 {port} 可用...")
        for i in range(timeout):
            if platform.system() == "Windows":
                result = subprocess.run(
                    f'netstat -ano | findstr :{port}',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout and 'LISTENING' in result.stdout:
                    self.logger.info(f"端口 {port} 已在监听")
                    return True
            else:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    self.logger.info(f"端口 {port} 已在监听")
                    return True
            
            if i < timeout - 1:
                time.sleep(1)
        
        self.logger.warning(f"等待端口 {port} 超时")
        return False

    def _cleanup_port(self, port):
        """清理端口"""
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    f'netstat -ano | findstr :{port}',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    own_pid = os.getpid()
                    killed = set()
                    
                    for line in lines:
                        if 'LISTENING' in line:
                            parts = line.split()
                            if len(parts) > 4:
                                pid = parts[-1]
                                if pid.isdigit():
                                    pid_int = int(pid)
                                    if pid_int != own_pid and pid_int not in killed:
                                        self.logger.info(f"终止进程 PID: {pid}")
                                        subprocess.run(
                                            f'taskkill /F /T /PID {pid}',
                                            shell=True,
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL
                                        )
                                        killed.add(pid_int)
                    
                    if killed:
                        time.sleep(2)
            except Exception as e:
                self.logger.warning(f"清理端口时出错: {e}")
        else:
            try:
                result = subprocess.run(
                    ['lsof', '-t', f'-i:{port}'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    own_pid = os.getpid()
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid and pid.isdigit():
                            pid_int = int(pid)
                            if pid_int != own_pid:
                                self.logger.info(f"终止进程 PID: {pid}")
                                subprocess.run(['kill', '-9', pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1)
            except FileNotFoundError:
                try:
                    subprocess.run(['fuser', '-k', f'{port}/tcp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1)
                except Exception as e:
                    self.logger.warning(f"fuser 失败: {e}")
            except Exception as e:
                self.logger.warning(f"清理端口时出错: {e}")

    def start_backend(self):
        """启动后端服务"""
        backend_path = str(self.project_root / "backend")
        
        self.logger.info("准备清理端口 8000...")
        self._cleanup_port(8000)
        time.sleep(1)
        
        if platform.system() == "Windows":
            venv_python = str(self.project_root / "backend" / ".venv" / "Scripts" / "python.exe")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.server_process = subprocess.Popen(
                [venv_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=backend_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                startupinfo=startupinfo
            )
        else:
            venv_python = str(self.project_root / "backend" / ".venv" / "bin" / "python")
            self.server_process = subprocess.Popen(
                [venv_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=backend_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid
            )
        
        self.running = True
        self.logger.info("后端进程已启动")
        
        time.sleep(2)
        
        if not self._wait_for_port(8000, timeout=30):
            self.logger.error("后端服务启动失败")
            self.stop_backend()
            return False
        
        for _ in range(10):
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/health")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        self.logger.info("后端服务就绪!")
                        return True
            except Exception:
                pass
            time.sleep(1)
        
        self.logger.error("后端健康检查失败")
        self.stop_backend()
        return False

    def stop_backend(self):
        """停止后端服务"""
        if not self.server_process:
            return
        
        self.running = False
        self.logger.info("正在停止后端服务...")
        
        try:
            if platform.system() == "Windows":
                if self.server_process.poll() is None:
                    subprocess.run(
                        f'taskkill /F /T /PID {self.server_process.pid}',
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            else:
                try:
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                except:
                    pass
        except Exception as e:
            self.logger.warning(f"停止后端时出错: {e}")
        
        self.server_process = None
        self.logger.info("后端服务已停止")

    def read_logs(self):
        """读取后端日志"""
        def read(pipe, prefix):
            while self.running:
                try:
                    line = pipe.readline()
                    if line:
                        content = line.strip()
                        if "[ERROR]" in content or "[Exception]" in content:
                            self.logger.error(f"[后端{prefix}] {content}")
                        elif "[WARNING]" in content:
                            self.logger.warning(f"[后端{prefix}] {content}")
                except:
                    break
        
        if self.server_process:
            t1 = threading.Thread(target=read, args=(self.server_process.stdout, "OUT"), daemon=True)
            t1.start()
            if self.server_process.stderr:
                t2 = threading.Thread(target=read, args=(self.server_process.stderr, "ERR"), daemon=True)
                t2.start()

    def run(self):
        """主运行函数"""
        self.logger.info("=" * 60)
        self.logger.info("颐本智能理疗系统 - 启动中")
        self.logger.info("=" * 60)
        self.logger.info(f"项目路径: {self.project_root}")
        self.logger.info(f"窗口尺寸: {self.window_width}x{self.window_height}")
        
        self.logger.info("启动后端服务...")
        if not self.start_backend():
            self.logger.error("后端启动失败，程序退出")
            return
        
        self.read_logs()
        time.sleep(1)
        
        self.logger.info("创建窗口...")
        try:
            self.window = webview.create_window(
                title="颐本智能理疗系统",
                url="http://127.0.0.1:8000",
                width=self.window_width,
                height=self.window_height,
                resizable=False,
                frameless=True
            )
            
            webview_window = self.window
            
            def close_window():
                self.stop_backend()
                if self.window:
                    self.window.destroy()
            
            webview_window.expose(close_window)
            self.logger.info("显示窗口...")
            webview.start()
            
            self.logger.info("窗口已关闭")
        except Exception as e:
            self.logger.error(f"窗口错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_backend()
            self.logger.info("程序退出")


if __name__ == "__main__":
    project_root = Path(__file__).parent
    logger = setup_logging(project_root)
    
    app = Application(logger)
    
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号...")
        app.stop_backend()
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        app.stop_backend()
    finally:
        app.stop_backend()
        logger.info("程序已退出")