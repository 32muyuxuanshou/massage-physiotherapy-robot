"""Small headless acceptance check for one locally generated doctor template."""

import argparse
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--family", choices=("SMPL-X", "SKEL"), required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
if args.family == "SMPL-X":
    candidates = [obj for obj in meshes if len(obj.data.vertices) == 10475]
else:
    candidates = [obj for obj in meshes if obj.get("body_model") == "skel" and obj.get("skel_role") == "skin"]
if len(candidates) != 1:
    raise RuntimeError(f"Expected one {args.family} skin mesh, got {len(candidates)}")
if not hasattr(bpy.context.scene, "smpl_acupoint_settings"):
    raise RuntimeError("Annotation add-on is not active")
if args.family == "SMPL-X":
    import smpl_acupoint_annotator as annotator

    target = candidates[0]
    if bpy.context.scene.smpl_acupoint_settings.workflow_mode != "DOCTOR_ATLAS":
        raise RuntimeError("SMPL-X template is not locked to doctor Atlas mode")
    if not target.get("smplx_template_target", False):
        raise RuntimeError("SMPL-X template target identity is missing")
    if target.get("smplx_template_topology_sha256") != annotator._topology_signature(target):
        raise RuntimeError("SMPL-X template topology signature is invalid")
    if target.get("smplx_template_shape_sha256") != annotator._shape_signature(target):
        raise RuntimeError("SMPL-X template shape signature is invalid")
    if target.get("smplx_template_pose_sha256") != annotator._pose_signature(target):
        raise RuntimeError("SMPL-X template pose signature is invalid")
print(f"DOCTOR_TEMPLATE_VERIFY=PASS family={args.family}")
