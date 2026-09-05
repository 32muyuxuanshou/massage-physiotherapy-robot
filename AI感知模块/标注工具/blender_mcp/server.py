"""Codex-facing MCP server for the controlled SKEL annotation workflow."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from PIL import Image, ImageDraw, ImageFont

from blender_client import BlenderBridgeError, BlenderClient


SERVER_VERSION = "0.2.1"
PROJECT_MARKER = "AI感知模块"
WRITE_SUBDIR = Path("outputs") / "BlenderMCP"


def _discover_project_root() -> Path:
    configured = os.environ.get("ACUPOINT_MCP_PROJECT_ROOT", "").strip()
    if configured:
        candidate = Path(configured).resolve()
        if candidate.name != PROJECT_MARKER:
            raise RuntimeError(f"ACUPOINT_MCP_PROJECT_ROOT 必须指向 {PROJECT_MARKER}")
        return candidate
    for parent in Path(__file__).resolve().parents:
        if parent.name == PROJECT_MARKER:
            return parent
    raise RuntimeError(f"无法定位 {PROJECT_MARKER} 项目根目录")


PROJECT_ROOT = _discover_project_root()
WRITE_ROOT = (PROJECT_ROOT / WRITE_SUBDIR).resolve()
WORKBENCH_ROOT = (
    PROJECT_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
).resolve()
MODEL_PACK_ROOT = (
    PROJECT_ROOT
    / "模型资源"
    / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发"
).resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def checked_read_file(raw_path: str, suffixes: set[str]) -> Path:
    candidate = Path(raw_path).expanduser().resolve()
    if not _inside(candidate, PROJECT_ROOT):
        raise ValueError(f"只允许读取 {PROJECT_ROOT} 内的文件")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    if candidate.suffix.lower() not in suffixes:
        raise ValueError(f"文件类型必须是：{', '.join(sorted(suffixes))}")
    return candidate


def _allocate_output_dir(category: str) -> Path:
    safe_category = "".join(ch for ch in category if ch.isalnum() or ch in "_-滴定样本会话")
    if not safe_category:
        safe_category = "output"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    for _attempt in range(20):
        candidate = WRITE_ROOT / safe_category / f"{timestamp}_{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("无法分配唯一输出目录")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _overlay(rgb_path: Path, labels_path: Path, output_path: Path) -> None:
    with labels_path.open("r", encoding="utf-8-sig") as handle:
        labels = json.load(handle)
    with Image.open(rgb_path) as source:
        canvas = source.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"
    try:
        font = ImageFont.truetype(str(font_path), 16) if font_path.is_file() else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    for point in labels.get("points", []):
        uv = point.get("uv_pixel_opencv")
        if not isinstance(uv, list) or len(uv) != 2 or not point.get("in_frame"):
            continue
        x, y = float(uv[0]), float(uv[1])
        visible = bool(point.get("visible"))
        color = (32, 220, 92, 255) if visible else (245, 72, 72, 255)
        radius = 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(255, 255, 255, 255), width=2)
        label = str(point.get("code") or point.get("point_id") or "")
        draw.text((x + 9, y - 10), label, fill=(255, 255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0, 220))
    canvas.convert("RGB").save(output_path, format="PNG")


client = BlenderClient()
mcp = MCPServer(
    "SKEL Acupoint Blender MCP",
    instructions=(
        "用于按摩理疗机器人内部研究。正式穴位只绑定 SKEL 原生皮肤；"
        "不得把 Blender 坐标直接作为机器人执行坐标。"
    ),
    version=SERVER_VERSION,
)


@mcp.tool(structured_output=True)
def blender_status() -> dict[str, Any]:
    """检查 Blender 桥接、当前文件、正式插件和目标人体状态（只读）。"""
    try:
        result = client.command("status", timeout=8.0)
        return {"mcp_version": SERVER_VERSION, "connected": True, **result}
    except BlenderBridgeError as exc:
        return {
            "mcp_version": SERVER_VERSION,
            "connected": False,
            "message": str(exc),
            "next_step": "调用 start_skel_session，或重新打开已安装桥接插件的 Blender。",
        }


@mcp.tool(structured_output=True)
def start_skel_session(gender: Literal["female", "male"] = "female") -> dict[str, Any]:
    """从冻结的正式 SKEL 模板创建工作副本并打开 Blender；绝不覆盖模板。"""
    current = blender_status()
    if current.get("connected"):
        return {
            "started": False,
            "reason": "已有 Blender 桥接会话正在运行，为避免连接到错误场景，本次未再启动。",
            "current": current,
        }
    blender_exe = WORKBENCH_ROOT / "runtime" / "blender" / "blender.exe"
    user_resources = WORKBENCH_ROOT / "user_resources"
    template_name = (
        "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
        if gender == "female"
        else "SKEL_MALE_TRUNK_LIMB_v2.3.blend"
    )
    template = MODEL_PACK_ROOT / "templates" / "SKEL" / template_name
    for required in (blender_exe, user_resources, template):
        if not required.exists():
            raise FileNotFoundError(required)
    session_dir = _allocate_output_dir("会话")
    work_blend = session_dir / f"SKEL_{gender}_MCP工作副本.blend"
    shutil.copy2(template, work_blend)
    environment = os.environ.copy()
    environment.update(
        {
            "BLENDER_USER_RESOURCES": str(user_resources),
            "ACUPOINT_MCP_PROJECT_ROOT": str(PROJECT_ROOT),
            "SMPL_ACUPOINT_WORKFLOW_MODE": "RESEARCH",
            "SMPL_ACUPOINT_SIMPLE_UI": "1",
        }
    )
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [str(blender_exe), str(work_blend)],
        cwd=str(session_dir),
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    deadline = time.monotonic() + 35.0
    status: dict | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Blender 启动失败，退出码 {process.returncode}")
        time.sleep(0.4)
        status = blender_status()
        if status.get("connected"):
            break
    if not status or not status.get("connected"):
        raise RuntimeError("Blender 已启动，但 35 秒内没有连上穴位 MCP 桥接器")
    manifest = {
        "schema": "acupoint-blender-mcp-session-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gender": gender,
        "source_template": str(template),
        "source_template_sha256": _sha256(template),
        "work_blend": str(work_blend),
        "pid": process.pid,
    }
    manifest_path = session_dir / "session_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "started": True,
        "pid": process.pid,
        "work_blend": str(work_blend),
        "manifest": str(manifest_path),
        "status": status,
        "notice": "这是工作副本；MCP 不会自动保存 .blend。",
    }


@mcp.tool(structured_output=True)
def inspect_scene() -> dict[str, Any]:
    """列出当前人体、相机和穴位数量，不改变 Blender 场景。"""
    return client.command("inspect_scene", timeout=15.0)


@mcp.tool(structured_output=True)
def prepare_annotation_draft(
    code: str,
    name_zh: str,
    side: Literal["MIDLINE", "LEFT", "RIGHT"] = "MIDLINE",
    body_region: Literal["NECK", "TORSO"] = "TORSO",
    meridian: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """仅预填插件草稿字段；不创建穴位、不写 JSON、也不保存 Blend。"""
    return client.command(
        "prepare_annotation_draft",
        {
            "code": code,
            "name_zh": name_zh,
            "side": side,
            "body_region": body_region,
            "meridian": meridian,
            "notes": notes,
        },
        timeout=15.0,
    )


@mcp.tool(structured_output=True)
def validate_atlas(atlas_path: str) -> dict[str, Any]:
    """校验正式 Atlas 与当前 SKEL 的模型族、性别、拓扑和表面绑定。"""
    atlas = checked_read_file(atlas_path, {".json"})
    return client.command("validate_atlas", {"atlas_path": str(atlas)}, timeout=30.0)


@mcp.tool(structured_output=True)
def get_acupoint_3d(atlas_path: str, point_id: str) -> dict[str, Any]:
    """由 face_index+barycentric 计算穴位在当前姿态/体型下的世界三维坐标。"""
    atlas = checked_read_file(atlas_path, {".json"})
    if not point_id.strip():
        raise ValueError("point_id 不能为空，例如 11_MIDLINE")
    return client.command(
        "get_acupoint_3d",
        {"atlas_path": str(atlas), "point_id": point_id.strip()},
        timeout=30.0,
    )


@mcp.tool(structured_output=True)
def list_cameras() -> dict[str, Any]:
    """列出当前 Blender 场景相机及活动相机（只读）。"""
    return client.command("list_cameras", timeout=15.0)


@mcp.tool(structured_output=True)
def set_camera_view(
    preset: Literal["front", "back", "left", "right"] = "front",
    distance_scale: float = 1.0,
    focal_length_mm: float = 50.0,
    camera_name: str = "ACU_MCP_CAMERA",
) -> dict[str, Any]:
    """设置临时相机为前/后/左/右视角；改变当前场景但绝不自动保存。"""
    if not 0.5 <= distance_scale <= 4.0:
        raise ValueError("distance_scale 必须在 0.5–4.0")
    if not 18.0 <= focal_length_mm <= 200.0:
        raise ValueError("focal_length_mm 必须在 18–200 mm")
    if not camera_name.startswith("ACU_") or len(camera_name) > 64:
        raise ValueError("camera_name 必须以 ACU_ 开头且不超过 64 个字符")
    return client.command(
        "set_camera_view",
        {
            "preset": preset,
            "distance_scale": float(distance_scale),
            "focal_length_mm": float(focal_length_mm),
            "camera_name": camera_name,
        },
        timeout=30.0,
    )


@mcp.tool(structured_output=True)
def export_training_sample(
    atlas_path: str,
    point_ids: list[str] | None = None,
    camera_name: str = "",
    width: int = 640,
    height: int = 640,
) -> dict[str, Any]:
    """导出一个对齐的 RGB-D 训练样本和可见 SKEL 皮肤 Mask；不保存 Blend。"""
    atlas = checked_read_file(atlas_path, {".json"})
    if not 128 <= width <= 4096 or not 128 <= height <= 4096:
        raise ValueError("图像宽高必须在 128–4096 像素")
    selected_ids = [value.strip() for value in (point_ids or []) if value.strip()]
    if len(selected_ids) > 1000:
        raise ValueError("单样本最多导出 1000 个点")
    output_dir = _allocate_output_dir("样本")
    try:
        result = client.command(
            "export_training_sample",
            {
                "atlas_path": str(atlas),
                "output_dir": str(output_dir),
                "point_ids": selected_ids,
                "camera_name": camera_name.strip(),
                "width": int(width),
                "height": int(height),
            },
            timeout=300.0,
        )
        rgb_path = checked_read_file(str(result["rgb_path"]), {".png"})
        depth_path = checked_read_file(str(result["scene_depth_z_path"]), {".npy"})
        valid_mask_path = checked_read_file(str(result["depth_valid_mask_path"]), {".png"})
        skin_mask_path = checked_read_file(str(result["skin_mask_path"]), {".png"})
        labels_path = checked_read_file(str(result["labels_path"]), {".json"})
        overlay_path = output_dir / "overlay.png"
        _overlay(rgb_path, labels_path, overlay_path)
        manifest = {
            "schema": "acupoint-training-sample-manifest-v2",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "files": {
                "rgb.png": _sha256(rgb_path),
                "scene_depth_z.npy": _sha256(depth_path),
                "depth_valid_mask.png": _sha256(valid_mask_path),
                "skin_mask.png": _sha256(skin_mask_path),
                "labels.json": _sha256(labels_path),
                "overlay.png": _sha256(overlay_path),
            },
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            **result,
            "overlay_path": str(overlay_path),
            "manifest_path": str(manifest_path),
            "output_dir": str(output_dir),
        }
    except Exception:
        # Keep a failed directory for diagnosis only when Blender wrote evidence.
        if output_dir.exists() and not any(output_dir.iterdir()):
            output_dir.rmdir()
        raise


if __name__ == "__main__":
    # stdout is the MCP wire.  Do not print before or during this call.
    mcp.run(transport="stdio")
