"""Run with the bundled Blender 4.5 LTS against the legacy SMPL test scene."""

import json
import os
import sys

import bpy


ADDON_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_PARENT not in sys.path:
    sys.path.insert(0, ADDON_PARENT)

import smpl_acupoint_annotator as addon


def require(condition, message):
    if not condition:
        raise AssertionError(message)


try:
    addon.unregister()
except Exception:
    pass
addon.register()

scene = bpy.context.scene
target = bpy.data.objects.get("SMPL-mesh-female")
require(target is not None, "SMPL-mesh-female is missing")
scene.smpl_acupoint_settings.target_mesh = target

addon.clear_annotations(scene)
polygon = target.data.polygons[0]
require(len(polygon.vertices) == 3, "SMPL mesh must be triangulated")

item = addon.add_annotation_from_surface(
    scene,
    target,
    face_index=0,
    barycentric=(0.2, 0.3, 0.5),
    code="TEST-001",
    name_zh="非医学测试点",
    notes="automated test only",
    body_region="TORSO",
)
marker = bpy.data.objects.get(item.marker_name)
require(marker is not None, "marker was not created")
require(marker.empty_display_type == "PLAIN_AXES", "marker must use point-style axes")
require(abs(scene.smpl_acupoint_settings.marker_size - 0.005) < 1e-9, "legacy marker size was not migrated")
require(abs(marker.empty_display_size - 0.005) < 1e-9, "marker does not use migrated size")
require(marker.name == "非医学测试点（TEST-001）", "medical display label is incorrect")
item.name_zh = "更新后的测试点"
require(marker.name == "更新后的测试点（TEST-001）", "edited medical name did not refresh")
initial_location = marker.location.copy()

shape_keys = target.data.shape_keys.key_blocks
shape_key = shape_keys.get("Shape001") or shape_keys.get("Shape000")
require(shape_key is not None, "SMPL shape key is missing")
shape_key.value = 0.4
bpy.context.view_layer.update()
addon.refresh_scene_markers(scene)
deformed_location = marker.location.copy()
require((deformed_location - initial_location).length > 1e-8, "marker did not follow shape deformation")

output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_output")
os.makedirs(output_dir, exist_ok=True)
json_path = os.path.join(output_dir, "annotations.json")
count = addon.export_annotations(scene, json_path)
require(count == 1, "unexpected export count")
with open(json_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
require(payload["schema_version"] == addon.SCHEMA_VERSION, "schema mismatch")
require(payload["model"]["family"] == "SMPL", "SMPL model family not exported")
require(len(payload["model"]["topology_signature_sha256"]) == 64, "topology signature missing")
require(payload["annotations"][0]["body_region"] == "TORSO", "body region missing")
require(len(payload["annotations"][0]["barycentric"]) == 3, "invalid barycentric export")

addon.clear_annotations(scene)
imported, skipped = addon.import_annotations(scene, target, json_path)
require(imported == 1 and skipped == 0, "import failed")
imported_again, skipped_again = addon.import_annotations(scene, target, json_path)
require(imported_again == 0 and skipped_again == 1, "duplicate protection failed")

# v0.3 must reject loading a SMPL annotation on an unrelated topology.
wrong_mesh = bpy.data.meshes.new("wrong-topology")
wrong_mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
wrong_target = bpy.data.objects.new("wrong-topology", wrong_mesh)
bpy.context.scene.collection.objects.link(wrong_target)
try:
    addon.import_annotations(scene, wrong_target, json_path)
except ValueError as error:
    require("拓扑不兼容" in str(error), "wrong topology rejection message missing")
else:
    raise AssertionError("wrong topology import was not rejected")

print("SMPL_ACUPOINT_TEST=PASS")
print(f"ANNOTATIONS={len(scene.smpl_acupoint_annotations)}")
print(f"MARKER_MOVEMENT_M={(deformed_location - initial_location).length:.9f}")
print(f"JSON={json_path}")
