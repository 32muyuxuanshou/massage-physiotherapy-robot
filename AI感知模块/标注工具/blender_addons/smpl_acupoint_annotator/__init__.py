# SPDX-License-Identifier: MIT
"""Doctor-facing surface annotation helpers for SMPL, SMPL-X, and SKEL meshes.

The durable location of each annotation is stored as a triangle face index and
barycentric coordinates.  Cartesian coordinates are derived values and are
updated whenever shape keys, armature pose, or object transforms change.
"""

bl_info = {
    "name": "SKEL/SMPL-X 穴位 Atlas 标注",
    "author": "Massage Therapy Robot Project",
    "version": (0, 6, 3),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Sidebar > 穴位标注",
    "description": "在启动器锁定的 SKEL 或 SMPL-X 表面标注，并保存拓扑指纹、面编号和重心坐标",
    "category": "3D View",
}

import json
import hashlib
import math
import os
import uuid
from datetime import datetime, timezone

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy_extras import view3d_utils
from mathutils import Vector

from .chinese_ui import (
    enable_blender_chinese,
    register_translations,
    unregister_translations,
)


SCHEMA_VERSION = "smpl-acupoint-annotation-v5"
LEGACY_SCHEMA_VERSIONS = {
    "smpl-acupoint-annotation-v1",
    "smpl-acupoint-annotation-v2",
    "smpl-acupoint-annotation-v3",
    "smpl-acupoint-annotation-v4",
}
PLUGIN_VERSION = "0.6.3"
ATLAS_VERSION = "trunk-limb-atlas-v1"
PROTOCOL_VERSION = "doctor-annotation-protocol-v2"
MARKER_COLLECTION_NAME = "SMPL_穴位标记"
_refreshing_markers = False
_updating_pose = False
_suspend_autosave = False
_autosave_in_progress = False


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _deployment_export_path():
    """Return a doctor-session export path when launched by the deployment UI."""
    export_root = os.environ.get("SMPL_ACUPOINT_EXPORT_ROOT", "").strip()
    if not export_root:
        return ""
    os.makedirs(export_root, exist_ok=True)
    blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    blend_name = blend_name or "穴位标注"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(export_root, f"{blend_name}_穴位标注_{timestamp}.json")


def _deployment_export_root():
    export_root = os.environ.get("SMPL_ACUPOINT_EXPORT_ROOT", "").strip()
    if export_root:
        os.makedirs(export_root, exist_ok=True)
    return export_root


def _safe_filename(value, fallback):
    cleaned = "".join(char if char not in '\\/:*?\"<>|' else "_" for char in value.strip())
    return cleaned or fallback


def _is_doctor_mode(scene):
    settings = getattr(scene, "smpl_acupoint_settings", None)
    return bool(settings and settings.workflow_mode == "DOCTOR_ATLAS")


def _is_simple_ui(scene):
    settings = getattr(scene, "smpl_acupoint_settings", None)
    return bool(settings and (settings.workflow_mode == "DOCTOR_ATLAS" or settings.simple_ui))


def _expected_doctor_family(scene):
    """Return the annotation family explicitly locked by the launcher/template."""
    configured = os.environ.get("SMPL_ACUPOINT_ATLAS_FAMILY", "").strip().upper()
    if configured in {"SKEL", "SMPL-X"}:
        return configured
    stored = str(scene.get("acupoint_atlas_family", "")).strip().upper()
    if stored in {"SKEL", "SMPL-X"}:
        return stored
    settings = getattr(scene, "smpl_acupoint_settings", None)
    return _model_family(settings.target_mesh) if settings and settings.target_mesh else ""


def _session_metadata(scene):
    settings = scene.smpl_acupoint_settings
    return {
        "session_id": settings.session_id,
        "doctor_id": settings.doctor_id,
        "task_id": settings.task_id,
        "workflow_mode": settings.workflow_mode,
        "template_id": settings.template_id,
        "template_gender": settings.template_gender,
        "template_file_sha256": settings.template_file_sha256,
        "atlas_version": settings.atlas_version or ATLAS_VERSION,
        "protocol_version": settings.protocol_version or PROTOCOL_VERSION,
        "resumed_from_session_id": settings.resumed_from_session_id,
    }


def _initialize_session(scene):
    """Receive trusted launcher metadata and lock the doctor annotation target."""
    settings = getattr(scene, "smpl_acupoint_settings", None)
    if settings is None:
        return
    env_map = {
        "session_id": "SMPL_ACUPOINT_SESSION_ID",
        "doctor_id": "SMPL_ACUPOINT_DOCTOR_ID",
        "task_id": "SMPL_ACUPOINT_TASK_ID",
        "template_id": "SMPL_ACUPOINT_TEMPLATE_ID",
        "template_gender": "SMPL_ACUPOINT_TEMPLATE_GENDER",
        "template_file_sha256": "SMPL_ACUPOINT_TEMPLATE_FILE_SHA256",
        "resumed_from_session_id": "SMPL_ACUPOINT_RESUMED_FROM_SESSION_ID",
    }
    for property_name, environment_name in env_map.items():
        value = os.environ.get(environment_name, "").strip()
        if value:
            setattr(settings, property_name, value)
    workflow_mode = os.environ.get("SMPL_ACUPOINT_WORKFLOW_MODE", "").strip()
    if workflow_mode in {"DOCTOR_ATLAS", "RESEARCH"}:
        settings.workflow_mode = workflow_mode
    simple_ui = os.environ.get("SMPL_ACUPOINT_SIMPLE_UI", "").strip().lower()
    if simple_ui in {"1", "true", "yes"}:
        settings.simple_ui = True
    atlas_family = os.environ.get("SMPL_ACUPOINT_ATLAS_FAMILY", "").strip().upper()
    if atlas_family in {"SKEL", "SMPL-X"}:
        scene["acupoint_atlas_family"] = atlas_family
    if not settings.atlas_version:
        settings.atlas_version = ATLAS_VERSION
    if not settings.protocol_version:
        settings.protocol_version = PROTOCOL_VERSION

    target = settings.target_mesh
    if target is None:
        target = next(
            (
                obj for obj in scene.objects
                if obj.type == "MESH" and bool(
                    obj.get("acupoint_template_target", False)
                    or obj.get("smplx_template_target", False)
                )
            ),
            None,
        )
    if target is None:
        target = next(
            (
                obj for obj in scene.objects
                if obj.type == "MESH" and str(obj.get("body_model", "")).lower() == "smplx"
            ),
            None,
        )
    if target is None:
        target = next(
            (
                obj for obj in scene.objects
                if obj.type == "MESH" and str(obj.get("body_model", "")).lower() == "skel"
                and str(obj.get("skel_role", "")).lower() == "skin"
            ),
            None,
        )
    if target is not None:
        settings.target_mesh = target
        if _is_doctor_mode(scene):
            target.hide_select = True
            armature = target.parent if target.parent and target.parent.type == "ARMATURE" else None
            if armature is not None:
                armature.hide_select = True
                armature.hide_set(True)
                armature.hide_render = True


def _finish_doctor_workspace_setup():
    """Frame the patient and activate the doctor panel after screen maximization."""
    try:
        for window in bpy.context.window_manager.windows:
            scene = window.scene
            if not _is_simple_ui(scene):
                continue
            screen = window.screen
            view_areas = [area for area in screen.areas if area.type == "VIEW_3D"]
            if not view_areas:
                continue
            area = max(view_areas, key=lambda candidate: candidate.width * candidate.height)
            space = area.spaces.active
            space.show_region_ui = True
            space.show_region_toolbar = False
            space.overlay.show_relationship_lines = False
            ui_region = next((region for region in area.regions if region.type == "UI"), None)
            if ui_region is not None:
                ui_region.active_panel_category = "穴位标注"

            target = scene.smpl_acupoint_settings.target_mesh
            window_region = next((region for region in area.regions if region.type == "WINDOW"), None)
            if target is not None and window_region is not None:
                target.hide_select = False
                bpy.ops.object.select_all(action="DESELECT")
                target.select_set(True)
                window.view_layer.objects.active = target
                with bpy.context.temp_override(
                    window=window,
                    screen=screen,
                    area=area,
                    region=window_region,
                    scene=scene,
                ):
                    try:
                        bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
                        bpy.ops.view3d.view_selected(use_all_regions=False)
                    except RuntimeError:
                        pass
                target.hide_select = True
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return None


def _configure_doctor_workspaces():
    """Open a distraction-free 3D view after a doctor session is loaded."""
    try:
        for window in bpy.context.window_manager.windows:
            scene = window.scene
            if not _is_simple_ui(scene):
                continue
            screen = window.screen
            view_areas = [area for area in screen.areas if area.type == "VIEW_3D"]
            if not view_areas:
                continue
            area = max(view_areas, key=lambda candidate: candidate.width * candidate.height)
            if len(screen.areas) > 1:
                with bpy.context.temp_override(window=window, screen=screen, area=area):
                    try:
                        bpy.ops.screen.screen_full_area(use_hide_panels=False)
                    except RuntimeError:
                        pass
        _finish_doctor_workspace_setup()
        if not bpy.app.timers.is_registered(_finish_doctor_workspace_setup):
            bpy.app.timers.register(_finish_doctor_workspace_setup, first_interval=0.6)
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return None


def _point_id(code, side):
    return f"{code.strip().upper()}_{side}"


def _validate_draft(scene):
    settings = scene.smpl_acupoint_settings
    code = settings.draft_code.strip().upper()
    name_zh = settings.draft_name_zh.strip()
    if not code:
        raise ValueError("请先填写穴位标准编码")
    if not name_zh:
        raise ValueError("请先填写穴位中文名称")
    if settings.draft_side not in {"MIDLINE", "LEFT", "RIGHT"}:
        raise ValueError("正式标注只能选择中线、左侧或右侧；双侧穴位请分别标左右两个点")
    if (
        _is_doctor_mode(scene)
        and _expected_doctor_family(scene) == "SKEL"
        and settings.draft_body_region in {"HEAD_FACE", "LEFT_HAND", "RIGHT_HAND"}
    ):
        raise ValueError("当前 SKEL Atlas 只用于躯干和四肢，不收集头面部或手部穴位")
    point_id = _point_id(code, settings.draft_side)
    for item in scene.smpl_acupoint_annotations:
        if _point_id(item.code, item.side) == point_id:
            raise ValueError(f"{code} 的该侧别已经标注，请先定位或删除原标注")
    return code, name_zh


