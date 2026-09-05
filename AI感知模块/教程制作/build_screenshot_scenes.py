"""Create deterministic, non-medical tutorial screenshot scenes in Blender."""

import argparse
import math
import os
import sys
from pathlib import Path

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--family", choices=("smplx", "skel"), required=True)
parser.add_argument("--gender", choices=("neutral", "female", "male"), required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

ai_root = Path(__file__).resolve().parents[1]
addon_parent = ai_root / "标注工具" / "blender_addons"
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))
import smpl_acupoint_annotator as annotator

try:
    annotator.unregister()
except Exception:
    pass
annotator.register()

scene = bpy.context.scene
target_name = (
    f"SMPLX-mesh-{args.gender}"
    if args.family == "smplx"
    else f"SKEL-skin-{args.gender}"
)
target = bpy.data.objects[target_name]
scene.smpl_acupoint_settings.target_mesh = target
scene.smpl_acupoint_settings.marker_size = 0.005
scene.smpl_acupoint_settings.surface_offset = 0.003
annotator.clear_annotations(scene)


def centroid(poly):
    return sum((target.data.vertices[i].co for i in poly.vertices), target.data.vertices[poly.vertices[0]].co * 0.0) / len(poly.vertices)


def closest_face(point):
    desired = target.data.vertices[0].co.copy()
    desired[:] = point
    return min(target.data.polygons, key=lambda poly: (centroid(poly) - desired).length_squared).index


if args.family == "smplx":
    points = (
        ("DEMO-01", "演示点一（非医学）", "HEAD_FACE", "MIDLINE", (0.0, -0.12, 0.23)),
        ("DEMO-02", "演示点二（非医学）", "TORSO", "LEFT", (-0.16, 0.13, -0.42)),
        ("DEMO-03", "演示点三（非医学）", "RIGHT_HAND", "RIGHT", (0.78, 0.02, -0.20)),
    )
else:
    # SKEL has no independent finger or facial articulation.  Use three torso
    # locations to demonstrate the same annotation mechanics without implying
    # that SKEL is suitable for detailed hand/face annotation.
    points = (
        ("DEMO-S1", "演示点一（非医学）", "TORSO", "MIDLINE", (0.0, 0.10, 0.40)),
        ("DEMO-S2", "演示点二（非医学）", "TORSO", "LEFT", (-0.12, 0.10, 0.15)),
        ("DEMO-S3", "演示点三（非医学）", "TORSO", "RIGHT", (0.12, 0.10, 0.00)),
    )

for code, name, region, side, point in points:
    face_index = closest_face(point)
    annotator.add_annotation_from_surface(
        scene,
        target,
        face_index,
        (1.0 / 3.0,) * 3,
        code=code,
        name_zh=name,
        meridian="教程演示区域",
        side=side,
        notes="仅演示软件操作，不代表医学穴位",
        body_region=region,
    )

bpy.context.view_layer.objects.active = target
target.select_set(True)
for obj in scene.objects:
    if obj != target:
        obj.select_set(False)

out = Path(args.output).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out), check_existing=False)
print(f"SCREENSHOT_SCENE_{args.family.upper()}=PASS")
for item in scene.smpl_acupoint_annotations:
    marker = bpy.data.objects[item.marker_name]
    print(item.code, item.face_index, tuple(round(value, 4) for value in marker.location))
