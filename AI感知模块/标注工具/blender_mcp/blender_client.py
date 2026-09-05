"""Small, typed client for the local Blender bridge.

The bridge deliberately uses newline-delimited JSON instead of exposing a
general Python evaluator.  Each command opens a short-lived socket so a broken
Blender session cannot leave the MCP process with a desynchronised stream.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from typing import Any


class BlenderBridgeError(RuntimeError):
    """The Blender bridge was unavailable or rejected a command."""


class BlenderClient:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or os.environ.get("ACUPOINT_MCP_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("ACUPOINT_MCP_PORT", "9877"))
        self._token: str | None = None
        self._lock = threading.Lock()

    def _exchange(self, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        if len(encoded) > 1024 * 1024:
            raise BlenderBridgeError("请求超过 1 MiB 安全上限")
        try:
            with socket.create_connection((self.host, self.port), timeout=3.0) as sock:
                sock.settimeout(timeout)
                sock.sendall(encoded)
                buffer = bytearray()
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if len(buffer) > 8 * 1024 * 1024:
                        raise BlenderBridgeError("Blender 返回内容超过 8 MiB 安全上限")
                    if b"\n" in buffer:
                        line, _separator, _rest = bytes(buffer).partition(b"\n")
                        return json.loads(line.decode("utf-8"))
        except (ConnectionError, OSError, socket.timeout) as exc:
            raise BlenderBridgeError(
                "未连接到 Blender 穴位 MCP 桥接器。请先打开已启用桥接插件的 Blender。"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderBridgeError("Blender 桥接器返回了无效 JSON") from exc
        raise BlenderBridgeError("Blender 桥接器没有返回结果")

    def _pair(self) -> str:
        response = self._exchange(
            {"id": str(uuid.uuid4()), "type": "pair", "params": {}}, timeout=5.0
        )
        if response.get("status") != "success":
            raise BlenderBridgeError(str(response.get("message") or "本地配对失败"))
        token = str((response.get("result") or {}).get("token") or "")
        if len(token) < 32:
            raise BlenderBridgeError("Blender 桥接器返回的配对令牌无效")
        self._token = token
        return token

    def command(
        self,
        command_type: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        if not command_type or not command_type.replace("_", "").isalnum():
            raise ValueError("非法命令名称")
        with self._lock:
            for attempt in range(2):
                token = self._token or self._pair()
                request_id = str(uuid.uuid4())
                response = self._exchange(
                    {
                        "id": request_id,
                        "type": command_type,
                        "token": token,
                        "params": params or {},
                    },
                    timeout=timeout,
                )
                if response.get("status") == "success":
                    return dict(response.get("result") or {})
                message = str(response.get("message") or "Blender 命令失败")
                if "令牌" in message and attempt == 0:
                    self._token = None
                    continue
                raise BlenderBridgeError(message)
        raise BlenderBridgeError("Blender 命令重试失败")

    def ping(self) -> dict[str, Any]:
        return self.command("ping", timeout=5.0)

