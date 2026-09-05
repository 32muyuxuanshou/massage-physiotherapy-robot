# SPDX-License-Identifier: MIT
"""Local Blender controls for the separately licensed SKEL research model."""

bl_info = {
    "name": "SKEL 生物力学模型控制",
    "author": "Massage Therapy Robot Project",
    "version": (0, 2, 0),
    "blender": (4, 5, 0),
    "location": "3D Viewport > Sidebar > SKEL控制",
    "description": "用中文滑动条驱动本机 SKEL 皮肤、骨骼和关节输出",
    "category": "3D View",
}

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector


ADDON_DIR = Path(__file__).resolve().parent


def _skel_root():
    env_root = os.environ.get("SKEL_RESEARCH_ROOT")
    if env_root and (Path(env_root) / "skel_blender_bridge.py").exists():
        return Path(env_root).resolve()
    if bpy.data.filepath:
        file_root = Path(bpy.data.filepath).resolve().parent
        if (file_root / "skel_blender_bridge.py").exists():
            return file_root
    for candidate in ADDON_DIR.parents:
        if (candidate / "skel_blender_bridge.py").exists():
            return candidate
    return ADDON_DIR


def _activate_annotations(scene, skin):
    if hasattr(scene, "smpl_acupoint_settings"):
        # Panel draw runs repeatedly. Reassigning the same PointerProperty on every
        # redraw fires its update callback again and can recurse into marker refresh.
        if scene.smpl_acupoint_settings.target_mesh != skin:
            scene.smpl_acupoint_settings.target_mesh = skin
        return
    try:
        bpy.ops.preferences.addon_enable(module="smpl_acupoint_annotator")
    except Exception:
        return
    if hasattr(scene, "smpl_acupoint_settings"):
        if scene.smpl_acupoint_settings.target_mesh != skin:
            scene.smpl_acupoint_settings.target_mesh = skin

POSE_FIELDS = (
    ("pelvis_tilt", 0, "骨盆前后倾"),
    ("pelvis_list", 1, "骨盆侧倾"),
    ("pelvis_rotation", 2, "骨盆旋转"),
    ("hip_flexion_r", 3, "右髋屈伸"),
    ("hip_adduction_r", 4, "右髋内收外展"),
    ("hip_rotation_r", 5, "右髋旋转"),
    ("knee_angle_r", 6, "右膝屈曲"),
    ("ankle_angle_r", 7, "右踝屈伸"),
    ("subtalar_angle_r", 8, "右距下关节"),
    ("mtp_angle_r", 9, "右跖趾屈伸"),
    ("hip_flexion_l", 10, "左髋屈伸"),
    ("hip_adduction_l", 11, "左髋内收外展"),
    ("hip_rotation_l", 12, "左髋旋转"),
    ("knee_angle_l", 13, "左膝屈曲"),
    ("ankle_angle_l", 14, "左踝屈伸"),
    ("subtalar_angle_l", 15, "左距下关节"),
    ("mtp_angle_l", 16, "左跖趾屈伸"),
    ("lumbar_bending", 17, "腰椎侧屈"),
    ("lumbar_extension", 18, "腰椎屈伸"),
    ("lumbar_twist", 19, "腰椎旋转"),
    ("thorax_bending", 20, "胸椎侧屈"),
    ("thorax_extension", 21, "胸椎屈伸"),
    ("thorax_twist", 22, "胸椎旋转"),
    ("head_bending", 23, "颈部侧屈"),
    ("head_extension", 24, "颈部屈伸"),
    ("head_twist", 25, "颈部旋转"),
    ("scapula_abduction_r", 26, "右肩胛前伸后缩"),
    ("scapula_elevation_r", 27, "右肩胛上提下压"),
    ("scapula_upward_rot_r", 28, "右肩胛上回旋"),
    ("shoulder_r_x", 29, "右肩 X"),
    ("shoulder_r_y", 30, "右肩 Y"),
    ("shoulder_r_z", 31, "右肩 Z"),
    ("elbow_flexion_r", 32, "右肘屈曲"),
    ("pro_sup_r", 33, "右前臂旋前旋后"),
    ("wrist_flexion_r", 34, "右腕屈伸"),
    ("wrist_deviation_r", 35, "右腕偏斜"),
    ("scapula_abduction_l", 36, "左肩胛前伸后缩"),
    ("scapula_elevation_l", 37, "左肩胛上提下压"),
    ("scapula_upward_rot_l", 38, "左肩胛上回旋"),
    ("shoulder_l_x", 39, "左肩 X"),
    ("shoulder_l_y", 40, "左肩 Y"),
    ("shoulder_l_z", 41, "左肩 Z"),
    ("elbow_flexion_l", 42, "左肘屈曲"),
    ("pro_sup_l", 43, "左前臂旋前旋后"),
    ("wrist_flexion_l", 44, "左腕屈伸"),
    ("wrist_deviation_l", 45, "左腕偏斜"),
)


