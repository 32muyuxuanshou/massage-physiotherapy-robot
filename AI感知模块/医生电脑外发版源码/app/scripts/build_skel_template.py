"""Build one doctor SKEL template from locally generated OBJ files."""

import argparse
import json
import os
import sys

import bpy


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gender", choices=("female", "male"), required=True)
    parser.add_argument("--skin", required=True)
    parser.add_argument("--skeleton", required=True)
    parser.add_argument("--joints", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def import_obj(path):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    created = [obj for obj in bpy.data.objects if obj not in before]
    return next(obj for obj in created if obj.type == "MESH")


def material(name, color, roughness):
    value = bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    shader = value.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    return value


args = arguments()
bpy.ops.preferences.addon_enable(module="smpl_acupoint_annotator")
bpy.ops.preferences.addon_enable(module="skel_blender_controls")
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

skin = import_obj(os.path.abspath(args.skin))
skin.name = f"SKEL-skin-{args.gender}"
skin["body_model"] = "skel"
skin["gender"] = args.gender
skin["skel_version"] = "1.1"
skin["skel_role"] = "skin"
skin.data.materials.append(material("SKEL_皮肤", (0.68, 0.48, 0.37, 1.0), 0.7))

skeleton = import_obj(os.path.abspath(args.skeleton))
skeleton.name = f"SKEL-skeleton-{args.gender}"
skeleton["body_model"] = "skel"
skeleton["gender"] = args.gender
skeleton["skel_version"] = "1.1"
skeleton["skel_role"] = "skeleton"
skeleton.show_in_front = True
skeleton.data.materials.append(material("SKEL_骨骼", (0.9, 0.84, 0.64, 1.0), 0.55))

with open(args.joints, "r", encoding="utf-8") as handle:
    joint_data = json.load(handle)
joint_collection = bpy.data.collections.new("SKEL_关节")
bpy.context.scene.collection.children.link(joint_collection)
for name, coordinate in zip(joint_data["joint_names"], joint_data["joints"]):
    marker = bpy.data.objects.new(f"SKEL-joint-{name}", None)
    marker.empty_display_type = "SPHERE"
    marker.empty_display_size = 0.012
    marker.location = coordinate
    joint_collection.objects.link(marker)

scene = bpy.context.scene
scene.smpl_acupoint_settings.target_mesh = skin
scene.smpl_acupoint_settings.draft_body_region = "TORSO"
scene.skel_controls.show_skin = True
scene.skel_controls.show_skeleton = False
scene.skel_controls.show_joint_names = False
skeleton.hide_viewport = True
skeleton.hide_render = True
joint_collection.hide_viewport = True
joint_collection.hide_render = True
scene["template_role"] = "SKEL biomechanical doctor annotation template"
scene["medical_warning"] = "Doctors determine all clinical labels and locations."
scene["license_warning"] = "Locally generated from the current user's licensed SKEL files; do not redistribute."
scene["skel_gender"] = args.gender
scene["skel_betas"] = [0.0] * 10
scene["skel_pose_degrees"] = {field: 0.0 for field, _index, _label in __import__("skel_blender_controls").POSE_FIELDS}
scene["skel_parameters_dirty"] = False

readme = bpy.data.texts.new("README_SKEL使用说明.txt")
readme.write(
    "本模板由当前医生电脑上的官方授权文件本地生成。\n"
    "调整参数后点击快速更新或完整更新。\n"
    "本文件仍受 SKEL 原许可约束，不得转发给未授权人员。\n"
)

bpy.ops.object.select_all(action="DESELECT")
skin.select_set(True)
bpy.context.view_layer.objects.active = skin
output = os.path.abspath(args.output)
os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
print(f"DOCTOR_SKEL_{args.gender.upper()}_BUILD=PASS")