def _validate_scene(scene, require_annotations=False):
    settings = scene.smpl_acupoint_settings
    target = settings.target_mesh
    if target is None or target.type != "MESH":
        raise ValueError("没有锁定的医生标注人体")
    if _is_doctor_mode(scene):
        actual_family = _model_family(target)
        expected_family = _expected_doctor_family(scene)
        if expected_family not in {"SKEL", "SMPL-X"}:
            raise ValueError("模板没有声明正式标注模型族")
        if actual_family != expected_family:
            raise ValueError(
                f"当前入口只允许在 {expected_family} 表面标注，不能改用 {actual_family}"
            )
        expected_signature = str(
            target.get("acupoint_template_topology_sha256", "")
            or target.get("smplx_template_topology_sha256", "")
        ).strip()
        actual_signature = _topology_signature(target)
        if not expected_signature:
            raise ValueError("模板缺少拓扑身份，不能作为正式医生标注模板")
        if expected_signature != actual_signature:
            raise ValueError("人体拓扑已发生变化，已阻止正式保存")
        expected_shape = str(
            target.get("acupoint_template_shape_sha256", "")
            or target.get("smplx_template_shape_sha256", "")
        ).strip()
        if not expected_shape:
            raise ValueError("模板缺少规范体型身份，不能作为正式医生标注模板")
        if expected_shape != _shape_signature(target):
            raise ValueError("人体体型参数已改变，已阻止正式保存；请重新打开工作副本")
        expected_pose = str(
            target.get("acupoint_template_pose_sha256", "")
            or target.get("smplx_template_pose_sha256", "")
        ).strip()
        if not expected_pose:
            raise ValueError("模板缺少规范姿态身份，不能作为正式医生标注模板")
        if expected_pose != _pose_signature(target):
            raise ValueError("人体姿态已改变，已阻止正式保存；请重新打开工作副本")
        for field_name, label in (
            (settings.session_id, "会话编号"),
            (settings.doctor_id, "医生编号"),
            (settings.task_id, "任务编号"),
            (settings.template_id, "模板编号"),
            (settings.template_gender, "模板性别"),
        ):
            if not field_name.strip():
                raise ValueError(f"缺少{label}，请从医生启动器重新打开")
    if require_annotations and not scene.smpl_acupoint_annotations:
        raise ValueError("当前还没有穴位标注")
    seen = set()
    for index, item in enumerate(scene.smpl_acupoint_annotations, start=1):
        if not item.code.strip() or not item.name_zh.strip():
            raise ValueError(f"第 {index} 个标注缺少编码或中文名称")
        if _is_doctor_mode(scene) and item.side not in {"MIDLINE", "LEFT", "RIGHT"}:
            raise ValueError(f"第 {index} 个标注侧别无效；双侧必须拆成左右两个点")
        item_point_id = _point_id(item.code, item.side)
        if item_point_id in seen:
            raise ValueError(f"发现重复穴位：{item.code}（{item.side}）")
        seen.add(item_point_id)
        if (
            _is_doctor_mode(scene)
            and _expected_doctor_family(scene) == "SKEL"
            and item.body_region in {"HEAD_FACE", "LEFT_HAND", "RIGHT_HAND"}
        ):
            raise ValueError(
                f"第 {index} 个标注超出当前 SKEL 躯干与四肢任务范围：{item.code}"
            )
        if bpy.data.objects.get(item.target_name) is None:
            raise ValueError(f"标注 {item.code} 的目标人体不存在，不能静默跳过")
    return target


def _mesh_poll(_self, obj):
    return obj is not None and obj.type == "MESH"


BODY_REGION_ITEMS = (
    ("HEAD_FACE", "头面部", "头皮、面部、耳周与下颌区域"),
    ("NECK", "颈部", "颈前、颈侧与项部"),
    ("TORSO", "躯干", "胸、腹、背、腰、骶部"),
    ("LEFT_ARM", "左上肢", "左肩、臂、肘与前臂，不含手"),
    ("RIGHT_ARM", "右上肢", "右肩、臂、肘与前臂，不含手"),
    ("LEFT_HAND", "左手", "左腕、手掌、手背与手指"),
    ("RIGHT_HAND", "右手", "右腕、手掌、手背与手指"),
    ("LEFT_LEG", "左下肢", "左髋、腿、膝、踝与足"),
    ("RIGHT_LEG", "右下肢", "右髋、腿、膝、踝与足"),
    ("OTHER", "其他/待定", "由医生复核后归类"),
)


def _model_family(target):
    if target is None or target.type != "MESH":
        return "NONE"
    body_model = str(target.get("body_model", "")).lower()
    if body_model == "skel" or target.name.upper().startswith("SKEL-SKIN-"):
        return "SKEL"
    if body_model == "smplx" or target.name.upper().startswith("SMPLX-"):
        return "SMPL-X"
    if len(target.data.vertices) == 10475:
        return "SMPL-X"
    if len(target.data.vertices) == 6890:
        return "SMPL"
    return "CUSTOM"


