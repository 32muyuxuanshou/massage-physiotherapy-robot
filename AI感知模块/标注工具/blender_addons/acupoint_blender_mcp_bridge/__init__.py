# SPDX-License-Identifier: MIT
"""Local, typed Blender bridge for the SKEL acupoint MCP server.

Socket threads only parse and enqueue requests.  Every bpy operation executes
from one persistent bpy.app.timers callback on Blender's main thread.
"""

from __future__ import annotations

import importlib
import hashlib
import json
import math
import os
import queue
import secrets
import socket
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import bpy
from bpy.types import Operator, Panel
from mathutils import Matrix, Vector


bl_info = {
    "name": "穴位 Blender MCP 桥接（内部研究）",
    "author": "Massage Therapy Robot Project",
    "version": (0, 2, 1),
    "blender": (4, 5, 0),
    "location": "3D Viewport > Sidebar > 穴位标注",
    "description": "只在本机开放受控的 SKEL Atlas、相机与单样本导出命令",
    "category": "3D View",
}


HOST = "127.0.0.1"
PORT = int(os.environ.get("ACUPOINT_MCP_PORT", "9877"))
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
SCHEMA_VERSION = "acupoint-blender-bridge-v1"
WRITE_SUBDIR = Path("outputs") / "BlenderMCP"
DELIVERY_SUBDIR = Path("outputs") / "交付文件"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _project_root() -> Path:
    configured = os.environ.get("ACUPOINT_MCP_PROJECT_ROOT", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend((Path(__file__).resolve(), Path(bpy.data.filepath).resolve() if bpy.data.filepath else Path()))
    for candidate in candidates:
        for parent in (candidate, *candidate.parents):
            if parent.name == "AI感知模块":
                return parent.resolve()
    raise RuntimeError("无法定位 AI感知模块；拒绝文件访问")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _read_path(raw_path: str, suffix: str) -> Path:
    root = _project_root()
    candidate = Path(raw_path).resolve()
    if not _inside(candidate, root):
        raise ValueError("文件不在 AI感知模块 许可目录内")
    if not candidate.is_file() or candidate.suffix.lower() != suffix:
        raise ValueError(f"无效的 {suffix} 文件：{candidate}")
    return candidate


def _write_dir(raw_path: str) -> Path:
    roots = [
        (_project_root() / WRITE_SUBDIR).resolve(),
        (_project_root() / DELIVERY_SUBDIR).resolve(),
    ]
    candidate = Path(raw_path).resolve()
    if not any(_inside(candidate, root) for root in roots):
        raise ValueError(f"输出目录必须位于：{roots}")
    if not candidate.is_dir():
        raise ValueError("输出目录不存在")
    return candidate


def _json_load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Atlas JSON 顶层必须是对象")
    return payload


def _annotator():
    try:
        return importlib.import_module("smpl_acupoint_annotator")
    except ImportError as exc:
        raise RuntimeError("未启用正式穴位插件 smpl_acupoint_annotator") from exc


def _training_core():
    try:
        return importlib.import_module("training_export_core")
    except ImportError as exc:
        raise RuntimeError("缺少内部训练导出核心 training_export_core") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_and_addon():
    addon = _annotator()
    target = addon._resolve_target(scene=bpy.context.scene)
    if target is None or target.type != "MESH":
        raise ValueError("当前场景没有设置穴位目标人体")
    return target, addon


def _matrix_rows(matrix: Matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def _object_original(obj):
    return getattr(obj, "original", obj) if obj is not None else None


def _camera_intrinsics(camera_data, width: int, height: int, scene, projection: Matrix) -> dict[str, Any]:
    pixel_aspect_x = float(scene.render.pixel_aspect_x)
    pixel_aspect_y = float(scene.render.pixel_aspect_y)
    # Derive K from the exact projection matrix Blender will use for this
    # requested output size.  This stays consistent with sensor fit, render
    # aspect and camera shifts without temporarily changing scene settings.
    fx = float(projection[0][0]) * width / 2.0
    fy = float(projection[1][1]) * height / 2.0
    cx = (1.0 - float(projection[0][2])) * width / 2.0
    cy = (1.0 + float(projection[1][2])) * height / 2.0
    return {
        "width": width,
        "height": height,
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
        "skew": 0.0,
        "K": [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
        "lens_mm": float(camera_data.lens),
        "sensor_width_mm": float(camera_data.sensor_width),
        "sensor_height_mm": float(camera_data.sensor_height),
        "sensor_fit": str(camera_data.sensor_fit),
        "pixel_aspect_x": pixel_aspect_x,
        "pixel_aspect_y": pixel_aspect_y,
        "shift_x": float(camera_data.shift_x),
        "shift_y": float(camera_data.shift_y),
        "pixel_coordinate_note": "continuous coordinates; image frame edges are 0 and width/height",
    }


def _project_world_point(
    point: Vector,
    world_to_blender_camera: Matrix,
    projection: Matrix,
    width: int,
    height: int,
) -> dict[str, Any]:
    camera_point = world_to_blender_camera @ point
    clip = projection @ camera_point.to_4d()
    if abs(float(clip.w)) <= 1e-12:
        return {
            "u": float("nan"),
            "v": float("nan"),
            "normalized_x": float("nan"),
            "normalized_y": float("nan"),
            "depth_m": -float(camera_point.z),
            "in_front": False,
        }
    ndc_x = float(clip.x / clip.w)
    ndc_y = float(clip.y / clip.w)
    normalized_x = (ndc_x + 1.0) / 2.0
    normalized_y = (ndc_y + 1.0) / 2.0
    depth_m = -float(camera_point.z)
    return {
        "u": normalized_x * width,
        "v": (1.0 - normalized_y) * height,
        "normalized_x": normalized_x,
        "normalized_y": normalized_y,
        "depth_m": depth_m,
        "in_front": depth_m > 0.0,
    }


def _validate_atlas_payload(payload: dict[str, Any], target, addon) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    schema = str(payload.get("schema_version") or "")
    if schema != addon.SCHEMA_VERSION:
        errors.append(f"训练导出只接受正式 {addon.SCHEMA_VERSION}，当前为 {schema or '缺失'}")
    model = payload.get("model") or {}
    target_model = addon._model_descriptor(target)
    source_family = str(model.get("family") or "").upper()
    if source_family != "SKEL":
        errors.append(f"正式路线要求 SKEL Atlas，当前文件为 {source_family or '未知模型'}")
    if target_model.get("family") != "SKEL":
        errors.append(f"当前目标不是 SKEL，而是 {target_model.get('family')}")
    source_gender = str(model.get("gender") or "").lower()
    target_gender = str(target_model.get("gender") or "").lower()
    if source_gender and target_gender and source_gender != target_gender:
        errors.append(f"性别不匹配：Atlas={source_gender}，人体={target_gender}")
    if int(model.get("vertex_count") or -1) != len(target.data.vertices):
        errors.append("顶点数量不匹配")
    if int(model.get("polygon_count") or -1) != len(target.data.polygons):
        errors.append("三角面数量不匹配")
    signature = str(model.get("topology_signature_sha256") or "")
    current_signature = addon._topology_signature(target)
    if signature != current_signature:
        errors.append("拓扑 SHA-256 不匹配")

    annotations = payload.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        errors.append("Atlas 不含穴位标注")
        annotations = []
    point_ids: set[str] = set()
    valid_annotations = 0
    for index, item in enumerate(annotations, start=1):
        if not isinstance(item, dict):
            errors.append(f"第 {index} 个标注不是对象")
            continue
        point_id = str(item.get("point_id") or "").strip().upper()
        if not point_id:
            errors.append(f"第 {index} 个标注缺少 point_id")
        elif point_id in point_ids:
            errors.append(f"重复 point_id：{point_id}")
        point_ids.add(point_id)
        if str(item.get("body_region") or "") in {"HEAD_FACE", "LEFT_HAND", "RIGHT_HAND"}:
            errors.append(f"{point_id or index} 超出 SKEL 躯干与四肢范围")
        try:
            face_index = int(item["face_index"])
            polygon = target.data.polygons[face_index]
            if len(polygon.vertices) != 3:
                raise ValueError("不是三角面")
            weights = [float(value) for value in item["barycentric"]]
            if len(weights) != 3 or not all(math.isfinite(value) for value in weights):
                raise ValueError("重心坐标无效")
            if abs(sum(weights) - 1.0) > 1e-5 or min(weights) < -1e-5 or max(weights) > 1.00001:
                raise ValueError("重心坐标不在三角形内")
            recorded_vertices = item.get("vertex_indices")
            if recorded_vertices is not None and tuple(int(value) for value in recorded_vertices) != tuple(polygon.vertices):
                raise ValueError("vertex_indices 与 face_index 不一致")
            valid_annotations += 1
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            errors.append(f"{point_id or index} 表面绑定无效：{exc}")
    if str(payload.get("plugin_version") or "") != str(addon.PLUGIN_VERSION):
        warnings.append(
            f"JSON plugin_version={payload.get('plugin_version')}；当前代码常量={addon.PLUGIN_VERSION}"
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "schema_version": schema,
        "annotation_count": len(annotations),
        "valid_annotation_count": valid_annotations,
        "source_model": model,
        "current_model": target_model,
    }


def _find_annotation(payload: dict[str, Any], point_id: str) -> dict[str, Any]:
    expected = point_id.strip().upper()
    for item in payload.get("annotations") or []:
        if str(item.get("point_id") or "").strip().upper() == expected:
            return item
    available = [str(item.get("point_id")) for item in (payload.get("annotations") or [])[:20]]
    raise KeyError(f"Atlas 中没有 {point_id}；前 20 个可用 ID：{available}")


def _point_sample(item: dict[str, Any], target, addon, depsgraph=None) -> dict[str, Any]:
    face_index = int(item["face_index"])
    weights = tuple(float(value) for value in item["barycentric"])
    point, normal, vertices = addon._surface_sample(target, face_index, weights, depsgraph=depsgraph)
    return {
        "point_id": str(item.get("point_id") or ""),
        "code": str(item.get("code") or ""),
        "name_zh": str(item.get("name_zh") or ""),
        "side": str(item.get("side") or ""),
        "body_region": str(item.get("body_region") or ""),
        "face_index": face_index,
        "vertex_indices": [int(value) for value in vertices],
        "barycentric": list(weights),
        "xyz_world_blender_m": [float(value) for value in point],
        "world_normal": [float(value) for value in normal],
        "_point": point,
        "_normal": normal,
    }


def command_ping(_params: dict[str, Any]) -> dict[str, Any]:
    return {"pong": True, "schema": SCHEMA_VERSION}


def command_status(_params: dict[str, Any]) -> dict[str, Any]:
    target = None
    addon_info = None
    try:
        target, addon = _target_and_addon()
        addon_info = {
            "bl_info_version": list(addon.bl_info.get("version", ())),
            "plugin_version_constant": addon.PLUGIN_VERSION,
            "schema_version": addon.SCHEMA_VERSION,
        }
    except Exception as exc:
        addon_info = {"error": str(exc)}
    return {
        "bridge_version": list(bl_info["version"]),
        "blender_version": bpy.app.version_string,
        "blend_path": bpy.data.filepath,
        "blend_saved": not bpy.data.is_dirty,
        "scene": bpy.context.scene.name,
        "formal_addon": addon_info,
        "target": (
            {
                "name": target.name,
                "family": _annotator()._model_family(target),
                "vertices": len(target.data.vertices),
                "polygons": len(target.data.polygons),
                "gender": str(target.get("gender") or target.get("skel_gender") or "unknown"),
            }
            if target is not None
            else None
        ),
        "notice": "MCP 不会自动保存 Blend；Blender 坐标不可直接用于机器人执行。",
    }


def command_prepare_annotation_draft(params: dict[str, Any]) -> dict[str, Any]:
    """Populate doctor-facing draft fields without creating or saving a point."""
    annotator = _annotator()
    scene = bpy.context.scene
    settings = getattr(scene, "smpl_acupoint_settings", None)
    if settings is None:
        raise RuntimeError("穴位标注插件尚未初始化")
    target = settings.target_mesh
    if target is None or target.type != "MESH":
        raise RuntimeError("当前场景没有有效的人体标注目标")
    if annotator._model_family(target) != "SKEL":
        raise ValueError("该命令只允许预填 SKEL 标注草稿")

    code = str(params.get("code", "")).strip().upper()
    name_zh = str(params.get("name_zh", "")).strip()
    meridian = str(params.get("meridian", "")).strip()
    notes = str(params.get("notes", "")).strip()
    side = str(params.get("side", "MIDLINE")).strip().upper()
    body_region = str(params.get("body_region", "TORSO")).strip().upper()
    valid_regions = {key for key, _label, _description in annotator.BODY_REGION_ITEMS}
    if not code or len(code) > 32:
        raise ValueError("编码不能为空且不得超过 32 个字符")
    if not name_zh or len(name_zh) > 64:
        raise ValueError("中文名称不能为空且不得超过 64 个字符")
    if side not in {"MIDLINE", "LEFT", "RIGHT"}:
        raise ValueError("医生标注侧别只能是 MIDLINE、LEFT 或 RIGHT")
    if body_region not in valid_regions:
        raise ValueError("身体分区不受支持")
    if len(notes) > 1000 or len(meridian) > 64:
        raise ValueError("草稿备注或经脉字段过长")

    settings.draft_code = code
    settings.draft_name_zh = name_zh
    settings.draft_meridian = meridian
    settings.draft_side = side
    settings.draft_body_region = body_region
    settings.draft_notes = notes
    checked_code, checked_name = annotator._validate_draft(scene)
    return {
        "prepared": True,
        "created_annotation": False,
        "saved": False,
        "code": checked_code,
        "name_zh": checked_name,
        "side": side,
        "body_region": body_region,
        "annotation_count": len(scene.smpl_acupoint_annotations),
    }


def command_inspect_scene(_params: dict[str, Any]) -> dict[str, Any]:
    target, addon = _target_and_addon()
    scene = bpy.context.scene
    settings = getattr(scene, "smpl_acupoint_settings", None)
    objects = [
        {
            "name": obj.name,
            "type": obj.type,
            "visible_viewport": not obj.hide_get(),
            "visible_render": not obj.hide_render,
            "role": str(obj.get("skel_role") or ""),
        }
        for obj in scene.objects
        if obj.type in {"MESH", "CAMERA", "ARMATURE"}
    ]
    return {
        "blend_path": bpy.data.filepath,
        "is_dirty": bpy.data.is_dirty,
        "target": addon._model_descriptor(target),
        "workflow_mode": str(settings.workflow_mode if settings else ""),
        "scene_annotation_count": len(getattr(scene, "smpl_acupoint_annotations", [])),
        "active_camera": scene.camera.name if scene.camera else None,
        "objects": objects,
    }


def command_validate_atlas(params: dict[str, Any]) -> dict[str, Any]:
    atlas_path = _read_path(str(params.get("atlas_path") or ""), ".json")
    target, addon = _target_and_addon()
    result = _validate_atlas_payload(_json_load(atlas_path), target, addon)
    return {"atlas_path": str(atlas_path), **result}


def command_get_acupoint_3d(params: dict[str, Any]) -> dict[str, Any]:
    atlas_path = _read_path(str(params.get("atlas_path") or ""), ".json")
    point_id = str(params.get("point_id") or "").strip()
    if not point_id:
        raise ValueError("point_id 不能为空")
    target, addon = _target_and_addon()
    payload = _json_load(atlas_path)
    validation = _validate_atlas_payload(payload, target, addon)
    if not validation["valid"]:
        raise ValueError("Atlas 校验失败：" + "；".join(validation["errors"][:10]))
    result = _point_sample(_find_annotation(payload, point_id), target, addon)
    result.pop("_point", None)
    result.pop("_normal", None)
    result["model"] = validation["current_model"]
    return result


def command_list_cameras(_params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    cameras = []
    for obj in scene.objects:
        if obj.type != "CAMERA":
            continue
        cameras.append(
            {
                "name": obj.name,
                "location": [float(value) for value in obj.location],
                "rotation_euler": [float(value) for value in obj.rotation_euler],
                "lens_mm": float(obj.data.lens),
                "active": obj == scene.camera,
                "created_by_mcp": bool(obj.get("acupoint_mcp_camera", False)),
            }
        )
    return {"active_camera": scene.camera.name if scene.camera else None, "cameras": cameras}


def _evaluated_world_bounds(target, depsgraph) -> tuple[Vector, Vector]:
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        if not points:
            raise ValueError("目标人体没有顶点")
        minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
        maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
        return minimum, maximum
    finally:
        evaluated.to_mesh_clear()


def command_set_camera_view(params: dict[str, Any]) -> dict[str, Any]:
    preset = str(params.get("preset") or "front").lower()
    if preset not in {"front", "back", "left", "right"}:
        raise ValueError("视角只支持 front/back/left/right")
    distance_scale = float(params.get("distance_scale", 1.0))
    focal_length = float(params.get("focal_length_mm", 50.0))
    camera_name = str(params.get("camera_name") or "ACU_MCP_CAMERA").strip()
    if not 0.5 <= distance_scale <= 4.0 or not 18.0 <= focal_length <= 200.0:
        raise ValueError("相机参数超出安全范围")
    if (
        not camera_name.startswith("ACU_")
        or len(camera_name) > 64
        or not all(character.isalnum() or character in "_-" for character in camera_name)
    ):
        raise ValueError("相机名称必须以 ACU_ 开头，且只含字母、数字、下划线或连字符")
    target, _addon = _target_and_addon()
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum, maximum = _evaluated_world_bounds(target, depsgraph)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    distance = max(float(size.x), float(size.y), float(size.z)) * 1.9 * distance_scale
    offsets = {
        "front": Vector((0.0, -distance, 0.0)),
        "back": Vector((0.0, distance, 0.0)),
        "left": Vector((-distance, 0.0, 0.0)),
        "right": Vector((distance, 0.0, 0.0)),
    }
    camera = bpy.data.objects.get(camera_name)
    if camera is not None and camera.type != "CAMERA":
        raise ValueError(f"场景中已存在同名非相机对象：{camera_name}")
    if camera is None:
        camera_data = bpy.data.cameras.new(f"{camera_name}_DATA")
        camera = bpy.data.objects.new(camera_name, camera_data)
        scene.collection.objects.link(camera)
        camera["acupoint_mcp_camera"] = True
    camera.location = center + offsets[preset]
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = focal_length
    camera.data.sensor_width = 36.0
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.shift_x = 0.0
    camera.data.shift_y = 0.0
    camera.data.clip_start = 0.01
    camera.data.clip_end = max(100.0, distance * 5.0)
    scene.camera = camera
    bpy.context.view_layer.update()
    return {
        "camera": camera.name,
        "preset": preset,
        "location": [float(value) for value in camera.location],
        "look_at": [float(value) for value in center],
        "lens_mm": float(camera.data.lens),
        "notice": "当前场景已改变但未保存；如不手动保存，关闭后不会写入 Blend。",
    }


def _visibility(scene, depsgraph, camera, target, point: Vector, normal: Vector) -> dict[str, Any]:
    camera_origin = camera.matrix_world.translation
    vector = point - camera_origin
    distance = vector.length
    if distance <= 1e-12:
        return {"front_facing": False, "visible_on_target": False, "ray_hit_object": None, "ray_hit_face_index": -1, "ray_error_m": None}
    direction = vector / distance
    front_facing = normal.dot(-direction) > 0.0
    tolerance = max(1e-4, distance * 1e-5)
    hit, hit_location, _hit_normal, face_index, hit_object, _matrix = scene.ray_cast(
        depsgraph, camera_origin, direction, distance=distance + tolerance
    )
    hit_original = _object_original(hit_object)
    target_hit = bool(hit and (hit_original == target or getattr(hit_original, "name", None) == target.name))
    ray_error = float((hit_location - point).length) if hit else None
    return {
        "front_facing": bool(front_facing),
        "visible_on_target": bool(target_hit and ray_error is not None and ray_error <= tolerance),
        "ray_hit_object": hit_original.name if hit_original is not None else None,
        "ray_hit_face_index": int(face_index) if hit else -1,
        "ray_error_m": ray_error,
        "ray_tolerance_m": tolerance,
    }


def _render_rgb(scene, output_path: Path, width: int, height: int) -> None:
    render = scene.render
    image_settings = render.image_settings
    saved = {
        "engine": render.engine,
        "filepath": render.filepath,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
        "file_format": image_settings.file_format,
        "color_mode": image_settings.color_mode,
        "film_transparent": render.film_transparent,
    }
    try:
        render.engine = "BLENDER_WORKBENCH"
        render.resolution_x = width
        render.resolution_y = height
        render.resolution_percentage = 100
        render.filepath = str(output_path)
        render.film_transparent = False
        image_settings.file_format = "PNG"
        image_settings.color_mode = "RGB"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        bpy.ops.render.render(write_still=True)
    finally:
        render.engine = saved["engine"]
        render.filepath = saved["filepath"]
        render.resolution_x = saved["resolution_x"]
        render.resolution_y = saved["resolution_y"]
        render.resolution_percentage = saved["resolution_percentage"]
        image_settings.file_format = saved["file_format"]
        image_settings.color_mode = saved["color_mode"]
        render.film_transparent = saved["film_transparent"]


def command_export_training_sample(params: dict[str, Any]) -> dict[str, Any]:
    atlas_path = _read_path(str(params.get("atlas_path") or ""), ".json")
    output_dir = _write_dir(str(params.get("output_dir") or ""))
    width = int(params.get("width", 640))
    height = int(params.get("height", 640))
    if not 128 <= width <= 4096 or not 128 <= height <= 4096:
        raise ValueError("图像宽高必须在 128–4096")
    requested_ids = [str(value).strip().upper() for value in (params.get("point_ids") or []) if str(value).strip()]
    if len(requested_ids) > 1000:
        raise ValueError("单样本最多 1000 个点")
    target, addon = _target_and_addon()
    payload = _json_load(atlas_path)
    validation = _validate_atlas_payload(payload, target, addon)
    if not validation["valid"]:
        raise ValueError("Atlas 校验失败：" + "；".join(validation["errors"][:10]))
    source_items = payload.get("annotations") or []
    if requested_ids:
        by_id = {str(item.get("point_id") or "").upper(): item for item in source_items}
        missing = [point_id for point_id in requested_ids if point_id not in by_id]
        if missing:
            raise KeyError(f"Atlas 不含这些 point_id：{missing}")
        source_items = [by_id[point_id] for point_id in requested_ids]

    scene = bpy.context.scene
    camera_name = str(params.get("camera_name") or "").strip()
    camera = bpy.data.objects.get(camera_name) if camera_name else scene.camera
    if camera is None or camera.type != "CAMERA":
        raise ValueError("没有可用相机；请先调用 set_camera_view")
    scene.camera = camera
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    core = _training_core()

    source_blend = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    source_dirty_at_start = bool(bpy.data.is_dirty)
    source_clean_at_start = bool(source_blend and source_blend.is_file() and not source_dirty_at_start)
    actual_source_sha256 = _file_sha256(source_blend) if source_blend and source_blend.is_file() else None
    expected_snapshot_sha256 = str(params.get("source_scene_snapshot_sha256") or "").strip().lower()
    if expected_snapshot_sha256:
        if len(expected_snapshot_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in expected_snapshot_sha256
        ):
            raise ValueError("source_scene_snapshot_sha256 必须是 64 位十六进制 SHA-256")
        if actual_source_sha256 != expected_snapshot_sha256:
            raise ValueError("当前 Blend 文件与声明的场景快照 SHA-256 不一致")
    snapshot_sha256 = (
        expected_snapshot_sha256
        or (actual_source_sha256 if source_clean_at_start else None)
    )
    bindings = [
        {
            "point_id": str(item.get("point_id") or ""),
            "code": str(item.get("code") or ""),
            "name_zh": str(item.get("name_zh") or ""),
            "side": str(item.get("side") or ""),
            "body_region": str(item.get("body_region") or ""),
            "face_index": int(item["face_index"]),
            "vertex_indices": [
                int(value)
                for value in (
                    item.get("vertex_indices")
                    or target.data.polygons[int(item["face_index"])].vertices
                )
            ],
            "barycentric": [float(value) for value in item["barycentric"]],
        }
        for item in source_items
    ]
    exported = core.export_sample(
        scene=scene,
        depsgraph=depsgraph,
        camera=camera,
        skin_object=target,
        bindings=bindings,
        output_dir=output_dir,
        frame=int(scene.frame_current),
        width=width,
        height=height,
        render_engine="BLENDER_EEVEE_NEXT",
        ray_tolerance_m=1e-4,
        mask_depth_tolerance_m=1e-4,
    )
    points: list[dict[str, Any]] = []
    for point in exported.points:
        normalized = dict(point)
        normalized["xyz_world_blender_m"] = normalized.pop("xyz_world_m")
        normalized.pop("object_name", None)
        points.append(normalized)

    buffers = exported.buffers
    render_camera = buffers.metadata["camera"]
    intrinsics = render_camera["intrinsics"]
    world_to_blender_camera = camera.matrix_world.inverted()
    world_to_opencv_camera = core.world_to_opencv_camera(camera)
    projection = camera.calc_matrix_camera(
        depsgraph,
        x=width,
        y=height,
        scale_x=float(scene.render.pixel_aspect_x),
        scale_y=float(scene.render.pixel_aspect_y),
    )
    labels_path = output_dir / "labels.json"
    if labels_path.exists():
        raise FileExistsError("拒绝覆盖已有 labels.json")
    labels = {
        "schema_version": "acupoint-training-sample-v2",
        "created_at": _utc_now(),
        "source_blend": str(source_blend) if source_blend else "",
        "source_blend_dirty": source_dirty_at_start,
        "source_scene_snapshot_sha256": snapshot_sha256,
        "source_atlas": str(atlas_path),
        "source_atlas_sha256": _file_sha256(atlas_path),
        "scene": {
            "name": scene.name,
            "frame": int(scene.frame_current),
            "snapshot_replayable": bool(snapshot_sha256),
            "snapshot_sha256": snapshot_sha256,
            "dirty_at_export_start": source_dirty_at_start,
            "replay_notice": (
                "明确提供并核对了快照哈希；仍必须用独立 Blender 重开复验。"
                if expected_snapshot_sha256
                else "仅当场景未修改时，当前文件哈希才能代表导出场景。"
            ),
            "unit": "m",
            "unit_scale_length": float(scene.unit_settings.scale_length),
        },
        "model": validation["current_model"],
        "camera": {
            "name": camera.name,
            "coordinate_convention": "OpenCV camera: +X right, +Y down, +Z forward; pixel origin top-left",
            "pixel_coordinate_note": "continuous edge coordinates; pixel center (column,row) is (column+0.5,row+0.5)",
            "intrinsics": intrinsics,
            "world_to_blender_camera": _matrix_rows(world_to_blender_camera),
            "world_to_opencv_camera": _matrix_rows(world_to_opencv_camera),
            "blender_projection_matrix": _matrix_rows(projection),
            "distortion": {
                "model": "NONE_SYNTHETIC_PINHOLE",
                "coefficients": [],
                "notice": "真实 RGB-D 相机必须另行标定内参、外参和畸变。",
            },
        },
        "buffers": {
            "scene_depth_z": {
                "file": "scene_depth_z.npy",
                "dtype": "float32",
                "unit": "m",
                "meaning": "OPENCV_CAMERA_Z_FIRST_VISIBLE_SCENE_SURFACE",
                "background_value": 0.0,
            },
            "depth_valid_mask": {
                "file": "depth_valid_mask.png",
                "dtype": "uint8",
                "values": [0, 255],
            },
            "skin_mask": {
                "file": "skin_mask.png",
                "dtype": "uint8",
                "meaning": "VISIBLE_SKEL_SKIN_FIRST_SURFACE",
                "values": [0, 255],
            },
        },
        "render": buffers.metadata,
        "points": points,
        "notices": [
            "SKEL 是结构先验，不是患者 CT。",
            "这是 Blender 合成相机坐标，不是机器人执行坐标。",
            "穴位随人体传播仍需医生验证。",
            "当前 Atlas 中的 111 是工程测试点，不是医学真值。",
        ],
    }
    temporary = labels_path.with_suffix(".json.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(labels, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, labels_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "rgb_path": str(buffers.rgb_path),
        "scene_depth_z_path": str(buffers.scene_depth_path),
        "depth_valid_mask_path": str(buffers.valid_mask_path),
        "skin_mask_path": str(buffers.skin_mask_path),
        "render_metadata_path": str(buffers.metadata_path),
        "labels_path": str(labels_path),
        "point_count": len(points),
        "visible_count": sum(1 for point in points if point["visible"]),
        "camera": camera.name,
        "source_scene_replayable": bool(snapshot_sha256),
        "source_scene_snapshot_sha256": snapshot_sha256,
        "notice": "只导出了样本文件，没有保存或覆盖 Blend。",
    }


COMMANDS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "ping": command_ping,
    "status": command_status,
    "inspect_scene": command_inspect_scene,
    "prepare_annotation_draft": command_prepare_annotation_draft,
    "validate_atlas": command_validate_atlas,
    "get_acupoint_3d": command_get_acupoint_3d,
    "list_cameras": command_list_cameras,
    "set_camera_view": command_set_camera_view,
    "export_training_sample": command_export_training_sample,
}


@dataclass
class WorkItem:
    request: dict[str, Any]
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class AcupointBridgeServer:
    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self.running = False
        self.token = secrets.token_hex(32)
        self.socket: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.queue: queue.Queue[WorkItem] = queue.Queue(maxsize=64)
        self._clients: set[socket.socket] = set()
        self._clients_lock = threading.Lock()
        self._timer_callback = self._drain_queue

    def start(self) -> None:
        if self.running:
            return
        if self.host != "127.0.0.1":
            raise RuntimeError("安全策略只允许绑定 127.0.0.1")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        server_socket.settimeout(1.0)
        self.socket = server_socket
        self.running = True
        self.thread = threading.Thread(target=self._server_loop, name="AcupointMCPBridge", daemon=True)
        self.thread.start()
        if not bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.register(self._timer_callback, first_interval=0.05, persistent=True)
        print(f"Acupoint Blender MCP bridge started on {self.host}:{self.port}")

    def stop(self) -> None:
        self.running = False
        if bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.unregister(self._timer_callback)
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None
        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None
        print("Acupoint Blender MCP bridge stopped")

    def _server_loop(self) -> None:
        while self.running and self.socket is not None:
            try:
                client, address = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if address[0] not in {"127.0.0.1", "::1"}:
                client.close()
                continue
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    @staticmethod
    def _send(client: socket.socket, response: dict[str, Any]) -> None:
        data = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > MAX_RESPONSE_BYTES:
            data = (json.dumps({"status": "error", "message": "响应超过 8 MiB 安全上限"}, ensure_ascii=False) + "\n").encode("utf-8")
        client.sendall(data)

    def _handle_client(self, client: socket.socket) -> None:
        client.settimeout(130.0)
        with self._clients_lock:
            self._clients.add(client)
        try:
            buffer = bytearray()
            while len(buffer) <= MAX_REQUEST_BYTES:
                chunk = client.recv(65536)
                if not chunk:
                    return
                buffer.extend(chunk)
                if b"\n" in buffer:
                    break
            if len(buffer) > MAX_REQUEST_BYTES:
                self._send(client, {"status": "error", "message": "请求超过 1 MiB 安全上限"})
                return
            line, separator, _rest = bytes(buffer).partition(b"\n")
            if not separator:
                self._send(client, {"status": "error", "message": "请求缺少换行帧结束符"})
                return
            request = json.loads(line.decode("utf-8"))
            request_id = str(request.get("id") or "")
            if request.get("type") == "pair":
                self._send(client, {"id": request_id, "status": "success", "result": {"token": self.token}})
                return
            supplied = request.get("token") if isinstance(request.get("token"), str) else ""
            if not secrets.compare_digest(supplied, self.token):
                self._send(client, {"id": request_id, "status": "error", "message": "配对令牌无效"})
                return
            item = WorkItem(request=request)
            try:
                self.queue.put(item, timeout=2.0)
            except queue.Full:
                self._send(client, {"id": request_id, "status": "error", "message": "Blender 命令队列已满"})
                return
            if not item.event.wait(timeout=125.0):
                self._send(client, {"id": request_id, "status": "error", "message": "Blender 主线程执行超时"})
                return
            self._send(client, item.response or {"id": request_id, "status": "error", "message": "空响应"})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            try:
                self._send(client, {"status": "error", "message": f"协议错误：{exc}"})
            except OSError:
                pass
        finally:
            with self._clients_lock:
                self._clients.discard(client)
            try:
                client.close()
            except OSError:
                pass

    def _drain_queue(self):
        if not self.running:
            return None
        for _index in range(16):
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            request_id = str(item.request.get("id") or "")
            try:
                command_type = str(item.request.get("type") or "")
                handler = COMMANDS.get(command_type)
                if handler is None:
                    raise ValueError(f"不支持的命令：{command_type}")
                params = item.request.get("params") or {}
                if not isinstance(params, dict):
                    raise ValueError("params 必须是 JSON 对象")
                result = handler(params)
                item.response = {"id": request_id, "status": "success", "result": result}
            except Exception as exc:
                traceback.print_exc()
                item.response = {"id": request_id, "status": "error", "message": str(exc)}
            finally:
                item.event.set()
        return 0.05


_server: AcupointBridgeServer | None = None


def _ensure_started():
    global _server
    if bpy.app.background:
        return None
    if _server is None:
        _server = AcupointBridgeServer()
    if not _server.running:
        try:
            _server.start()
        except OSError as exc:
            print(f"Acupoint Blender MCP bridge failed to start: {exc}")
    return None


class ACUPOINT_MCP_OT_start(Operator):
    bl_idname = "acupoint_mcp.start_bridge"
    bl_label = "启动本机 MCP"

    def execute(self, _context):
        _ensure_started()
        if _server and _server.running:
            self.report({"INFO"}, f"穴位 MCP 已监听 {HOST}:{PORT}")
            return {"FINISHED"}
        self.report({"ERROR"}, "穴位 MCP 启动失败；端口可能被占用")
        return {"CANCELLED"}


class ACUPOINT_MCP_OT_stop(Operator):
    bl_idname = "acupoint_mcp.stop_bridge"
    bl_label = "停止本机 MCP"

    def execute(self, _context):
        if _server:
            _server.stop()
        self.report({"INFO"}, "穴位 MCP 已停止")
        return {"FINISHED"}


class ACUPOINT_MCP_PT_panel(Panel):
    bl_label = "Codex 自动化（内部）"
    bl_idname = "ACUPOINT_MCP_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "穴位标注"
    bl_order = 1000

    def draw(self, _context):
        layout = self.layout
        running = bool(_server and _server.running)
        box = layout.box()
        box.label(text=("MCP 已连接本机" if running else "MCP 未启动"), icon=("CHECKMARK" if running else "ERROR"))
        box.label(text=f"127.0.0.1:{PORT}")
        row = box.row(align=True)
        row.operator("acupoint_mcp.start_bridge", text="启动")
        row.operator("acupoint_mcp.stop_bridge", text="停止")
        layout.label(text="不开放任意 Python；不会自动保存")
        layout.label(text="仅供内部研究，不是机器人坐标")


CLASSES = (ACUPOINT_MCP_OT_start, ACUPOINT_MCP_OT_stop, ACUPOINT_MCP_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    if not bpy.app.background:
        # Add-on registration runs on Blender's main thread, so socket startup
        # and the single persistent queue timer can be registered safely here.
        # Starting immediately also works when Blender is launched hidden for
        # automated tests, where a deferred UI timer may not get its first tick.
        _ensure_started()


def unregister():
    global _server
    if _server:
        _server.stop()
        _server = None
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