def _find_skin(scene):
    settings = getattr(scene, "smpl_acupoint_settings", None)
    scene_gender = str(scene.get("skel_gender", "female"))
    if (
        settings
        and settings.target_mesh
        and settings.target_mesh.get("body_model") == "skel"
        and settings.target_mesh.get("gender") == scene_gender
    ):
        return settings.target_mesh
    return bpy.data.objects.get(f"SKEL-skin-{scene_gender}")


def _find_skeleton(scene):
    return bpy.data.objects.get(f"SKEL-skeleton-{scene.get('skel_gender', 'female')}")


def _parameters(settings):
    betas = [float(value) for value in settings.betas]
    betas[0] = float(settings.height_shape)
    betas[1] = float(settings.weight_shape)
    pose = [0.0] * 46
    for field, index, _label in POSE_FIELDS:
        pose[index] = math.radians(float(getattr(settings, field)))
    return {
        "betas": betas,
        "pose": pose,
        "trans": [0.0, 0.0, 0.0],
    }


def _read_obj_vertices(path):
    vertices = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                values = line.split()
                vertices.append((float(values[1]), float(values[2]), float(values[3])))
    return vertices


def _update_mesh_vertices(obj, path):
    vertices = _read_obj_vertices(path)
    if len(vertices) != len(obj.data.vertices):
        raise RuntimeError(
            f"拓扑不匹配：文件 {len(vertices)} 顶点，Blender 对象 {len(obj.data.vertices)} 顶点"
        )
    for vertex, coordinate in zip(obj.data.vertices, vertices):
        vertex.co = coordinate
    obj.data.update()