def _topology_signature(target):
    """Stable hash of vertex count and ordered polygon vertex indices."""
    digest = hashlib.sha256()
    digest.update(f"v={len(target.data.vertices)};p={len(target.data.polygons)};".encode("ascii"))
    for polygon in target.data.polygons:
        digest.update(",".join(str(int(index)) for index in polygon.vertices).encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()


def _model_descriptor(target):
    if target is None:
        return None
    gender = target.get("smplx_gender") or target.get("gender") or "unknown"
    family = _model_family(target)
    return {
        "family": _model_family(target),
        "variant": str(
            target.get("skel_version", "") if family == "SKEL"
            else target.get("smplx_version", "standard")
        ),
        "gender": str(gender),
        "template_id": str(
            target.get("acupoint_template_id", "")
            or target.get("smplx_template_id", "")
        ),
        "canonical_shape_id": str(
            target.get("acupoint_canonical_shape_id", "")
            or target.get("smplx_canonical_shape_id", "shape-zero")
        ),
        "canonical_pose_id": str(
            target.get("acupoint_canonical_pose_id", "")
            or target.get("smplx_canonical_pose_id", "template-default")
        ),
        "object_name": target.name,
        "vertex_count": len(target.data.vertices),
        "polygon_count": len(target.data.polygons),
        "topology_signature_sha256": _topology_signature(target),
    }


def _resolve_target(context=None, scene=None):
    scene = scene or (context.scene if context else bpy.context.scene)
    settings = getattr(scene, "smpl_acupoint_settings", None)
    if settings and settings.target_mesh and settings.target_mesh.type == "MESH":
        return settings.target_mesh

    active = context.active_object if context else bpy.context.active_object
    if active and active.type == "MESH":
        return active
    if active and active.type == "ARMATURE":
        return next((child for child in active.children if child.type == "MESH"), None)
    return None


def _ensure_marker_collection(scene):
    collection = bpy.data.collections.get(MARKER_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(MARKER_COLLECTION_NAME)
    if collection.name not in {child.name for child in scene.collection.children}:
        scene.collection.children.link(collection)
    return collection


def _barycentric_weights(point, a, b, c):
    v0 = b - a
    v1 = c - a
    v2 = point - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) < 1e-12:
        raise ValueError("命中的三角形退化，无法计算重心坐标")
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    u = 1.0 - v - w
    return (u, v, w)


def _surface_sample(target, face_index, barycentric, depsgraph=None):
    """Return evaluated world point, world normal, and triangle vertex ids."""
    if target is None or target.type != "MESH":
        raise ValueError("目标对象不是网格")
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        if face_index < 0 or face_index >= len(evaluated_mesh.polygons):
            raise IndexError(f"面编号 {face_index} 超出模型范围")
        polygon = evaluated_mesh.polygons[face_index]
        vertex_ids = tuple(polygon.vertices)
        if len(vertex_ids) != 3:
            raise ValueError("当前版本仅支持三角网格；请先对目标模型进行三角化")
        weights = tuple(float(value) for value in barycentric)
        local_point = Vector((0.0, 0.0, 0.0))
        for weight, vertex_id in zip(weights, vertex_ids):
            local_point += evaluated_mesh.vertices[vertex_id].co * weight
        world_point = evaluated.matrix_world @ local_point
        normal_matrix = evaluated.matrix_world.inverted().transposed().to_3x3()
        world_normal = (normal_matrix @ polygon.normal).normalized()
        return world_point, world_normal, vertex_ids
    finally:
        evaluated.to_mesh_clear()


def _canonical_local_sample(target, face_index, barycentric):
    """Return a stable point on the undeformed template mesh."""
    if face_index < 0 or face_index >= len(target.data.polygons):
        raise IndexError(f"面编号 {face_index} 超出基础模板范围")
    polygon = target.data.polygons[face_index]
    vertex_ids = tuple(polygon.vertices)
    if len(vertex_ids) != 3:
        raise ValueError("基础模板不是三角网格")
    point = Vector((0.0, 0.0, 0.0))
    for weight, vertex_id in zip(barycentric, vertex_ids):
        point += target.data.vertices[vertex_id].co * float(weight)
    return point


def _raycast_target(context, target, event):
    area = context.area
    if area is None or area.type != "VIEW_3D":
        return None
    window_region = next((region for region in area.regions if region.type == "WINDOW"), None)
    region_3d = context.space_data.region_3d
    if window_region is None or region_3d is None:
        return None

    region_x = event.mouse_x - window_region.x
    region_y = event.mouse_y - window_region.y
    if not (0 <= region_x < window_region.width and 0 <= region_y < window_region.height):
        return None

    coord = (region_x, region_y)
    ray_origin_world = view3d_utils.region_2d_to_origin_3d(window_region, region_3d, coord)
    ray_direction_world = view3d_utils.region_2d_to_vector_3d(window_region, region_3d, coord)

    depsgraph = context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    inverse = evaluated.matrix_world.inverted()
    ray_origin_local = inverse @ ray_origin_world
    ray_direction_local = (inverse.to_3x3() @ ray_direction_world).normalized()
    hit, location, normal, face_index = evaluated.ray_cast(ray_origin_local, ray_direction_local)
    if not hit or face_index < 0:
        return None

    evaluated_mesh = evaluated.to_mesh()
    try:
        polygon = evaluated_mesh.polygons[face_index]
        vertex_ids = tuple(polygon.vertices)
        if len(vertex_ids) != 3:
            raise ValueError("目标模型不是三角网格")
        if face_index >= len(target.data.polygons):
            raise ValueError("当前变形改变了模型拓扑，不能建立稳定表面绑定")
        base_vertex_ids = tuple(target.data.polygons[face_index].vertices)
        if vertex_ids != base_vertex_ids:
            raise ValueError("当前变形改变了三角面顺序或顶点索引，不能建立稳定表面绑定")
        a, b, c = (evaluated_mesh.vertices[index].co.copy() for index in vertex_ids)
        barycentric = _barycentric_weights(location, a, b, c)
    finally:
        evaluated.to_mesh_clear()

    world_point = evaluated.matrix_world @ location
    normal_matrix = evaluated.matrix_world.inverted().transposed().to_3x3()
    world_normal = (normal_matrix @ normal).normalized()
    return face_index, barycentric, world_point, world_normal


def _marker_display_label(item):
    """Return the doctor-facing label shown beside a viewport marker."""
    name_zh = item.name_zh.strip()
    code = item.code.strip()
    if name_zh and code and name_zh.casefold() != code.casefold():
        label = f"{name_zh}（{code}）"
    else:
        label = name_zh or code or "未命名穴位"

    side_label = {
        "LEFT": "左",
        "RIGHT": "右",
        "BILATERAL": "双侧",
    }.get(item.side)
    return f"{label}·{side_label}" if side_label else label


def _marker_name(item):
    label = _marker_display_label(item)
    return "".join(char if char not in '\\/:*?\"<>|' else "_" for char in label)


def _create_or_update_marker(scene, item, world_point=None, world_normal=None):
    marker = bpy.data.objects.get(item.marker_name) if item.marker_name else None
    if marker is None:
        marker = bpy.data.objects.new(_marker_name(item), None)
        marker["smpl_acupoint_id"] = item.annotation_id
        marker["smpl_acupoint_target"] = item.target_name
        _ensure_marker_collection(scene).objects.link(marker)
        item.marker_name = marker.name

    settings = scene.smpl_acupoint_settings
    display_version = int(settings.get("_smpl_acupoint_display_version", 0))
    if display_version < 2:
        settings["_smpl_acupoint_display_version"] = 2
        if math.isclose(settings.marker_size, 0.015, rel_tol=0.0, abs_tol=1e-9):
            settings.marker_size = 0.005
    marker.empty_display_type = "PLAIN_AXES"
    marker.empty_display_size = settings.marker_size
    marker.show_name = True
    marker.show_in_front = True
    marker.color = settings.marker_color
    marker.name = _marker_name(item)
    marker["smpl_acupoint_label"] = _marker_display_label(item)
    item.marker_name = marker.name

    if world_point is None or world_normal is None:
        target = bpy.data.objects.get(item.target_name)
        world_point, world_normal, _ = _surface_sample(
            target, item.face_index, item.barycentric
        )
    marker.location = world_point + world_normal * settings.surface_offset
    if world_normal.length_squared > 0:
        marker.rotation_mode = "QUATERNION"
        marker.rotation_quaternion = world_normal.to_track_quat("Z", "Y")
    return marker


def add_annotation_from_surface(
    scene,
    target,
    face_index,
    barycentric,
    code="",
    name_zh="",
    meridian="",
    side="MIDLINE",
    notes="",
    confidence=1.0,
    body_region="TORSO",
):
    global _suspend_autosave
    item = scene.smpl_acupoint_annotations.add()
    previous_suspend = _suspend_autosave
    _suspend_autosave = True
    try:
        item.annotation_id = str(uuid.uuid4())
        item.code = code.strip().upper()
        item.name_zh = name_zh.strip()
        item.meridian = meridian.strip()
        item.side = side
        item.notes = notes.strip()
        item.confidence = confidence
        item.body_region = body_region
        item.target_name = target.name
        item.face_index = int(face_index)
        item.barycentric = tuple(float(value) for value in barycentric)
        item.pose_id = scene.smpl_acupoint_settings.current_pose_id
        item.created_at = _utc_now()
        item.updated_at = item.created_at
    finally:
        _suspend_autosave = previous_suspend
    point, normal, _ = _surface_sample(target, item.face_index, item.barycentric)
    _create_or_update_marker(scene, item, point, normal)
    scene.smpl_acupoint_active_index = len(scene.smpl_acupoint_annotations) - 1
    _autosave_scene(scene)
    return item


def refresh_scene_markers(scene, depsgraph=None):
    global _refreshing_markers
    if _refreshing_markers or not hasattr(scene, "smpl_acupoint_annotations"):
        return
    _refreshing_markers = True
    try:
        depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
        for item in scene.smpl_acupoint_annotations:
            target = bpy.data.objects.get(item.target_name)
            if target is None or target.type != "MESH":
                continue
            try:
                point, normal, _ = _surface_sample(
                    target, item.face_index, item.barycentric, depsgraph
                )
                _create_or_update_marker(scene, item, point, normal)
            except (IndexError, ValueError, ReferenceError):
                continue
    finally:
        _refreshing_markers = False


def clear_annotations(scene):
    for item in list(scene.smpl_acupoint_annotations):
        marker = bpy.data.objects.get(item.marker_name)
        if marker is not None:
            bpy.data.objects.remove(marker, do_unlink=True)
    scene.smpl_acupoint_annotations.clear()
    scene.smpl_acupoint_active_index = 0


def _shape_payload(target):
    if _model_family(target) == "SKEL":
        scene = bpy.context.scene
        values = list(scene.get("skel_betas", [0.0] * 10))
        return {f"beta_{index}": float(value) for index, value in enumerate(values)}
    shape_keys = getattr(target.data, "shape_keys", None)
    if shape_keys is None:
        return {}
    return {
        key.name: float(key.value)
        for key in shape_keys.key_blocks
        if key.name.startswith("Shape") or key.name.startswith("Exp")
    }


def _pose_payload(target):
    if _model_family(target) == "SKEL":
        scene = bpy.context.scene
        values = dict(scene.get("skel_pose_degrees", {}))
        return {
            "representation": "SKEL biomechanical degrees",
            "parameters": {str(name): float(value) for name, value in sorted(values.items())},
        }
    armature = target.parent if target.parent and target.parent.type == "ARMATURE" else None
    if armature is None:
        return {"armature": None, "bones": {}}
    bones = {}
    for bone in armature.pose.bones:
        quaternion = bone.matrix_basis.to_quaternion()
        bones[bone.name] = {
            "rotation_quaternion_wxyz": [float(value) for value in quaternion],
            "location": [float(value) for value in bone.location],
        }
    return {"armature": armature.name, "bones": bones}


def _shape_signature(target):
    digest = hashlib.sha256()
    for name, value in sorted(_shape_payload(target).items()):
        digest.update(f"{name}={value:.9f};".encode("utf-8"))
    return digest.hexdigest()


def _pose_signature(target):
    digest = hashlib.sha256()
    if _model_family(target) == "SKEL":
        payload = _pose_payload(target).get("parameters", {})
        for name, value in sorted(payload.items()):
            digest.update(f"{name}={float(value):.9f};".encode("utf-8"))
        return digest.hexdigest()
    armature = target.parent if target.parent and target.parent.type == "ARMATURE" else None
    if armature is None:
        digest.update(b"no-armature")
        return digest.hexdigest()
    for bone in sorted(armature.pose.bones, key=lambda value: value.name):
        digest.update((bone.name + ":").encode("utf-8"))
        for row in bone.matrix_basis:
            for value in row:
                digest.update(f"{float(value):.9f},".encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()


def build_export_payload(scene):
    settings = scene.smpl_acupoint_settings
    target = settings.target_mesh
    annotations = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for item in scene.smpl_acupoint_annotations:
        item_target = bpy.data.objects.get(item.target_name)
        if item_target is None:
            raise ValueError(f"标注 {item.code or item.annotation_id} 的目标人体不存在")
        point, normal, vertex_ids = _surface_sample(
            item_target, item.face_index, item.barycentric, depsgraph
        )
        local_point = item_target.matrix_world.inverted() @ point
        canonical_point = _canonical_local_sample(
            item_target, item.face_index, item.barycentric
        )
        annotations.append(
            {
                "id": item.annotation_id,
                "point_id": _point_id(item.code, item.side),
                "code": item.code,
                "name_zh": item.name_zh,
                "meridian": item.meridian,
                "side": item.side,
                "notes": item.notes,
                "confidence": float(item.confidence),
                "body_region": item.body_region,
                "target_mesh": item.target_name,
                "face_index": int(item.face_index),
                "vertex_indices": [int(value) for value in vertex_ids],
                "barycentric": [float(value) for value in item.barycentric],
                "canonical_local_position_m": [float(value) for value in canonical_point],
                "local_position_m": [float(value) for value in local_point],
                "world_position_m": [float(value) for value in point],
                "world_normal": [float(value) for value in normal],
                "pose_id": item.pose_id or settings.current_pose_id,
                "review_status": item.review_status,
                "created_at": item.created_at,
                "updated_at": item.updated_at or item.created_at,
            }
        )

    model = None
    if target is not None:
        model = _model_descriptor(target)
        model["shape_parameters"] = _shape_payload(target)
        model["pose"] = _pose_payload(target)
    target_family = _model_family(target)
    native_skel = target_family == "SKEL"
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "created_at": _utc_now(),
        "atlas": {
            "atlas_version": settings.atlas_version or ATLAS_VERSION,
            "protocol_version": settings.protocol_version or PROTOCOL_VERSION,
        },
        "session": _session_metadata(scene),
        "coordinate_system": "Blender right-handed, Z-up",
        "linear_unit": "meter",
        "medical_status": "doctor_annotation; not an automatic clinical recommendation",
        "structural_context": {
            "native_skel_model": native_skel,
            "native_skeleton_visible_at_export": bool(
                scene.get("skel_native_skeleton_visible", False)
            ) if native_skel else False,
            "native_skeleton_used": bool(settings.skel_reference_used) if native_skel else False,
            "cross_model_registration_used": False if native_skel else bool(
                scene.get("skel_registration_method", "")
            ),
            "notice": (
                "SKEL skin and skeleton are generated by the same parametric model; "
                "the skeleton is a structural prior, not patient CT ground truth"
                if native_skel else
                "No SKEL overlay is used by the independent SMPL-X workflow"
            ),
        },
        "reference_layers": {
            "skel_reference_used": bool(settings.skel_reference_used) if not native_skel else False,
            "skel_reference_visible_at_export": bool(scene.get("skel_reference_visible", False)) if not native_skel else False,
            "skel_registration_id": settings.skel_registration_id if not native_skel else "",
            "skel_registration_method": str(scene.get("skel_registration_method", "")) if not native_skel else "",
            "skel_surface_rmse_m": float(scene.get("skel_surface_rmse_m", -1.0)) if not native_skel else -1.0,
            "skel_surface_distance_p95_m": float(
                scene.get("skel_surface_distance_p95_m", -1.0)
            ) if not native_skel else -1.0,
            "skel_model_pack_id": str(scene.get("skel_model_pack_id", "")) if not native_skel else "",
            "notice": "Legacy cross-model reference fields; unused when SKEL is the annotation model",
        },
        "model": model,
        "annotations": annotations,
    }


def _atomic_write_payload(filepath, payload):
    directory = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(directory, exist_ok=True)
    temporary_path = filepath + ".tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, filepath)
    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass


def export_annotations(scene, filepath, strict=None):
    if strict is None:
        strict = _is_doctor_mode(scene)
    if strict:
        _validate_scene(scene, require_annotations=True)
    payload = build_export_payload(scene)
    _atomic_write_payload(filepath, payload)
    return len(payload["annotations"])


def _autosave_scene(scene):
    """Deliberately do nothing: only an explicit Save commits annotation data."""
    return


def import_annotations(scene, target, filepath):
    global _suspend_autosave
    # utf-8-sig reads ordinary UTF-8 unchanged and strips the optional BOM
    # written by some Windows/PowerShell tools.
    with open(filepath, "r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if payload.get("schema") == "doctor-annotation-session-v3" and not payload.get("schema_version"):
        import_root = os.environ.get("SMPL_ACUPOINT_ATLAS_IMPORT_ROOT", "").strip()
        export_directory = str(payload.get("export_directory", "")).strip()
        if not export_directory and import_root and payload.get("session_id"):
            export_directory = os.path.join(import_root, str(payload["session_id"]))
        if not import_root or not export_directory:
            raise ValueError("这是“本次标注信息.json”，请先保存 Atlas，再选择正式标注 JSON")
        import_root = os.path.realpath(import_root)
        export_directory = os.path.realpath(export_directory)
        try:
            inside_import_root = os.path.commonpath((import_root, export_directory)) == import_root
        except ValueError:
            inside_import_root = False
        if not inside_import_root or not os.path.isdir(export_directory):
            raise ValueError("会话信息指向的导出目录无效，请到“导出结果”中选择穴位 JSON")
        candidates = [
            os.path.join(export_directory, name)
            for name in os.listdir(export_directory)
            if name.endswith("_正式标注_最新.json")
            and os.path.isfile(os.path.join(export_directory, name))
        ]
        if not candidates:
            raise ValueError("该会话还没有穴位导出；请先在 Atlas 模式点击“保存本次标注”")
        filepath = max(candidates, key=os.path.getmtime)
        with open(filepath, "r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    schema_version = payload.get("schema_version")
    if schema_version not in {SCHEMA_VERSION, *LEGACY_SCHEMA_VERSIONS}:
        raise ValueError("不支持的标注文件版本")

    source_session = payload.get("session") or {}
    settings = scene.smpl_acupoint_settings
    for property_name in (
        "session_id", "doctor_id", "task_id", "template_id", "template_gender",
        "template_file_sha256", "atlas_version", "protocol_version",
    ):
        value = source_session.get(property_name)
        if value and not getattr(settings, property_name, ""):
            setattr(settings, property_name, str(value))

    source_model = payload.get("model") or {}
    source_family = str(source_model.get("family", "")).strip().upper()
    target_family = _model_family(target)
    if source_family and source_family != target_family:
        raise ValueError(
            f"模型不兼容：标注文件属于 {source_family}，当前人体属于 {target_family}"
        )
    source_gender = str(source_model.get("gender", "")).strip().lower()
    target_gender = str(settings.template_gender or target.get("skel_gender", "")).strip().lower()
    if source_gender and target_gender and source_gender != target_gender:
        raise ValueError(
            f"性别不兼容：标注文件为 {source_gender}，当前模板为 {target_gender}；请使用同一性别的 Atlas"
        )
    source_vertex_count = source_model.get("vertex_count")
    if source_vertex_count is not None and int(source_vertex_count) != len(target.data.vertices):
        raise ValueError(
            f"拓扑不兼容：标注文件为 {source_vertex_count} 顶点，当前模型为 "
            f"{len(target.data.vertices)} 顶点；不能在 SMPL 与 SMPL-X 之间直接导入"
        )
    source_polygon_count = source_model.get("polygon_count")
    if source_polygon_count is not None and int(source_polygon_count) != len(target.data.polygons):
        raise ValueError("拓扑不兼容：模型三角面数量不同")
    source_signature = source_model.get("topology_signature_sha256")
    if source_signature and str(source_signature) != _topology_signature(target):
        raise ValueError("拓扑不兼容：模型面顺序或顶点索引不同")

    existing_ids = {item.annotation_id for item in scene.smpl_acupoint_annotations}
    existing_point_ids = {
        _point_id(item.code, item.side) for item in scene.smpl_acupoint_annotations
    }
    imported = 0
    skipped = 0
    prepared = []
    prepared_ids = set()
    prepared_point_ids = set()
    for data in payload.get("annotations", []):
        annotation_id = str(data.get("id") or uuid.uuid4())
        code = str(data.get("code", "")).strip().upper()
        name_zh = str(data.get("name_zh", "")).strip()
        side = str(data.get("side", "MIDLINE"))
        if not code or not name_zh:
            raise ValueError("标注文件中存在缺少编码或中文名称的穴位")
        if side not in {"MIDLINE", "LEFT", "RIGHT", "BILATERAL", "UNSPECIFIED"}:
            side = "UNSPECIFIED"
        point_id = _point_id(code, side)
        if (
            annotation_id in existing_ids
            or annotation_id in prepared_ids
            or point_id in existing_point_ids
            or point_id in prepared_point_ids
        ):
            skipped += 1
            continue
        face_index = int(data["face_index"])
        barycentric = tuple(float(value) for value in data["barycentric"])
        if len(barycentric) != 3 or not all(math.isfinite(value) for value in barycentric):
            raise ValueError(f"穴位 {point_id} 的重心坐标无效")
        if abs(sum(barycentric) - 1.0) > 1e-4:
            raise ValueError(f"穴位 {point_id} 的重心坐标之和不等于 1")
        if any(value < -1e-7 or value > 1.0 + 1e-7 for value in barycentric):
            raise ValueError(f"穴位 {point_id} 的重心坐标落在三角面之外")
        _, _, expected_vertex_ids = _surface_sample(target, face_index, barycentric)
        source_vertex_ids = data.get("vertex_indices")
        if source_vertex_ids is not None:
            source_vertex_ids = tuple(int(value) for value in source_vertex_ids)
            if source_vertex_ids != tuple(expected_vertex_ids):
                raise ValueError(f"穴位 {point_id} 的三角面顶点索引与当前模板不一致")
        prepared.append((data, annotation_id, code, name_zh, side, face_index, barycentric))
        prepared_ids.add(annotation_id)
        prepared_point_ids.add(point_id)

    previous_suspend = _suspend_autosave
    _suspend_autosave = True
    try:
        for data, annotation_id, code, name_zh, side, face_index, barycentric in prepared:
            item = scene.smpl_acupoint_annotations.add()
            item.annotation_id = annotation_id
            item.code = code
            item.name_zh = name_zh
            item.meridian = str(data.get("meridian", ""))
            item.side = side
            item.notes = str(data.get("notes", ""))
            item.confidence = float(data.get("confidence", 1.0))
            region = str(data.get("body_region", "TORSO"))
            item.body_region = region if region in {key for key, _, _ in BODY_REGION_ITEMS} else "OTHER"
            item.target_name = target.name
            item.face_index = face_index
            item.barycentric = barycentric
            item.pose_id = str(data.get("pose_id", "CANONICAL"))
            item.review_status = str(data.get("review_status", "DRAFT"))
            item.created_at = str(data.get("created_at", _utc_now()))
            item.updated_at = str(data.get("updated_at", item.created_at))
            _create_or_update_marker(scene, item)
            existing_ids.add(annotation_id)
            existing_point_ids.add(_point_id(code, side))
            imported += 1
    finally:
        _suspend_autosave = previous_suspend
    if imported:
        scene.smpl_acupoint_active_index = len(scene.smpl_acupoint_annotations) - 1
        _autosave_scene(scene)
    return imported, skipped


@persistent
def _depsgraph_update_handler(scene, depsgraph):
    refresh_scene_markers(scene, depsgraph)


@persistent
def _load_post_handler(_unused):
    scenes = getattr(bpy.data, "scenes", None)
    if scenes is not None:
        for scene in scenes:
            _initialize_session(scene)
            refresh_scene_markers(scene)
    if not bpy.app.background and not bpy.app.timers.is_registered(_configure_doctor_workspaces):
        bpy.app.timers.register(_configure_doctor_workspaces, first_interval=0.25)


def _display_settings_update(self, context):
    if context and context.scene:
        refresh_scene_markers(context.scene)


def _annotation_label_update(self, context):
    """Rename an existing marker immediately when a doctor edits its label."""
    if _refreshing_markers or _suspend_autosave:
        return
    marker = bpy.data.objects.get(self.marker_name) if self.marker_name else None
    if marker is not None:
        marker.name = _marker_name(self)
        marker["smpl_acupoint_label"] = _marker_display_label(self)
        self.marker_name = marker.name
    self.updated_at = _utc_now()
    if context and context.scene:
        _autosave_scene(context.scene)
    if context and context.area:
        context.area.tag_redraw()


def _apply_pose_sliders(self, context):
    global _updating_pose
    if _updating_pose or context is None:
        return
    target = _resolve_target(context=context)
    # SKEL is regenerated by its external biomechanical model. Its skin has no
    # Blender armature parent, so the direct SMPL/SMPL-X bone sliders cannot be
    # applied safely or interactively.
    if _model_family(target) == "SKEL":
        return
    armature = target.parent if target and target.parent and target.parent.type == "ARMATURE" else None
    if armature is None:
        return

    _updating_pose = True
    try:
        mapping = {
            ("Spine1", "spine1"): (self.spine1_x, self.spine1_y, self.spine1_z),
            ("L_Shoulder", "left_shoulder"): (
                self.left_shoulder_x,
                self.left_shoulder_y,
                self.left_shoulder_z,
            ),
            ("R_Shoulder", "right_shoulder"): (
                self.right_shoulder_x,
                self.right_shoulder_y,
                self.right_shoulder_z,
            ),
            ("L_Elbow", "left_elbow"): (self.left_elbow_x, 0.0, 0.0),
            ("R_Elbow", "right_elbow"): (self.right_elbow_x, 0.0, 0.0),
            ("jaw",): (self.jaw_x, 0.0, self.jaw_z),
            ("left_wrist",): (self.left_wrist_x, self.left_wrist_y, self.left_wrist_z),
            ("right_wrist",): (self.right_wrist_x, self.right_wrist_y, self.right_wrist_z),
        }
        for bone_names, degrees_xyz in mapping.items():
            bone = next((armature.pose.bones.get(name) for name in bone_names if armature.pose.bones.get(name)), None)
            if bone is None:
                continue
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = tuple(math.radians(value) for value in degrees_xyz)
        context.view_layer.update()
        refresh_scene_markers(context.scene)
    finally:
        _updating_pose = False


def _apply_hand_pose(self, context):
    if context is None:
        return
    target = _resolve_target(context=context)
    if _model_family(target) != "SMPL-X" or not hasattr(bpy.ops.object, "smplx_set_handpose"):
        return
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    context.view_layer.objects.active = target
    if hasattr(context.window_manager, "smplx_tool"):
        context.window_manager.smplx_tool.smplx_handpose = self.hand_pose
    bpy.ops.object.smplx_set_handpose("EXEC_DEFAULT")
    refresh_scene_markers(context.scene)


class SMPLAcupointAnnotation(PropertyGroup):
    annotation_id: StringProperty(name="ID")
    code: StringProperty(name="标准编码", update=_annotation_label_update)
    name_zh: StringProperty(name="中文名称", update=_annotation_label_update)
    meridian: StringProperty(name="经脉/区域", update=_annotation_label_update)
    side: EnumProperty(
        name="侧别",
        items=(
            ("MIDLINE", "中线", ""),
            ("LEFT", "左侧", ""),
            ("RIGHT", "右侧", ""),
            ("BILATERAL", "双侧", ""),
            ("UNSPECIFIED", "未指定", ""),
        ),
        default="MIDLINE",
        update=_annotation_label_update,
    )
    notes: StringProperty(name="医生备注", update=_annotation_label_update)
    confidence: FloatProperty(
        name="置信度", min=0.0, max=1.0, default=1.0,
        update=_annotation_label_update,
    )
    body_region: EnumProperty(
        name="身体分区", items=BODY_REGION_ITEMS, default="TORSO",
        update=_annotation_label_update,
    )
    target_name: StringProperty(name="目标网格")
    face_index: IntProperty(name="面编号", default=-1)
    barycentric: FloatVectorProperty(name="重心坐标", size=3, default=(1.0, 0.0, 0.0))
    marker_name: StringProperty(name="标记对象")
    pose_id: StringProperty(name="标注姿态", default="CANONICAL")
    review_status: EnumProperty(
        name="复核状态",
        items=(("DRAFT", "待复核", ""), ("REVIEWED", "已复核", "")),
        default="DRAFT",
        update=_annotation_label_update,
    )
    created_at: StringProperty(name="创建时间")
    updated_at: StringProperty(name="更新时间")


class SMPLAcupointSettings(PropertyGroup):
    workflow_mode: EnumProperty(
        name="工作模式",
        items=(
            ("DOCTOR_ATLAS", "医生 Atlas", "受约束的正式医生标注"),
            ("RESEARCH", "内部研究", "开放模型与数据工具"),
        ),
        default="RESEARCH",
    )
    simple_ui: BoolProperty(name="简洁界面", default=False)
    research_height: FloatProperty(name="身高（米）", min=1.4, max=2.2, default=1.70)
    research_weight: FloatProperty(name="体重（千克）", min=40.0, max=110.0, default=60.0)
    session_id: StringProperty(name="会话编号")
    doctor_id: StringProperty(name="医生编号")
    task_id: StringProperty(name="任务编号")
    template_id: StringProperty(name="模板编号")
    template_gender: StringProperty(name="模板性别")
    template_file_sha256: StringProperty(name="模板文件 SHA-256")
    resumed_from_session_id: StringProperty(name="续接自会话")
    atlas_version: StringProperty(name="Atlas 版本", default=ATLAS_VERSION)
    protocol_version: StringProperty(name="标注协议", default=PROTOCOL_VERSION)
    current_pose_id: StringProperty(name="当前标准姿态", default="CANONICAL")
    last_autosave_at: StringProperty(name="最近自动保存")
    last_save_error: StringProperty(name="最近保存错误")
    skel_reference_used: BoolProperty(name="使用过 SKEL 参考", default=False)
    skel_registration_id: StringProperty(name="SKEL 配准编号")
    show_advanced: BoolProperty(name="高级信息", default=False)
    target_mesh: PointerProperty(name="SMPL/SMPL-X/SKEL 人体网格", type=bpy.types.Object, poll=_mesh_poll)
    draft_code: StringProperty(name="标准编码", description="例如由医生填写 BL23；插件不自动给出临床位置")
    draft_name_zh: StringProperty(name="中文名称")
    draft_meridian: StringProperty(name="经脉/区域")
    draft_side: EnumProperty(
        name="侧别",
        items=(
            ("MIDLINE", "中线", ""),
            ("LEFT", "左侧", ""),
            ("RIGHT", "右侧", ""),
        ),
        default="MIDLINE",
    )
    draft_notes: StringProperty(name="医生备注")
    draft_body_region: EnumProperty(name="身体分区", items=BODY_REGION_ITEMS, default="TORSO")
    marker_size: FloatProperty(
        name="标记大小", subtype="DISTANCE", min=0.001, max=0.1, default=0.005,
        update=_display_settings_update,
    )
    surface_offset: FloatProperty(
        name="离表面距离", subtype="DISTANCE", min=0.0, max=0.05, default=0.003,
        update=_display_settings_update,
    )
    marker_color: FloatVectorProperty(
        name="标记颜色", subtype="COLOR", size=4, min=0.0, max=1.0,
        default=(1.0, 0.05, 0.02, 1.0), update=_display_settings_update,
    )

    spine1_x: FloatProperty(name="脊柱 X", min=-60, max=60, default=0, update=_apply_pose_sliders)
    spine1_y: FloatProperty(name="脊柱 Y", min=-60, max=60, default=0, update=_apply_pose_sliders)
    spine1_z: FloatProperty(name="脊柱 Z", min=-60, max=60, default=0, update=_apply_pose_sliders)
    left_shoulder_x: FloatProperty(name="左肩 X", min=-180, max=180, default=0, update=_apply_pose_sliders)
    left_shoulder_y: FloatProperty(name="左肩 Y", min=-180, max=180, default=0, update=_apply_pose_sliders)
    left_shoulder_z: FloatProperty(name="左肩 Z", min=-180, max=180, default=0, update=_apply_pose_sliders)
    right_shoulder_x: FloatProperty(name="右肩 X", min=-180, max=180, default=0, update=_apply_pose_sliders)
    right_shoulder_y: FloatProperty(name="右肩 Y", min=-180, max=180, default=0, update=_apply_pose_sliders)
    right_shoulder_z: FloatProperty(name="右肩 Z", min=-180, max=180, default=0, update=_apply_pose_sliders)
    left_elbow_x: FloatProperty(name="左肘 X", min=-160, max=160, default=0, update=_apply_pose_sliders)
    right_elbow_x: FloatProperty(name="右肘 X", min=-160, max=160, default=0, update=_apply_pose_sliders)
    jaw_x: FloatProperty(name="下颌开合 X", min=-35, max=35, default=0, update=_apply_pose_sliders)
    jaw_z: FloatProperty(name="下颌侧移 Z", min=-20, max=20, default=0, update=_apply_pose_sliders)
    left_wrist_x: FloatProperty(name="左腕 X", min=-90, max=90, default=0, update=_apply_pose_sliders)
    left_wrist_y: FloatProperty(name="左腕 Y", min=-90, max=90, default=0, update=_apply_pose_sliders)
    left_wrist_z: FloatProperty(name="左腕 Z", min=-90, max=90, default=0, update=_apply_pose_sliders)
    right_wrist_x: FloatProperty(name="右腕 X", min=-90, max=90, default=0, update=_apply_pose_sliders)
    right_wrist_y: FloatProperty(name="右腕 Y", min=-90, max=90, default=0, update=_apply_pose_sliders)
    right_wrist_z: FloatProperty(name="右腕 Z", min=-90, max=90, default=0, update=_apply_pose_sliders)
    hand_pose: EnumProperty(
        name="双手预设",
        items=(("relaxed", "自然放松", "自然弯曲的手指"), ("flat", "平展", "手指伸直")),
        default="relaxed",
        update=_apply_hand_pose,
    )
    show_pose_controls: BoolProperty(name="显示姿态滑动条", default=False)


class SMPL_ACU_UL_annotations(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            label = " · ".join(value for value in (item.code, item.name_zh) if value) or f"标注 {index + 1}"
            layout.label(text=label, icon="EMPTY_AXIS")
            layout.label(text=dict((key, label) for key, label, _ in BODY_REGION_ITEMS).get(item.body_region, ""))
            layout.label(text={"LEFT": "左", "RIGHT": "右", "MIDLINE": "中", "BILATERAL": "双"}.get(item.side, ""))
        else:
            layout.alignment = "CENTER"
            layout.label(text="", icon="EMPTY_AXIS")


class SMPL_ACU_OT_use_active_mesh(Operator):
    bl_idname = "smpl_acupoint.use_active_mesh"
    bl_label = "使用当前人体"
    bl_description = "把当前选中的网格设为穴位标注目标"

    def execute(self, context):
        target = context.active_object
        if target and target.type == "ARMATURE":
            target = next((child for child in target.children if child.type == "MESH"), None)
        if target is None or target.type != "MESH":
            self.report({"ERROR"}, "请先选择 SMPL 人体网格或其骨架")
            return {"CANCELLED"}
        context.scene.smpl_acupoint_settings.target_mesh = target
        self.report({"INFO"}, f"标注目标：{target.name}")
        return {"FINISHED"}


class SMPL_ACU_OT_add_surface_point(Operator):
    bl_idname = "smpl_acupoint.add_surface_point"
    bl_label = "在人体表面点选"
    bl_description = "进入点选模式；在人体表面单击创建一个标注点，Esc 或右键取消"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        target = _resolve_target(context=context)
        if target is None:
            self.report({"ERROR"}, "请先设置 SMPL 人体网格")
            return {"CANCELLED"}
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "请从 3D 视图右侧面板启动点选")
            return {"CANCELLED"}
        if _is_doctor_mode(context.scene):
            try:
                _validate_scene(context.scene, require_annotations=False)
                code, name_zh = _validate_draft(context.scene)
            except ValueError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}
            context.scene.smpl_acupoint_settings.draft_code = code
            context.scene.smpl_acupoint_settings.draft_name_zh = name_zh
        self.target_name = target.name
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set("CROSSHAIR")
        context.workspace.status_text_set("穴位点选：左键点人体表面；Esc/右键取消")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"}:
            context.window.cursor_modal_restore()
            context.workspace.status_text_set(None)
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            target = bpy.data.objects.get(self.target_name)
            if target is None:
                context.window.cursor_modal_restore()
                context.workspace.status_text_set(None)
                return {"CANCELLED"}
            try:
                hit = _raycast_target(context, target, event)
            except ValueError as error:
                self.report({"ERROR"}, str(error))
                return {"RUNNING_MODAL"}
            if hit is None:
                self.report({"WARNING"}, "没有命中人体；请在人体表面再次单击")
                return {"RUNNING_MODAL"}
            face_index, barycentric, world_point, world_normal = hit
            settings = context.scene.smpl_acupoint_settings
            item = add_annotation_from_surface(
                context.scene,
                target,
                face_index,
                barycentric,
                code=settings.draft_code,
                name_zh=settings.draft_name_zh,
                meridian=settings.draft_meridian,
                side=settings.draft_side,
                notes=settings.draft_notes,
                body_region=settings.draft_body_region,
            )
            marker = bpy.data.objects.get(item.marker_name)
            if marker:
                marker.location = world_point + world_normal * settings.surface_offset
            context.window.cursor_modal_restore()
            context.workspace.status_text_set(None)
            self.report({"INFO"}, f"已创建：{item.code or item.name_zh or '未命名标注'}")
            return {"FINISHED"}
        return {"PASS_THROUGH"}


class SMPL_ACU_OT_select_annotation(Operator):
    bl_idname = "smpl_acupoint.select_annotation"
    bl_label = "定位选中标注"

    def execute(self, context):
        scene = context.scene
        index = scene.smpl_acupoint_active_index
        if index < 0 or index >= len(scene.smpl_acupoint_annotations):
            return {"CANCELLED"}
        marker = bpy.data.objects.get(scene.smpl_acupoint_annotations[index].marker_name)
        if marker is None:
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        marker.select_set(True)
        context.view_layer.objects.active = marker
        try:
            bpy.ops.view3d.view_selected(use_all_regions=False)
        except RuntimeError:
            pass
        return {"FINISHED"}


class SMPL_ACU_OT_remove_annotation(Operator):
    bl_idname = "smpl_acupoint.remove_annotation"
    bl_label = "删除选中标注"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        index = scene.smpl_acupoint_active_index
        if index < 0 or index >= len(scene.smpl_acupoint_annotations):
            return {"CANCELLED"}
        item = scene.smpl_acupoint_annotations[index]
        marker = bpy.data.objects.get(item.marker_name)
        if marker is not None:
            bpy.data.objects.remove(marker, do_unlink=True)
        scene.smpl_acupoint_annotations.remove(index)
        scene.smpl_acupoint_active_index = max(0, min(index, len(scene.smpl_acupoint_annotations) - 1))
        _autosave_scene(scene)
        return {"FINISHED"}


class SMPL_ACU_OT_set_annotation_side(Operator):
    bl_idname = "smpl_acupoint.set_annotation_side"
    bl_label = "设置标注侧别"
    side: EnumProperty(
        items=(("MIDLINE", "中线", ""), ("LEFT", "左侧", ""), ("RIGHT", "右侧", "")),
        default="MIDLINE",
    )

    def execute(self, context):
        scene = context.scene
        index = scene.smpl_acupoint_active_index
        if index < 0 or index >= len(scene.smpl_acupoint_annotations):
            return {"CANCELLED"}
        scene.smpl_acupoint_annotations[index].side = self.side
        return {"FINISHED"}


class SMPL_ACU_OT_refresh_markers(Operator):
    bl_idname = "smpl_acupoint.refresh_markers"
    bl_label = "刷新表面位置"

    def execute(self, context):
        refresh_scene_markers(context.scene)
        self.report({"INFO"}, "标注点已按当前体型和姿态刷新")
        return {"FINISHED"}


class SMPL_ACU_OT_back_view(Operator):
    bl_idname = "smpl_acupoint.back_view"
    bl_label = "标准视图"
    view_type: EnumProperty(
        items=(("FRONT", "前", ""), ("BACK", "后", ""), ("LEFT", "左", ""), ("RIGHT", "右", "")),
        default="BACK",
    )

    def execute(self, context):
        target = _resolve_target(context=context)
        if target:
            bpy.ops.object.select_all(action="DESELECT")
            target.select_set(True)
            context.view_layer.objects.active = target
        try:
            bpy.ops.view3d.view_axis(type=self.view_type, align_active=False)
            if target:
                bpy.ops.view3d.view_selected(use_all_regions=False)
        except RuntimeError:
            self.report({"WARNING"}, "请在 3D 视图中使用该按钮")
            return {"CANCELLED"}
        return {"FINISHED"}


class SMPL_ACU_OT_apply_pose_correctives(Operator):
    bl_idname = "smpl_acupoint.apply_pose_correctives"
    bl_label = "应用 SMPL 姿态修正"

    def execute(self, context):
        target = _resolve_target(context=context)
        if _model_family(target) == "SKEL":
            if not hasattr(context.scene, "skel_controls"):
                self.report({"ERROR"}, "请使用项目 SKEL 启动器打开 Blender 4.5，再通过 SKEL 生物力学控制更新")
                return {"CANCELLED"}
            try:
                result = bpy.ops.skel.update_skin("EXEC_DEFAULT")
            except (AttributeError, RuntimeError) as error:
                self.report({"ERROR"}, f"SKEL 更新失败：{error}")
                return {"CANCELLED"}
            return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}
        armature = target.parent if target and target.parent and target.parent.type == "ARMATURE" else None
        if armature is None:
            self.report({"ERROR"}, "目标人体没有 SMPL 骨架")
            return {"CANCELLED"}
        operator_name = None
        if hasattr(bpy.ops.object, "smplx_set_poseshapes"):
            operator_name = "smplx_set_poseshapes"
        elif hasattr(bpy.ops.object, "smpl_set_poseshapes"):
            operator_name = "smpl_set_poseshapes"
        if operator_name is None:
            self.report({"ERROR"}, "未检测到官方 SMPL/SMPL-X 插件的姿态修正操作")
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        context.view_layer.objects.active = armature
        result = getattr(bpy.ops.object, operator_name)("EXEC_DEFAULT")
        refresh_scene_markers(context.scene)
        if "FINISHED" not in result:
            return {"CANCELLED"}
        return {"FINISHED"}


class SMPL_ACU_OT_reset_pose_controls(Operator):
    bl_idname = "smpl_acupoint.reset_pose_controls"
    bl_label = "姿态归零"

    def execute(self, context):
        global _updating_pose
        settings = context.scene.smpl_acupoint_settings
        target = _resolve_target(context=context)
        model_family = _model_family(target)
        _updating_pose = True
        try:
            for name in (
                "spine1_x", "spine1_y", "spine1_z",
                "left_shoulder_x", "left_shoulder_y", "left_shoulder_z",
                "right_shoulder_x", "right_shoulder_y", "right_shoulder_z",
                "left_elbow_x", "right_elbow_x",
                "jaw_x", "jaw_z",
                "left_wrist_x", "left_wrist_y", "left_wrist_z",
                "right_wrist_x", "right_wrist_y", "right_wrist_z",
            ):
                setattr(settings, name, 0.0)
        finally:
            _updating_pose = False
        _apply_pose_sliders(settings, context)

        if model_family == "SKEL":
            if not hasattr(context.scene, "skel_controls"):
                self.report({"ERROR"}, "当前是 SKEL，但未加载 SKEL 生物力学控制；请用项目 .cmd 启动器重新打开")
                return {"CANCELLED"}
            try:
                result = bpy.ops.skel.reset_pose("EXEC_DEFAULT")
            except (AttributeError, RuntimeError) as error:
                self.report({"ERROR"}, f"SKEL 姿态归零失败：{error}")
                return {"CANCELLED"}
            return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}

        reset_operator = None
        if model_family == "SMPL-X" and hasattr(bpy.ops.object, "smplx_reset_poseshapes"):
            reset_operator = "smplx_reset_poseshapes"
        elif model_family == "SMPL" and hasattr(bpy.ops.object, "smpl_reset_poseshapes"):
            reset_operator = "smpl_reset_poseshapes"
        if reset_operator:
            if target:
                bpy.ops.object.select_all(action="DESELECT")
                target.select_set(True)
                context.view_layer.objects.active = target
                try:
                    getattr(bpy.ops.object, reset_operator)("EXEC_DEFAULT")
                except (AttributeError, RuntimeError) as error:
                    self.report({"WARNING"}, f"骨骼已归零，但姿态修正重置失败：{error}")
        return {"FINISHED"}


