# SPDX-License-Identifier: MIT
"""Toggle and fit a licensed SKEL reference below a SMPL-X surface.

The reference is deliberately display-only.  Acupoints continue to belong to
the SMPL-X mesh and SKEL must never become an annotation target.
"""

from __future__ import annotations

bl_info = {
    "name": "SMPL-X + SKEL 内部结构参考",
    "author": "Massage Therapy Robot Project",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Sidebar > 穴位标注",
    "description": "在 SMPL-X 下方显示不可选中的 SKEL 结构参考，并按需重新拟合",
    "category": "3D View",
}

import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

import bpy
import numpy as np
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector


PACK_SCHEMA = "smplx-skel-model-pack-v2"
REFERENCE_OBJECT = "SKEL_结构参考_不可标注"
REFERENCE_COLLECTION = "SKEL_内部结构参考"
REFERENCE_MATERIAL = "SKEL_参考蓝"
FIT_METHOD = "project-surface-fit-v1"
MEDICAL_NOTICE = "SKEL 仅作生物力学结构参考，不是患者 CT 或真实骨骼定位"
_auto_load_scheduled = False


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _settings(scene=None):
    scene = scene or bpy.context.scene
    return getattr(scene, "smplx_skel_reference", None)


def _target(scene=None):
    scene = scene or bpy.context.scene
    annotation = getattr(scene, "smpl_acupoint_settings", None)
    if annotation and annotation.target_mesh and annotation.target_mesh.type == "MESH":
        if len(annotation.target_mesh.data.vertices) == 10475:
            return annotation.target_mesh
    candidates = [
        obj for obj in scene.objects
        if obj.type == "MESH" and len(obj.data.vertices) == 10475
    ]
    return candidates[0] if len(candidates) == 1 else None


def _gender(scene=None, target=None):
    scene = scene or bpy.context.scene
    target = target or _target(scene)
    values = []
    annotation = getattr(scene, "smpl_acupoint_settings", None)
    if annotation:
        values.append(annotation.template_gender)
    if target:
        values.extend((target.get("smplx_gender", ""), target.get("gender", "")))
    for value in values:
        text = str(value).strip().lower()
        if text in {"female", "女性", "f"}:
            return "female"
        if text in {"male", "男性", "m"}:
            return "male"
        if text in {"neutral", "中性", "n"}:
            return "neutral"
    return "unknown"


def _pack_root(scene=None):
    settings = _settings(scene)
    configured = settings.model_pack_root.strip() if settings else ""
    value = configured or os.environ.get("SMPLX_SKEL_MODEL_PACK_ROOT", "").strip()
    return Path(bpy.path.abspath(value)).resolve() if value else None


def _read_manifest(scene=None):
    root = _pack_root(scene)
    if root is None:
        raise ValueError("未连接 v2.2 内部模型包，请从 v2.2 启动器打开")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"模型包缺少 manifest.json：{root}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != PACK_SCHEMA:
        raise ValueError("不是兼容的 v2.2 SMPL-X + SKEL 模型包")
    return root, payload


def _reference_object(scene=None):
    scene = scene or bpy.context.scene
    return scene.objects.get(REFERENCE_OBJECT)


def _apply_display(scene=None):
    settings = _settings(scene)
    obj = _reference_object(scene)
    if settings is None or obj is None:
        return
    obj.hide_viewport = not settings.enabled
    obj.hide_render = not settings.enabled
    obj.hide_select = True
    obj.show_in_front = settings.xray
    obj.display_type = "SOLID"
    obj.color = (0.04, 0.34, 0.92, float(settings.opacity))
    for material in obj.data.materials:
        material.diffuse_color = (0.04, 0.34, 0.92, float(settings.opacity))
        material.blend_method = "BLEND"
        material.show_transparent_back = True
    active_scene = scene or bpy.context.scene
    active_scene["skel_reference_visible"] = bool(settings.enabled)
    annotation = getattr(active_scene, "smpl_acupoint_settings", None)
    if annotation is not None and settings.enabled:
        annotation.skel_reference_used = True


def _display_update(self, context):
    _apply_display(context.scene)


def _ensure_collection(scene):
    collection = bpy.data.collections.get(REFERENCE_COLLECTION)
    if collection is None:
        collection = bpy.data.collections.new(REFERENCE_COLLECTION)
    if collection.name not in {item.name for item in scene.collection.children}:
        scene.collection.children.link(collection)
    collection.hide_select = True
    return collection


