"""Build one doctor SMPL-X template from the user's licensed Blender add-on."""

import argparse
import os
import sys

import bpy
import smpl_acupoint_annotator as annotator


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gender", choices=("female", "male", "neutral"), required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


args = arguments()
bpy.ops.preferences.addon_enable(module="bl_ext.user_default.smplx_blender_addon")
bpy.ops.preferences.addon_enable(module="smpl_acupoint_annotator")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

tool = bpy.context.window_manager.smplx_tool
tool.body_model = "smplx"
tool.smplx_version = "locked_head"
tool.smplx_gender = args.gender
tool.smplx_uv = "UV_2023"
tool.smplx_texture = "NONE"
result = bpy.ops.scene.smplx_add_gender("EXEC_DEFAULT")
if "FINISHED" not in result:
    raise RuntimeError(f"SMPL-X creation failed: {result}")

mesh = bpy.context.active_object
if mesh is None or mesh.type != "MESH":
    raise RuntimeError("SMPL-X add-on did not create an active mesh")
if len(mesh.data.vertices) != 10475 or len(mesh.data.polygons) != 20908:
    raise RuntimeError("Unexpected SMPL-X topology")

scene = bpy.context.scene
scene.smpl_acupoint_settings.target_mesh = mesh
scene.smpl_acupoint_settings.workflow_mode = "DOCTOR_ATLAS"
scene.smpl_acupoint_settings.draft_body_region = "TORSO"
scene.smpl_acupoint_settings.current_pose_id = "CANONICAL_TEMPLATE_DEFAULT"
scene["template_role"] = "SMPL-X locked full-body doctor annotation template"
scene["medical_warning"] = "Doctors determine all clinical labels and locations."
scene["license_warning"] = "Locally generated from the current user's licensed SMPL-X files; do not redistribute."
scene["smplx_gender"] = args.gender
signature = annotator._topology_signature(mesh)
scene["smplx_topology_signature_sha256"] = signature
mesh["smplx_template_target"] = True
mesh["smplx_template_id"] = f"smplx-{args.gender}-doctor-v1"
mesh["smplx_canonical_shape_id"] = "shape-zero"
mesh["smplx_canonical_pose_id"] = "template-default"
mesh["smplx_template_topology_sha256"] = signature
mesh["smplx_template_shape_sha256"] = annotator._shape_signature(mesh)
mesh["smplx_template_pose_sha256"] = annotator._pose_signature(mesh)
mesh.hide_select = True
if mesh.parent and mesh.parent.type == "ARMATURE":
    mesh.parent.hide_select = True
    mesh.parent.hide_set(True)
    mesh.parent.hide_render = True

readme = bpy.data.texts.new("README_医生标注说明.txt")
readme.write(
    "本模板由当前医生电脑上的官方授权文件本地生成。\n"
    "所有穴位名称和位置必须由专业医生确认。\n"
    "正式 Atlas 模式锁定人体体型和姿态；医生只旋转视图并点选表面。\n"
    "本文件仍受 SMPL-X 原许可约束，不得转发给未授权人员。\n"
)

output = os.path.abspath(args.output)
os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
print(f"DOCTOR_SMPLX_{args.gender.upper()}_BUILD=PASS")