def _activate_smplx_target(context):
    target = _resolve_target(context=context)
    if target is None or _model_family(target) != "SMPL-X":
        raise ValueError("未找到 SMPL-X 人体")
    target.hide_select = False
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    context.view_layer.objects.active = target
    return target


class SMPL_ACU_OT_apply_body_measurements(Operator):
    bl_idname = "smpl_acupoint.apply_body_measurements"
    bl_label = "应用身高和体重"
    bl_description = "使用 SMPL-X 官方回归器生成体型；仅限内部研究模式"

    @classmethod
    def poll(cls, context):
        return not _is_doctor_mode(context.scene)

    def execute(self, context):
        try:
            _activate_smplx_target(context)
            if not hasattr(context.window_manager, "smplx_tool"):
                raise ValueError("未加载模型包中的 SMPL-X 官方调整组件")
            settings = context.scene.smpl_acupoint_settings
            context.window_manager.smplx_tool.smplx_height = settings.research_height
            context.window_manager.smplx_tool.smplx_weight = settings.research_weight
            result = bpy.ops.object.smplx_measurements_to_shape("EXEC_DEFAULT")
            if "FINISHED" not in result:
                raise ValueError("SMPL-X 没有完成体型更新")
        except (AttributeError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "体型已更新；如使用骨架，请再点击“更新骨架对齐”")
        return {"FINISHED"}