def _read_obj(path):
    vertices = []
    faces = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    x, y, z = (float(parts[1]), float(parts[2]), float(parts[3]))
                    # SKEL/OpenSim Y-up -> Blender Z-up.
                    vertices.append((x, -z, y))
            elif line.startswith("f "):
                raw = [token.split("/", 1)[0] for token in line.split()[1:]]
                polygon = []
                for token in raw:
                    index = int(token)
                    polygon.append(index - 1 if index > 0 else len(vertices) + index)
                if len(polygon) >= 3:
                    faces.append(tuple(polygon))
    if not vertices or not faces:
        raise ValueError(f"SKEL OBJ 无有效网格：{path}")
    return vertices, faces


def _load_reference(scene, obj_path, fit_path, pack_id):
    old = _reference_object(scene)
    if old is not None:
        mesh = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    vertices, faces = _read_obj(obj_path)
    mesh = bpy.data.meshes.new("SKEL_结构参考网格")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(REFERENCE_OBJECT, mesh)
    _ensure_collection(scene).objects.link(obj)

    material = bpy.data.materials.get(REFERENCE_MATERIAL)
    if material is None:
        material = bpy.data.materials.new(REFERENCE_MATERIAL)
    if len(mesh.materials) == 0:
        mesh.materials.append(material)

    fit = json.loads(Path(fit_path).read_text(encoding="utf-8-sig"))
    target = _target(scene)
    target_hash = _evaluated_target_hash(target) if target else ""
    registration_id = f"{FIT_METHOD}:{fit.get('gender', 'unknown')}:{target_hash[:16]}"
    obj["reference_role"] = "SKEL_STRUCTURAL_REFERENCE_ONLY"
    obj["annotation_target_allowed"] = False
    obj["medical_ground_truth"] = False
    obj["registration_id"] = registration_id
    obj["registration_method"] = str(fit.get("method", FIT_METHOD))
    obj["surface_rmse_m"] = float(fit.get("surface_rmse_m", -1.0))
    obj["surface_distance_p95_m"] = float(fit.get("surface_distance_p95_m", -1.0))
    obj["model_pack_id"] = pack_id
    obj["notice"] = MEDICAL_NOTICE

    settings = _settings(scene)
    settings.enabled = True
    settings.last_status = "骨架参考已加载"
    settings.last_error = ""
    settings.registration_id = registration_id
    settings.registration_method = obj["registration_method"]
    settings.surface_rmse_m = obj["surface_rmse_m"]
    settings.surface_p95_m = obj["surface_distance_p95_m"]
    settings.model_pack_id = pack_id
    annotation = getattr(scene, "smpl_acupoint_settings", None)
    if annotation is not None:
        annotation.skel_reference_used = True
        annotation.skel_registration_id = registration_id
    scene["skel_reference_used"] = True
    scene["skel_reference_visible"] = True
    scene["skel_registration_id"] = registration_id
    scene["skel_registration_method"] = settings.registration_method
    scene["skel_surface_rmse_m"] = settings.surface_rmse_m
    scene["skel_surface_distance_p95_m"] = settings.surface_p95_m
    scene["skel_model_pack_id"] = pack_id
    scene["skel_reference_notice"] = MEDICAL_NOTICE
    _apply_display(scene)
    return obj


def _evaluated_vertices(target):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        values = np.asarray(
            [
                (
                    float((evaluated.matrix_world @ vertex.co).x),
                    float((evaluated.matrix_world @ vertex.co).z),
                    -float((evaluated.matrix_world @ vertex.co).y),
                )
                for vertex in evaluated_mesh.vertices
            ],
            dtype=np.float32,
        )
    finally:
        evaluated.to_mesh_clear()
    if values.shape != (10475, 3):
        raise ValueError(f"当前目标不是标准 SMPL-X 拓扑：{values.shape}")
    return values


def _evaluated_target_hash(target):
    return hashlib.sha256(_evaluated_vertices(target).tobytes()).hexdigest()


def _export_target(target, output, gender):
    vertices = _evaluated_vertices(target)
    faces = np.asarray([tuple(face.vertices) for face in target.data.polygons], dtype=np.int32)
    np.savez_compressed(
        output,
        vertices=vertices,
        faces=faces,
        target_name=target.name,
        gender=gender,
    )
    return hashlib.sha256(vertices.tobytes()).hexdigest()