def _update_joint_markers(scene, joints_path):
    with open(joints_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    collection = bpy.data.collections.get("SKEL_关节")
    if collection is None:
        collection = bpy.data.collections.new("SKEL_关节")
        scene.collection.children.link(collection)
    for name, coordinate in zip(payload["joint_names"], payload["joints"]):
        obj = bpy.data.objects.get(f"SKEL-joint-{name}")
        if obj is None:
            obj = bpy.data.objects.new(f"SKEL-joint-{name}", None)
            obj.empty_display_type = "SPHERE"
            obj.empty_display_size = 0.012
            collection.objects.link(obj)
        obj.show_name = bool(getattr(scene.skel_controls, "show_joint_names", False))
        obj.location = coordinate


def _run_bridge(scene, skin_only=False):
    annotation_settings = getattr(scene, "smpl_acupoint_settings", None)
    if annotation_settings and annotation_settings.workflow_mode == "DOCTOR_ATLAS":
        raise RuntimeError("规范 Atlas 已锁定 SKEL 体型和姿态；请从启动器选择内部研究模式")
    settings = scene.skel_controls
    skin = _find_skin(scene)
    if skin is None:
        raise RuntimeError("当前文件缺少 SKEL 皮肤对象")
    gender = str(skin.get("gender", scene.get("skel_gender", "female")))
    root = _skel_root()
    python_override = os.environ.get("SKEL_PYTHON_EXE")
    python_exe = Path(python_override).resolve() if python_override else root / ".venv" / "Scripts" / "python.exe"
    bridge_script = root / "skel_blender_bridge.py"
    work_dir = root / "output" / "blender_bridge"
    if not python_exe.exists() or not bridge_script.exists():
        raise RuntimeError("SKEL 本机计算环境不完整；请重新运行首次配置")
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="utf-8", delete=False, dir=work_dir
    ) as handle:
        json.dump(_parameters(settings), handle, ensure_ascii=False, indent=2)
        parameter_path = Path(handle.name)
    command = [
        str(python_exe), str(bridge_script),
        "--gender", gender,
        "--parameters", str(parameter_path),
        "--output", str(work_dir),
    ]
    if skin_only:
        command.append("--skin-only")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    child_env = os.environ.copy()
    loader_override = os.environ.get("SKEL_LOADER_ROOT")
    if loader_override:
        child_env["SKEL_LOADER_ROOT"] = loader_override
    result = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        timeout=180,
        startupinfo=startup,
        env=child_env,
    )
    try:
        parameter_path.unlink(missing_ok=True)
    except OSError:
        pass
    if result.returncode != 0:
        message_bytes = result.stderr or result.stdout or b""
        try:
            message = message_bytes.decode("utf-8")
        except UnicodeDecodeError:
            message = message_bytes.decode("gbk", errors="replace")
        raise RuntimeError(message.strip() or "SKEL 计算失败")

    _update_mesh_vertices(skin, work_dir / f"skin_{gender}.obj")

    if not skin_only:
        skeleton = _find_skeleton(scene)
        if skeleton is None:
            raise RuntimeError("当前文件缺少 SKEL 骨骼对象")
        _update_mesh_vertices(skeleton, work_dir / f"skeleton_{gender}.obj")
    _update_joint_markers(scene, work_dir / f"joints_{gender}.json")

    _activate_annotations(scene, skin)
    try:
        bpy.ops.smpl_acupoint.refresh_markers()
    except Exception:
        pass
    scene["skel_betas"] = list(_parameters(settings)["betas"])
    scene["skel_pose_degrees"] = {
        field: float(getattr(settings, field)) for field, _index, _label in POSE_FIELDS
    }
    scene["skel_gender"] = gender
    scene["skel_parameters_dirty"] = False
    bpy.context.view_layer.update()


def _parameter_changed(self, context):
    if context and context.scene:
        context.scene["skel_parameters_dirty"] = True


def _apply_visibility(scene):
    settings = scene.skel_controls
    skin = _find_skin(scene)
    skeleton = _find_skeleton(scene)
    if skin:
        skin.hide_viewport = not settings.show_skin
        skin.hide_render = not settings.show_skin
    if skeleton:
        skeleton.hide_select = True
        skeleton.hide_viewport = not settings.show_skeleton
        skeleton.hide_render = not settings.show_skeleton
    joint_collection = bpy.data.collections.get("SKEL_关节")
    if joint_collection:
        show_joints = bool(settings.show_skeleton and settings.show_joint_names)
        joint_collection.hide_viewport = not show_joints
        joint_collection.hide_render = not show_joints
        for joint in joint_collection.objects:
            joint.hide_select = True
            joint.show_name = show_joints
    scene["skel_native_skeleton_visible"] = bool(settings.show_skeleton)
    annotation_settings = getattr(scene, "smpl_acupoint_settings", None)
    if annotation_settings is not None and settings.show_skeleton:
        annotation_settings.skel_reference_used = True


def _visibility_changed(self, context):
    if context and context.scene and hasattr(context.scene, "skel_controls"):
        _apply_visibility(context.scene)