class SMPL_ACU_OT_reset_body_shape(Operator):
    bl_idname = "smpl_acupoint.reset_body_shape"
    bl_label = "体型归零"
    bl_description = "清除 SMPL-X Shape 参数；仅限内部研究模式"

    @classmethod
    def poll(cls, context):
        return not _is_doctor_mode(context.scene)

    def execute(self, context):
        try:
            _activate_smplx_target(context)
            result = bpy.ops.object.smplx_reset_shape("EXEC_DEFAULT")
            if "FINISHED" not in result:
                raise ValueError("SMPL-X 没有完成体型归零")
        except (AttributeError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "体型已归零；如使用骨架，请再点击“更新骨架对齐”")
        return {"FINISHED"}


class SMPL_ACU_OT_export_json(Operator, ExportHelper):
    bl_idname = "smpl_acupoint.export_json"
    bl_label = "导出穴位 JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        if _is_doctor_mode(context.scene):
            export_root = _deployment_export_root()
            if not export_root:
                self.report({"ERROR"}, "缺少会话导出目录，请从医生启动器重新打开")
                return {"CANCELLED"}
            session_id = _safe_filename(context.scene.smpl_acupoint_settings.session_id, "当前会话")
            self.filepath = os.path.join(export_root, f"{session_id}_正式标注_最新.json")
            return self.execute(context)
        deployment_path = _deployment_export_path()
        if deployment_path:
            self.filepath = deployment_path
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            count = export_annotations(context.scene, self.filepath)
        except (OSError, ValueError, IndexError) as error:
            self.report({"ERROR"}, f"导出失败：{error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已导出 {count} 个穴位标注")
        return {"FINISHED"}


