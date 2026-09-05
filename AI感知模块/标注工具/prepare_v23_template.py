"""Prepare independent SKEL/SMPL-X v2.3 Blender templates.

Run from Blender in background mode.  The source model files remain untouched.
"""

import argparse
import os
import sys
from pathlib import Path

import bpy


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=("SKEL", "SMPL-X"), required=True)
    parser.add_argument("--gender", choices=("female", "male", "neutral"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--addon-root", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


args = arguments()
addon_root = Path(args.addon_root).resolve()
if str(addon_root) not in sys.path:
    sys.path.insert(0, str(addon_root))

import smpl_acupoint_annotator as annotator

try:
    annotator.unregister()
except Exception:
    pass
annotator.register()

controls = None
if args.family == "SKEL":
    if args.gender == "neutral":
        raise RuntimeError("SKEL has no neutral model")
    import skel_blender_controls as controls

    try:
        controls.unregister()
    except Exception:
        pass
    controls.register()

scene = bpy.context.scene
if args.family == "SKEL":
    target = bpy.data.objects.get(f"SKEL-skin-{args.gender}")
else:
    target = next(
        (
            obj for obj in scene.objects
            if obj.type == "MESH" and (
                str(obj.get("body_model", "")).lower() == "smplx"
                or len(obj.data.vertices) == 10475
            )
        ),
        None,
    )
if target is None:
    raise RuntimeError(f"Could not find {args.family} annotation surface")

settings = scene.smpl_acupoint_settings
settings.target_mesh = target
settings.simple_ui = True
settings.workflow_mode = "DOCTOR_ATLAS" if args.family == "SKEL" else "RESEARCH"
settings.template_gender = args.gender
settings.template_id = (
    f"skel-{args.gender}-trunk-limb-v2.3"
    if args.family == "SKEL"
    else f"smplx-{args.gender}-research-v2.3"
)

scene["acupoint_atlas_family"] = args.family
scene["template_role"] = (
    "SKEL native skin trunk-limb doctor annotation template"
    if args.family == "SKEL"
    else "Independent SMPL-X full-body research template without SKEL overlay"
)
scene["medical_warning"] = (
    "Doctors determine clinical locations; SKEL skeleton is not patient CT ground truth."
)
scene["license_warning"] = "Licensed internal research asset; do not redistribute."

target["acupoint_template_target"] = True
target["acupoint_template_family"] = args.family
target["acupoint_template_id"] = settings.template_id
target["acupoint_canonical_shape_id"] = "shape-zero"
target["acupoint_canonical_pose_id"] = "template-default"

if args.family == "SKEL":
    scene["skel_gender"] = args.gender
    scene["skel_betas"] = [0.0] * 10
    scene["skel_pose_degrees"] = {
        field: 0.0 for field, _index, _label in controls.POSE_FIELDS
    }
    scene["skel_parameters_dirty"] = False
    skel_settings = scene.skel_controls
    skel_settings.betas = (0.0,) * 10
    skel_settings.height_shape = 0.0
    skel_settings.weight_shape = 0.0
    for field, _index, _label in controls.POSE_FIELDS:
        setattr(skel_settings, field, 0.0)
    skel_settings.show_skin = True
    skel_settings.show_skeleton = False
    skel_settings.show_joint_names = False
    controls._apply_visibility(scene)
    skeleton = bpy.data.objects.get(f"SKEL-skeleton-{args.gender}")
    if skeleton:
        skeleton.hide_select = True
    joints = bpy.data.collections.get("SKEL_关节")
    if joints:
        for joint in joints.objects:
            joint.hide_select = True

target["acupoint_template_topology_sha256"] = annotator._topology_signature(target)
target["acupoint_template_shape_sha256"] = annotator._shape_signature(target)
target["acupoint_template_pose_sha256"] = annotator._pose_signature(target)

bpy.ops.object.select_all(action="DESELECT")
target.hide_select = args.family == "SKEL"
target.select_set(True)
bpy.context.view_layer.objects.active = target

output = Path(args.output).resolve()
output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
print(
    f"V23_TEMPLATE_PREPARE=PASS family={args.family} gender={args.gender} "
    f"vertices={len(target.data.vertices)} polygons={len(target.data.polygons)} output={output}"
)