class SKELControls(PropertyGroup):
    betas: FloatVectorProperty(
        name="体型参数 β0–β9",
        size=10,
        min=-2.0,
        max=2.0,
        default=(0.0,) * 10,
        update=_parameter_changed,
    )
    height_shape: FloatProperty(
        name="身高体型 β0",
        description="SKEL 统计体型参数，不是厘米",
        min=-2.0,
        max=2.0,
        default=0.0,
        update=_parameter_changed,
    )
    weight_shape: FloatProperty(
        name="体重体型 β1",
        description="SKEL 统计体型参数，不是公斤",
        min=-2.0,
        max=2.0,
        default=0.0,
        update=_parameter_changed,
    )
    show_all_pose: BoolProperty(name="显示全部姿态参数", default=False)
    show_skeleton: BoolProperty(name="显示内部骨骼", default=False, update=_visibility_changed)
    show_skin: BoolProperty(name="显示皮肤", default=True, update=_visibility_changed)
    show_joint_names: BoolProperty(name="显示关节名称", default=False, update=_visibility_changed)


for _field, _index, _label in POSE_FIELDS:
    SKELControls.__annotations__[_field] = FloatProperty(
        name=f"{_label}（度）",
        min=-180.0,
        max=180.0,
        default=0.0,
        update=_parameter_changed,
    )


class SKEL_OT_update_skin(Operator):
    bl_idname = "skel.update_skin"
    bl_label = "快速更新皮肤"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            _run_bridge(context.scene, skin_only=True)
        except Exception as error:
            self.report({"ERROR"}, str(error)[-900:])
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 皮肤已更新")
        return {"FINISHED"}


class SKEL_OT_update_all(Operator):
    bl_idname = "skel.update_all"
    bl_label = "完整更新皮肤和骨骼"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            _run_bridge(context.scene, skin_only=False)
        except Exception as error:
            self.report({"ERROR"}, str(error)[-900:])
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 皮肤、骨骼和关节已更新")
        return {"FINISHED"}


class SKEL_OT_reset(Operator):
    bl_idname = "skel.reset_parameters"
    bl_label = "恢复默认并更新皮肤"

    def execute(self, context):
        settings = context.scene.skel_controls
        settings.betas = (0.0,) * 10
        settings.height_shape = 0.0
        settings.weight_shape = 0.0
        for field, _index, _label in POSE_FIELDS:
            setattr(settings, field, 0.0)
        context.scene["skel_parameters_dirty"] = True
        try:
            _run_bridge(context.scene, skin_only=True)
        except Exception as error:
            self.report({"ERROR"}, str(error)[-900:])
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 已恢复默认体型和姿势，并更新皮肤")
        return {"FINISHED"}


class SKEL_OT_reset_pose(Operator):
    bl_idname = "skel.reset_pose"
    bl_label = "姿态归零并更新"

    def execute(self, context):
        settings = context.scene.skel_controls
        for field, _index, _label in POSE_FIELDS:
            setattr(settings, field, 0.0)
        context.scene["skel_parameters_dirty"] = True
        try:
            _run_bridge(context.scene, skin_only=True)
        except Exception as error:
            self.report({"ERROR"}, str(error)[-900:])
            return {"CANCELLED"}
        self.report({"INFO"}, "SKEL 姿态已归零并更新皮肤；体型参数保持不变")
        return {"FINISHED"}


class SKEL_OT_visibility(Operator):
    bl_idname = "skel.apply_visibility"
    bl_label = "应用显示设置"

    def execute(self, context):
        _apply_visibility(context.scene)
        return {"FINISHED"}