class SMPL_ACU_OT_save_doctor_session(Operator):
    bl_idname = "smpl_acupoint.save_doctor_session"
    bl_label = "保存本次标注"
    bl_description = "校验并保存 Blender 工作副本和正式 JSON；日常不需要另选文件"

    def execute(self, context):
        scene = context.scene
        try:
            _validate_scene(scene, require_annotations=True)
            if not bpy.data.filepath:
                raise ValueError("当前不是启动器创建的工作副本，请从医生启动器重新打开")
            bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, check_existing=False)
            export_root = _deployment_export_root()
            if not export_root:
                raise ValueError("缺少会话导出目录，请从医生启动器重新打开")
            session_id = _safe_filename(scene.smpl_acupoint_settings.session_id, "当前会话")
            filepath = os.path.join(export_root, f"{session_id}_正式标注_最新.json")
            count = export_annotations(scene, filepath, strict=True)
            scene.smpl_acupoint_settings.last_save_error = ""
        except (OSError, RuntimeError, ValueError, IndexError, ReferenceError) as error:
            scene.smpl_acupoint_settings.last_save_error = str(error)
            self.report({"ERROR"}, f"保存失败：{error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已保存 {count} 个穴位：{filepath}")
        return {"FINISHED"}


class SMPL_ACU_OT_import_json(Operator, ImportHelper):
    bl_idname = "smpl_acupoint.import_json"
    bl_label = "导入穴位 JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        import_root = os.environ.get("SMPL_ACUPOINT_ATLAS_IMPORT_ROOT", "").strip()
        if import_root and os.path.isdir(import_root):
            self.filepath = os.path.join(import_root, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        target = _resolve_target(context=context)
        if target is None:
            self.report({"ERROR"}, "请先设置导入目标人体")
            return {"CANCELLED"}
        try:
            imported, skipped = import_annotations(context.scene, target, self.filepath)
        except (OSError, KeyError, TypeError, ValueError, IndexError, json.JSONDecodeError) as error:
            self.report({"ERROR"}, f"导入失败：{error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"导入 {imported} 个，跳过重复 {skipped} 个")
        return {"FINISHED"}


def _draw_doctor_panel(layout, context):
    scene = context.scene
    settings = scene.smpl_acupoint_settings
    research_mode = not _is_doctor_mode(scene)
    target = settings.target_mesh
    model_family = _model_family(target)
    skel_mode = model_family == "SKEL"

    status_box = layout.box()
    status_box.label(
        text=(
            "SKEL 内部研究 · 可调模型" if research_mode and skel_mode
            else "SMPL-X 独立研究" if research_mode
            else "SKEL 躯干与四肢穴位 Atlas" if skel_mode
            else "SMPL-X 全身穴位 Atlas"
        ),
        icon="TOOL_SETTINGS" if research_mode else "USER",
    )
    status_box.label(text=f"医生：{settings.doctor_id or '未识别'}")
    status_box.label(text=f"任务：{settings.task_id or '未识别'}")
    gender_label = {"neutral": "中性", "female": "女性", "male": "男性"}.get(
        settings.template_gender.lower(), settings.template_gender or "未识别"
    )
    status_box.label(
        text=f"模板：{model_family or '未识别'} · {gender_label}",
        icon="UNLOCKED" if research_mode else "LOCKED",
    )
    if research_mode:
        status_box.label(text="调整后的点不属于规范 Atlas，请勿混入正式母版", icon="ERROR")
    if settings.resumed_from_session_id:
        status_box.label(text=f"续接：{settings.resumed_from_session_id}", icon="FILE_REFRESH")

    step = 1
    if research_mode:
        import_box = layout.box()
        import_box.label(text=f"{step}. 导入规范 Atlas", icon="IMPORT")
        import_row = import_box.row()
        import_row.scale_y = 1.5
        import_row.operator("smpl_acupoint.import_json", text="选择 Atlas JSON 并导入", icon="IMPORT")
        if scene.smpl_acupoint_annotations:
            import_box.label(
                text=f"当前已有 {len(scene.smpl_acupoint_annotations)} 个穴位；重复编码和侧别会跳过",
                icon="CHECKMARK",
            )
        else:
            import_box.label(text="请选择同为 SKEL、同一性别的正式标注 JSON", icon="INFO")
        step += 1

        shape_box = layout.box()
        shape_box.label(text=f"{step}. 调整体型与姿态（可选）", icon="ARMATURE_DATA")
        if skel_mode:
            skel_controls = getattr(scene, "skel_controls", None)
            if skel_controls is None:
                shape_box.label(text="SKEL 原生控制插件未加载", icon="ERROR")
            else:
                shape_box.prop(skel_controls, "height_shape", slider=True)
                shape_box.prop(skel_controls, "weight_shape", slider=True)
                shape_box.label(text="β0/β1 是统计体型参数，不是厘米或公斤")
                shape_box.prop(skel_controls, "show_all_pose", text="展开常用姿态", toggle=True)
                if skel_controls.show_all_pose:
                    for name in (
                        "lumbar_bending", "lumbar_extension", "lumbar_twist",
                        "thorax_bending", "thorax_extension", "thorax_twist",
                        "scapula_abduction_r", "scapula_elevation_r",
                        "scapula_abduction_l", "scapula_elevation_l",
                        "elbow_flexion_r", "elbow_flexion_l",
                        "knee_angle_r", "knee_angle_l",
                    ):
                        shape_box.prop(skel_controls, name, slider=True)
                row = shape_box.row(align=True)
                row.operator("skel.update_skin", text="更新皮肤", icon="OUTLINER_OB_MESH")
                row.operator("skel.update_all", text="更新皮肤和骨架", icon="ARMATURE_DATA")
                shape_box.operator("skel.reset_parameters", text="恢复默认", icon="LOOP_BACK")
                if scene.get("skel_parameters_dirty", False):
                    shape_box.label(text="参数已改变，点击更新后才生效", icon="ERROR")
        else:
            smplx_tool = getattr(context.window_manager, "smplx_tool", None)
            if smplx_tool is not None:
                shape_box.prop(settings, "research_height")
                shape_box.prop(settings, "research_weight")
                row = shape_box.row(align=True)
                row.operator("smpl_acupoint.apply_body_measurements", icon="CHECKMARK")
                row.operator("smpl_acupoint.reset_body_shape", icon="LOOP_BACK")
            else:
                shape_box.label(text="模型包的 SMPL-X 官方调整组件未启用", icon="ERROR")
            shape_box.prop(settings, "show_pose_controls", text="展开姿态滑动条", toggle=True)
            if settings.show_pose_controls:
                shape_box.label(text="角度单位：度；拖动后人体立即变化")
                for name in (
                    "spine1_x", "spine1_y", "spine1_z",
                    "left_shoulder_x", "right_shoulder_x",
                    "left_elbow_x", "right_elbow_x",
                    "jaw_x", "jaw_z",
                    "left_wrist_x", "right_wrist_x",
                ):
                    shape_box.prop(settings, name, slider=True)
                row = shape_box.row(align=True)
                row.operator("smpl_acupoint.reset_pose_controls", text="姿态归零", icon="LOOP_BACK")
                row.operator("smpl_acupoint.apply_pose_correctives", text="更新姿态修正", icon="MOD_SMOOTH")
            shape_box.label(text="SMPL-X 独立运行，不叠加 SKEL", icon="INFO")
        step += 1

    view_box = layout.box()
    view_box.label(text=f"{step}. 调整观察方向", icon="VIEW3D")
    view_row = view_box.row(align=True)
    for view_type, label in (("FRONT", "前"), ("BACK", "后"), ("LEFT", "左"), ("RIGHT", "右")):
        operator = view_row.operator("smpl_acupoint.back_view", text=label)
        operator.view_type = view_type
    view_box.label(text="鼠标中键旋转 · 滚轮缩放 · Shift+中键平移")
    step += 1

    if skel_mode:
        reference_box = layout.box()
        reference_box.label(text=f"{step}. 原生骨架显示（可选）", icon="OUTLINER_OB_ARMATURE")
        skel_controls = getattr(scene, "skel_controls", None)
        if skel_controls is None:
            reference_box.label(text="SKEL 原生控制插件未加载", icon="ERROR")
        else:
            reference_box.prop(skel_controls, "show_skeleton", toggle=True, icon="HIDE_OFF")
            joint_row = reference_box.row()
            joint_row.enabled = skel_controls.show_skeleton
            joint_row.prop(skel_controls, "show_joint_names")
            reference_box.label(text="皮肤和骨架来自同一 SKEL，不经过 SMPL-X 配准", icon="INFO")
            reference_box.label(text="骨架仍是结构先验，不是患者 CT", icon="INFO")
        step += 1

    draft_box = layout.box()
    draft_box.label(text=f"{step}. 填名称，再点人体", icon="PIVOT_CURSOR")
    draft_box.prop(settings, "draft_code")
    draft_box.prop(settings, "draft_name_zh")
    draft_box.prop(settings, "draft_body_region")
    draft_box.prop(settings, "draft_side", expand=True)
    row = draft_box.row()
    row.scale_y = 1.8
    row.operator("smpl_acupoint.add_surface_point", text="开始点选人体表面", icon="RESTRICT_SELECT_OFF")
    draft_box.label(text="双侧穴位必须分别选择左侧、右侧各标一次", icon="INFO")
    step += 1

    list_box = layout.box()
    list_box.label(text=f"{step}. 已标注 {len(scene.smpl_acupoint_annotations)} 个", icon="CHECKMARK")
    list_box.template_list(
        "SMPL_ACU_UL_annotations", "doctor", scene, "smpl_acupoint_annotations",
        scene, "smpl_acupoint_active_index", rows=6,
    )
    row = list_box.row(align=True)
    row.operator("smpl_acupoint.select_annotation", text="定位", icon="VIEWZOOM")
    row.operator("smpl_acupoint.remove_annotation", text="删除", icon="TRASH")

    index = scene.smpl_acupoint_active_index
    if 0 <= index < len(scene.smpl_acupoint_annotations):
        item = scene.smpl_acupoint_annotations[index]
        edit_box = list_box.box()
        edit_box.label(text="修改选中标注")
        edit_box.prop(item, "code")
        edit_box.prop(item, "name_zh")
        edit_box.prop(item, "body_region")
        side_row = edit_box.row(align=True)
        side_row.label(text="侧别")
        for side, label in (("MIDLINE", "中线"), ("LEFT", "左"), ("RIGHT", "右")):
            operator = side_row.operator(
                "smpl_acupoint.set_annotation_side",
                text=label,
                depress=item.side == side,
            )
            operator.side = side
        edit_box.prop(item, "confidence")
        edit_box.prop(item, "notes")
    step += 1

    save_box = layout.box()
    save_box.label(text=f"{step}. 保存", icon="FILE_TICK")
    save_row = save_box.row()
    save_row.scale_y = 1.8
    save_row.operator("smpl_acupoint.save_doctor_session", icon="FILE_TICK")
    save_box.label(text="只有点击上方按钮才会记录；未保存的修改不会提交", icon="INFO")
    if settings.last_save_error:
        error_row = save_box.row()
        error_row.alert = True
        error_row.label(text=settings.last_save_error, icon="ERROR")

    layout.prop(settings, "show_advanced", toggle=True, icon="PREFERENCES")
    if settings.show_advanced:
        advanced = layout.box()
        advanced.label(text=f"会话：{settings.session_id}")
        advanced.label(text=f"模板 ID：{settings.template_id}")
        if settings.target_mesh:
            advanced.label(text=f"拓扑：{_topology_signature(settings.target_mesh)[:12]}…")
        advanced.prop(settings, "marker_size")
        advanced.prop(settings, "surface_offset")
        advanced.prop(settings, "marker_color")
        advanced.label(text="内部骨架仅作结构先验，不是患者真实骨骼", icon="INFO")


class SMPL_ACU_PT_main(Panel):
    bl_label = "穴位标注"
    bl_idname = "SMPL_ACU_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "穴位标注"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.smpl_acupoint_settings

        if _is_simple_ui(scene):
            _draw_doctor_panel(layout, context)
            return

        target_box = layout.box()
        target_box.label(text="1. 选择人体", icon="OUTLINER_OB_MESH")
        target_box.prop(settings, "target_mesh")
        target_box.operator("smpl_acupoint.use_active_mesh", icon="EYEDROPPER")
        view_row = target_box.row(align=True)
        for view_type, label in (("FRONT", "前"), ("BACK", "后"), ("LEFT", "左"), ("RIGHT", "右")):
            operator = view_row.operator("smpl_acupoint.back_view", text=label)
            operator.view_type = view_type

        draft_box = layout.box()
        draft_box.label(text="2. 填写后在表面点选", icon="GREASEPENCIL")
        draft_box.prop(settings, "draft_code")
        draft_box.prop(settings, "draft_name_zh")
        draft_box.prop(settings, "draft_body_region")
        draft_box.prop(settings, "draft_meridian")
        draft_box.prop(settings, "draft_side")
        draft_box.prop(settings, "draft_notes")
        row = draft_box.row()
        row.scale_y = 1.4
        row.operator("smpl_acupoint.add_surface_point", icon="PIVOT_CURSOR")
        draft_box.label(text="临床位置由医生确认；插件不自动推荐穴位", icon="INFO")

        list_box = layout.box()
        list_box.label(text=f"3. 已标注（{len(scene.smpl_acupoint_annotations)}）", icon="PRESET")
        list_box.template_list(
            "SMPL_ACU_UL_annotations", "", scene, "smpl_acupoint_annotations",
            scene, "smpl_acupoint_active_index", rows=5,
        )
        row = list_box.row(align=True)
        row.operator("smpl_acupoint.select_annotation", text="定位", icon="VIEWZOOM")
        row.operator("smpl_acupoint.remove_annotation", text="删除", icon="TRASH")
        row.operator("smpl_acupoint.refresh_markers", text="刷新", icon="FILE_REFRESH")

        index = scene.smpl_acupoint_active_index
        if 0 <= index < len(scene.smpl_acupoint_annotations):
            item = scene.smpl_acupoint_annotations[index]
            edit_box = list_box.box()
            edit_box.label(text="选中标注信息")
            edit_box.prop(item, "code")
            edit_box.prop(item, "name_zh")
            edit_box.prop(item, "body_region")
            edit_box.prop(item, "meridian")
            edit_box.prop(item, "side")
            edit_box.prop(item, "notes")
            edit_box.prop(item, "confidence")
            edit_box.label(text=f"面 {item.face_index}  ·  重心 {tuple(round(v, 4) for v in item.barycentric)}")

        display_box = layout.box()
        display_box.label(text="显示设置", icon="HIDE_OFF")
        display_box.prop(settings, "marker_size")
        display_box.prop(settings, "surface_offset")
        display_box.prop(settings, "marker_color")

        pose_box = layout.box()
        model_family = _model_family(settings.target_mesh)
        if model_family == "SKEL":
            pose_box.label(text="SKEL 姿态由生物力学模型重新计算", icon="INFO")
            if hasattr(scene, "skel_controls"):
                pose_box.label(text="请在“SKEL 生物力学控制”中调整参数")
                pose_box.label(text="拖动后须点击“快速更新皮肤”才会变形")
                row = pose_box.row(align=True)
                row.operator("skel.update_skin", text="快速更新皮肤", icon="OUTLINER_OB_MESH")
                row.operator("skel.reset_pose", text="姿态归零并更新", icon="LOOP_BACK")
            else:
                pose_box.label(text="当前未加载 SKEL 控制，请用项目 .cmd 启动器重开", icon="ERROR")
        else:
            pose_box.prop(settings, "show_pose_controls", toggle=True)
        if model_family != "SKEL" and settings.show_pose_controls:
            pose_box.label(text="角度单位：度；采用模型骨骼局部 XYZ")
            for name in ("spine1_x", "spine1_y", "spine1_z"):
                pose_box.prop(settings, name, slider=True)
            if _model_family(settings.target_mesh) == "SMPL-X":
                pose_box.separator()
                pose_box.label(text="SMPL-X 头面与手腕")
                pose_box.prop(settings, "hand_pose")
                for name in (
                    "jaw_x", "jaw_z",
                    "left_wrist_x", "left_wrist_y", "left_wrist_z",
                    "right_wrist_x", "right_wrist_y", "right_wrist_z",
                ):
                    pose_box.prop(settings, name, slider=True)
            pose_box.separator()
            for name in (
                "left_shoulder_x", "left_shoulder_y", "left_shoulder_z",
                "right_shoulder_x", "right_shoulder_y", "right_shoulder_z",
                "left_elbow_x", "right_elbow_x",
            ):
                pose_box.prop(settings, name, slider=True)
            row = pose_box.row(align=True)
            row.operator("smpl_acupoint.reset_pose_controls", icon="LOOP_BACK")
            row.operator("smpl_acupoint.apply_pose_correctives", icon="MOD_SMOOTH")

        io_box = layout.box()
        io_box.label(text="4. 数据交换", icon="FILE")
        row = io_box.row(align=True)
        row.operator("smpl_acupoint.export_json", icon="EXPORT")
        row.operator("smpl_acupoint.import_json", icon="IMPORT")
        io_box.label(text="JSON 保存拓扑指纹、身体分区、面编号、重心坐标与 XYZ")


classes = (
    SMPLAcupointAnnotation,
    SMPLAcupointSettings,
    SMPL_ACU_UL_annotations,
    SMPL_ACU_OT_use_active_mesh,
    SMPL_ACU_OT_add_surface_point,
    SMPL_ACU_OT_select_annotation,
    SMPL_ACU_OT_remove_annotation,
    SMPL_ACU_OT_set_annotation_side,
    SMPL_ACU_OT_refresh_markers,
    SMPL_ACU_OT_back_view,
    SMPL_ACU_OT_apply_pose_correctives,
    SMPL_ACU_OT_reset_pose_controls,
    SMPL_ACU_OT_apply_body_measurements,
    SMPL_ACU_OT_reset_body_shape,
    SMPL_ACU_OT_export_json,
    SMPL_ACU_OT_save_doctor_session,
    SMPL_ACU_OT_import_json,
    SMPL_ACU_PT_main,
)


def register():
    register_translations()
    enable_blender_chinese(save_preferences=False)
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.smpl_acupoint_settings = PointerProperty(type=SMPLAcupointSettings)
    bpy.types.Scene.smpl_acupoint_annotations = CollectionProperty(type=SMPLAcupointAnnotation)
    bpy.types.Scene.smpl_acupoint_active_index = IntProperty(default=0, min=0)
    scenes = getattr(bpy.data, "scenes", None)
    if scenes is not None:
        for scene in scenes:
            _initialize_session(scene)
    if not bpy.app.background and not bpy.app.timers.is_registered(_configure_doctor_workspaces):
        bpy.app.timers.register(_configure_doctor_workspaces, first_interval=0.25)
    if _depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_handler)
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)


def unregister():
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
    if _depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_update_handler)
    del bpy.types.Scene.smpl_acupoint_active_index
    del bpy.types.Scene.smpl_acupoint_annotations
    del bpy.types.Scene.smpl_acupoint_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_translations()


if __name__ == "__main__":
    register()
