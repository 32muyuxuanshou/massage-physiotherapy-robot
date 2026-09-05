"""Tutorial-level, non-interactive acceptance test for SMPL-X and SKEL templates.

Run inside Blender with one of the doctor templates open.  All generated files
are written to a caller-provided QA directory; the source template is never
saved or overwritten.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--family", choices=("smplx", "skel"), required=True)
parser.add_argument("--gender", choices=("female", "male", "neutral"), required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

output_dir = Path(args.output_dir).resolve()
output_dir.mkdir(parents=True, exist_ok=True)

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
target = bpy.data.objects.get(target_name)
assert target is not None and target.type == "MESH", target_name
scene.smpl_acupoint_settings.target_mesh = target
annotator.clear_annotations(scene)

samples = (
    ("DEMO-A", "演示点A（非医学）", "HEAD_FACE", "MIDLINE", 0),
    ("DEMO-B", "演示点B（非医学）", "TORSO", "LEFT", 100),
    ("DEMO-C", "演示点C（非医学）", "LEFT_HAND", "RIGHT", 1000),
)
for code, name, region, side, face_index in samples:
    assert face_index < len(target.data.polygons)
    annotator.add_annotation_from_surface(
        scene,
        target,
        face_index,
        (0.2, 0.3, 0.5),
        code=code,
        name_zh=name,
        meridian="教程验收区域",
        side=side,
        notes="仅用于软件验收，不是医学穴位",
        body_region=region,
    )

assert len(scene.smpl_acupoint_annotations) == 3
second = scene.smpl_acupoint_annotations[1]
second.name_zh = "演示点B-已修改（非医学）"
second.side = "RIGHT"
marker = bpy.data.objects.get(second.marker_name)
assert marker is not None
assert "演示点B-已修改" in marker.name and "右" in marker.name

before_pose = [
    bpy.data.objects[item.marker_name].location.copy()
    for item in scene.smpl_acupoint_annotations
]
if args.family == "smplx":
    settings = scene.smpl_acupoint_settings
    settings.left_shoulder_z = 18.0
    settings.left_elbow_x = 22.0
    settings.jaw_x = 8.0
    shape_key = target.data.shape_keys.key_blocks.get("Shape001")
    assert shape_key is not None
    shape_key.value = 0.15
    bpy.context.view_layer.update()
    annotator.refresh_scene_markers(scene)
else:
    skel_parent = ai_root / "模型资源" / "SKEL" / "blender_addons"
    if str(skel_parent) not in sys.path:
        sys.path.insert(0, str(skel_parent))
    import skel_blender_controls as controls

    try:
        controls.unregister()
    except Exception:
        pass
    controls.register()
    scene.skel_controls.lumbar_bending = 6.0
    scene.skel_controls.thorax_twist = 4.0
    scene.skel_controls.betas = (0.15, -0.10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    result = bpy.ops.skel.update_skin("EXEC_DEFAULT")
    assert "FINISHED" in result
    annotator.refresh_scene_markers(scene)

after_pose = [
    bpy.data.objects[item.marker_name].location.copy()
    for item in scene.smpl_acupoint_annotations
]
assert any((after - before).length > 1e-8 for before, after in zip(before_pose, after_pose))

json_path = output_dir / f"{args.family}_{args.gender}_three_demo_points.json"
assert annotator.export_annotations(scene, str(json_path)) == 3
with json_path.open("r", encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload["schema_version"] == annotator.SCHEMA_VERSION
assert len(payload["annotations"]) == 3
assert payload["annotations"][1]["name_zh"] == "演示点B-已修改（非医学）"
assert payload["annotations"][1]["side"] == "RIGHT"
assert all(len(item["barycentric"]) == 3 for item in payload["annotations"])
assert len(payload["model"]["topology_signature_sha256"]) == 64

annotator.clear_annotations(scene)
assert len(scene.smpl_acupoint_annotations) == 0
imported, skipped = annotator.import_annotations(scene, target, str(json_path))
assert (imported, skipped) == (3, 0)
imported, skipped = annotator.import_annotations(scene, target, str(json_path))
assert (imported, skipped) == (0, 3)

wrong_mesh = bpy.data.meshes.new("QA-wrong-topology")
wrong_mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
wrong_target = bpy.data.objects.new("QA-wrong-topology", wrong_mesh)
scene.collection.objects.link(wrong_target)
try:
    annotator.import_annotations(scene, wrong_target, str(json_path))
except ValueError as error:
    assert "拓扑不兼容" in str(error)
else:
    raise AssertionError("wrong topology import was not rejected")

blend_path = output_dir / f"{args.family}_{args.gender}_qa_saved_copy.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
assert blend_path.exists() and blend_path.stat().st_size > 0

print(f"TUTORIAL_WORKFLOW_{args.family.upper()}_{args.gender.upper()}=PASS")
print(f"ANNOTATIONS={len(scene.smpl_acupoint_annotations)}")
print(f"JSON={json_path}")
print(f"BLEND_COPY={blend_path}")