class SMPLXSKELReferenceSettings(PropertyGroup):
    model_pack_root: StringProperty(name="模型包目录", subtype="DIR_PATH")
    enabled: BoolProperty(name="显示 SKEL 骨架参考", default=True, update=_display_update)
    opacity: FloatProperty(name="骨架不透明度", min=0.1, max=1.0, default=0.72, update=_display_update)
    xray: BoolProperty(name="透过皮肤显示", default=True, update=_display_update)
    last_status: StringProperty(name="状态")
    last_error: StringProperty(name="错误")
    registration_id: StringProperty(name="配准编号")
    registration_method: StringProperty(name="配准方法")
    surface_rmse_m: FloatProperty(name="表面拟合 RMSE", default=-1.0)
    surface_p95_m: FloatProperty(name="表面距离 P95", default=-1.0)
    model_pack_id: StringProperty(name="模型包编号")


class SMPLX_SKEL_OT_load_reference(Operator):
    bl_idname = "smplx_skel.load_reference"
    bl_label = "加载/恢复骨架参考"
    bl_description = "从内部模型包加载当前性别的规范 SKEL 参考"

    def execute(self, context):
        scene = context.scene
        settings = _settings(scene)
        try:
            root, manifest = _read_manifest(scene)
            gender = _gender(scene)
            if gender == "neutral":
                raise ValueError("中性 SMPL-X 没有官方中性 SKEL；请选择女性或男性模板")
            if gender not in {"female", "male"}:
                raise ValueError("无法识别 SMPL-X 性别")
            obj_path = root / "alignment" / f"fitted_{gender}" / f"skel_reference_{gender}.obj"
            fit_path = root / "alignment" / f"fitted_{gender}" / f"skel_fit_{gender}.json"
            if not obj_path.is_file() or not fit_path.is_file():
                raise ValueError(f"模型包缺少 {gender} SKEL 基线配准")
            _load_reference(scene, obj_path, fit_path, str(manifest.get("pack_id", "")))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            settings.last_error = str(error)
            settings.last_status = "加载失败"
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 结构参考已加载；穴位仍只标在 SMPL-X 上")
        return {"FINISHED"}