class SKEL_PT_controls(Panel):
    bl_label = "SKEL 生物力学控制"
    bl_idname = "SKEL_PT_controls"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # 与穴位标注统一放入始终可见的 Item/项目页签，方便医生在小屏幕使用。
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.skel_controls
        skin = _find_skin(scene)
        if skin is not None:
            _activate_annotations(scene, skin)
        annotation_settings = getattr(scene, "smpl_acupoint_settings", None)
        doctor_atlas = bool(
            annotation_settings and annotation_settings.workflow_mode == "DOCTOR_ATLAS"
        )

        box = layout.box()
        box.label(text="1. 模型和显示", icon="ARMATURE_DATA")
        gender_label = "女性 SKEL" if scene.get("skel_gender", "female") == "female" else "男性 SKEL"
        box.label(text=f"当前模型：{gender_label}")
        box.label(text="切换男女请返回启动器打开对应模板")
        row = box.row(align=True)
        row.prop(settings, "show_skin")
        row.prop(settings, "show_skeleton")
        row = box.row()
        row.enabled = settings.show_skeleton
        row.prop(settings, "show_joint_names")
        box.label(text="需要结构对照时显示骨骼；穴位仍点在皮肤上")

        if doctor_atlas:
            lock = layout.box()
            lock.label(text="规范 Atlas 已锁定体型和姿态", icon="LOCKED")
            lock.label(text="如需调节，请从启动器选择“内部研究”")
            lock.label(text="骨架是结构先验，不是患者 CT", icon="INFO")
            return

        shape = layout.box()
        shape.label(text="2. 简化体型（建议 -2～2）", icon="MOD_ARMATURE")
        shape.prop(settings, "height_shape", slider=True)
        shape.prop(settings, "weight_shape", slider=True)
        shape.label(text="它们是统计参数，不是厘米或公斤")
        shape.prop(settings, "betas", text="高级 β0–β9")
        shape.label(text="计算时 β0/β1 以上方两个简化滑条为准")

        pose = layout.box()
        pose.label(text="3. 常用按摩体位", icon="POSE_HLT")
        pose.label(text="滑动只修改参数；点击下方更新后人体才会变形", icon="INFO")
        for field in (
            "lumbar_bending", "lumbar_extension", "lumbar_twist",
            "thorax_bending", "thorax_extension", "thorax_twist",
            "head_bending", "head_extension", "head_twist",
            "scapula_abduction_r", "scapula_elevation_r", "scapula_upward_rot_r",
            "scapula_abduction_l", "scapula_elevation_l", "scapula_upward_rot_l",
            "elbow_flexion_r", "pro_sup_r", "wrist_flexion_r",
            "elbow_flexion_l", "pro_sup_l", "wrist_flexion_l",
        ):
            pose.prop(settings, field, slider=True)
        pose.prop(settings, "show_all_pose", toggle=True)
        if settings.show_all_pose:
            common = {
                "lumbar_bending", "lumbar_extension", "lumbar_twist",
                "thorax_bending", "thorax_extension", "thorax_twist",
                "head_bending", "head_extension", "head_twist",
                "scapula_abduction_r", "scapula_elevation_r", "scapula_upward_rot_r",
                "scapula_abduction_l", "scapula_elevation_l", "scapula_upward_rot_l",
                "elbow_flexion_r", "pro_sup_r", "wrist_flexion_r",
                "elbow_flexion_l", "pro_sup_l", "wrist_flexion_l",
            }
            for field, _index, _label in POSE_FIELDS:
                if field not in common:
                    pose.prop(settings, field, slider=True)

        run = layout.box()
        run.label(text="4. 计算并刷新", icon="FILE_REFRESH")
        if scene.get("skel_parameters_dirty", False):
            run.label(text="参数已改动，点击更新后生效", icon="ERROR")
        row = run.row(align=True)
        row.scale_y = 1.35
        row.operator("skel.update_skin", icon="OUTLINER_OB_MESH")
        row.operator("skel.update_all", icon="ARMATURE_DATA")
        run.operator("skel.reset_parameters", text="恢复默认并更新皮肤", icon="LOOP_BACK")
        run.label(text="完整更新较慢；皮肤点标注会随更新后的网格刷新")
        run.label(text="SKEL 无手指关节和面部表情，请用 SMPL-X 标注这些区域")


CLASSES = (
    SKELControls,
    SKEL_OT_update_skin,
    SKEL_OT_update_all,
    SKEL_OT_reset,
    SKEL_OT_reset_pose,
    SKEL_OT_visibility,
    SKEL_PT_controls,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skel_controls = bpy.props.PointerProperty(type=SKELControls)


def unregister():
    del bpy.types.Scene.skel_controls
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
