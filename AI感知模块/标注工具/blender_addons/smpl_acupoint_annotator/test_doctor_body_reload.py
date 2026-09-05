"""Verify durable bindings after reopening a fixed SMPL-X Body work copy."""

import json
import os

import bpy
import smpl_acupoint_annotator as annotator


scene = bpy.context.scene
annotator._initialize_session(scene)
assert len(scene.smpl_acupoint_annotations) == 3
target = scene.smpl_acupoint_settings.target_mesh
assert target is not None
assert target.get("smplx_distribution_profile") == "SMPL-X Body / CC BY 4.0"

json_path = os.path.join(
    os.environ["SMPL_ACUPOINT_EXPORT_ROOT"],
    "TEST_BODY_SESSION_001_正式标注_最新.json",
)
with open(json_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
expected = {
    item["id"]: (item["face_index"], tuple(item["barycentric"]))
    for item in payload["annotations"]
}
for item in scene.smpl_acupoint_annotations:
    face_index, barycentric = expected[item.annotation_id]
    assert item.face_index == face_index
    assert max(abs(a - b) for a, b in zip(item.barycentric, barycentric)) < 1e-7
    point, normal, _ = annotator._surface_sample(target, item.face_index, item.barycentric)
    assert point.length > 0.0
    assert abs(normal.length - 1.0) < 1e-5

print("SMPL_ACUPOINT_DOCTOR_BODY_RELOAD_TEST=PASS")