class SMPLX_SKEL_OT_update_alignment(Operator):
    bl_idname = "smplx_skel.update_alignment"
    bl_label = "按当前体型/姿态更新骨架"
    bl_description = "模型调整后重新拟合 SKEL；通常需要约 10 秒"

    def execute(self, context):
        scene = context.scene
        settings = _settings(scene)
        try:
            root, manifest = _read_manifest(scene)
            target = _target(scene)
            if target is None:
                raise ValueError("未找到唯一的 SMPL-X 标注表面")
            gender = _gender(scene, target)
            if gender == "neutral":
                raise ValueError("中性 SMPL-X 不自动套用女性或男性骨架")
            if gender not in {"female", "male"}:
                raise ValueError("无法识别 SMPL-X 性别")

            python_exe = Path(os.environ.get("SMPLX_SKEL_PYTHON_EXE", "")).resolve()
            fit_script = Path(os.environ.get("SMPLX_SKEL_FIT_SCRIPT", "")).resolve()
            loader_root = root / "licensed" / "SKEL" / "loader"
            mapping = root / "alignment" / f"mapping_{gender}.npz"
            baseline = root / "alignment" / f"fitted_{gender}" / f"skel_fit_{gender}.json"
            for path, label in (
                (python_exe, "配准 Python"), (fit_script, "配准脚本"),
                (loader_root / "skel" / "skel_model.py", "SKEL Loader"),
                (mapping, "配准映射"), (baseline, "基线参数"),
            ):
                if not path.is_file() and label != "SKEL Loader":
                    raise ValueError(f"缺少{label}：{path}")
                if label == "SKEL Loader" and not path.is_file():
                    raise ValueError(f"缺少{label}：{path}")

            cache_root = Path(os.environ.get("SMPLX_SKEL_CACHE_ROOT", "").strip() or (Path(bpy.data.filepath).parent / "_skel_cache"))
            cache_root.mkdir(parents=True, exist_ok=True)
            provisional = cache_root / f"current_{gender}.npz"
            target_hash = _export_target(target, provisional, gender)
            fit_root = cache_root / gender / target_hash[:16]
            fit_root.mkdir(parents=True, exist_ok=True)
            target_path = fit_root / "smplx_target.npz"
            if provisional != target_path:
                provisional.replace(target_path)
            output_obj = fit_root / f"skel_reference_{gender}.obj"
            output_json = fit_root / f"skel_fit_{gender}.json"
            if not output_obj.is_file() or not output_json.is_file():
                settings.last_status = "正在重新拟合骨架，请稍候……"
                command = [
                    str(python_exe), str(fit_script),
                    "--target", str(target_path),
                    "--mapping", str(mapping),
                    "--gender", gender,
                    "--loader-root", str(loader_root),
                    "--output", str(fit_root),
                    "--initial-parameters", str(baseline),
                    "--steps", "80",
                ]
                result = subprocess.run(
                    command,
                    cwd=str(fit_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=180,
                    check=False,
                )
                if result.returncode != 0 or "SMPLX_SKEL_FIT=PASS" not in result.stdout:
                    detail = (result.stderr or result.stdout or "没有输出").strip()[-1200:]
                    raise ValueError(f"SKEL 重新拟合失败：{detail}")
            _load_reference(scene, output_obj, output_json, str(manifest.get("pack_id", "")))
            settings.last_status = "骨架已按当前模型更新"
            scene["skel_alignment_updated_at"] = _utc_now()
        except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            settings.last_error = str(error)
            settings.last_status = "更新失败"
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 已按当前 SMPL-X 更新")
        return {"FINISHED"}


class SMPLX_SKEL_PT_reference(Panel):
    bl_label = "SKEL 骨架参考（内部）"
    bl_idname = "SMPLX_SKEL_PT_reference"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "穴位标注"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = _settings(context.scene)
        gender = _gender(context.scene)

        warning = layout.box()
        warning.alert = True
        warning.label(text="仅作结构参考，不是患者真实骨骼", icon="INFO")
        warning.label(text="穴位始终只保存在 SMPL-X 表面")
        if gender == "neutral":
            warning.label(text="中性模板不显示骨架；请选择女性或男性", icon="ERROR")
            return

        obj = _reference_object(context.scene)
        if obj is None:
            row = layout.row()
            row.scale_y = 1.5
            row.operator("smplx_skel.load_reference", icon="OUTLINER_OB_MESH")
        else:
            layout.prop(settings, "enabled", toggle=True, icon="HIDE_OFF")
            controls = layout.column(align=True)
            controls.enabled = settings.enabled
            controls.prop(settings, "opacity", slider=True)
            controls.prop(settings, "xray")
            row = layout.row()
            row.scale_y = 1.35
            row.operator("smplx_skel.update_alignment", icon="FILE_REFRESH")
            layout.label(text="调整体型或姿态后，再按一次更新", icon="INFO")

        if settings.surface_rmse_m >= 0:
            layout.label(text=f"表面拟合 RMSE：{settings.surface_rmse_m * 1000:.1f} mm")
            layout.label(text=f"表面距离 P95：{settings.surface_p95_m * 1000:.1f} mm")
        if settings.last_status:
            layout.label(text=settings.last_status, icon="CHECKMARK")
        if settings.last_error:
            box = layout.box()
            box.alert = True
            box.label(text=settings.last_error[:120], icon="ERROR")


def _auto_load():
    global _auto_load_scheduled
    _auto_load_scheduled = False
    if bpy.app.background or os.environ.get("SMPLX_SKEL_AUTOLOAD", "") != "1":
        return None
    scene = bpy.context.scene
    if _reference_object(scene) is None and _gender(scene) in {"female", "male"}:
        try:
            root, manifest = _read_manifest(scene)
            gender = _gender(scene)
            obj_path = root / "alignment" / f"fitted_{gender}" / f"skel_reference_{gender}.obj"
            fit_path = root / "alignment" / f"fitted_{gender}" / f"skel_fit_{gender}.json"
            _load_reference(scene, obj_path, fit_path, str(manifest.get("pack_id", "")))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            settings = _settings(scene)
            if settings is not None:
                settings.last_status = "自动加载失败"
                settings.last_error = str(error)
    return None


def _schedule_auto_load():
    global _auto_load_scheduled
    if not _auto_load_scheduled:
        _auto_load_scheduled = True
        bpy.app.timers.register(_auto_load, first_interval=0.8)


@persistent
def _load_post(_unused):
    global _auto_load_scheduled
    # File loading can discard an earlier non-persistent timer while the flag
    # remains true.  Reset it so every opened template gets one reliable pass.
    _auto_load_scheduled = False
    _schedule_auto_load()


classes = (
    SMPLXSKELReferenceSettings,
    SMPLX_SKEL_OT_load_reference,
    SMPLX_SKEL_OT_update_alignment,
    SMPLX_SKEL_PT_reference,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.smplx_skel_reference = PointerProperty(type=SMPLXSKELReferenceSettings)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    _schedule_auto_load()


def unregister():
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    del bpy.types.Scene.smplx_skel_reference
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
