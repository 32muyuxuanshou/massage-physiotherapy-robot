"""Headless acceptance test for a fixed, distributable SMPL-X Body template."""

import json
import os

import bpy
import smpl_acupoint_annotator as annotator


scene = bpy.context.scene
settings = scene.smpl_acupoint_settings
annotator._initialize_session(scene)
target = settings.target_mesh

assert settings.workflow_mode == "DOCTOR_ATLAS"
assert target is not None
assert target.get("smplx_distribution_profile") == "SMPL-X Body / CC BY 4.0"
names = [key.name for key in target.data.shape_keys.key_blocks]
assert not [name for name in names if name.startswith(("Shape", "Exp"))]
assert len([name for name in names if name.startswith("Pose")]) == 486

annotator.clear_annotations(scene)
for code, name, side, face_index in (
    ("GV14", "大椎", "MIDLINE", 100),
    ("BL23", "肾俞", "LEFT", 1000),
    ("BL23", "肾俞", "RIGHT", 2000),
):
    annotator.add_annotation_from_surface(
        scene,
        target,
        face_index,
        (0.2, 0.3, 0.5),
        code=code,
        name_zh=name,
        side=side,
        body_region="TORSO",
    )

armature = target.parent
bone = armature.pose.bones[0]
original_basis = bone.matrix_basis.copy()
bone.rotation_mode = "XYZ"
bone.rotation_euler.x += 0.1
try:
    annotator._validate_scene(scene)
except ValueError as error:
    assert "姿态" in str(error)
else:
    raise AssertionError("Doctor pose tampering was not rejected")
bone.matrix_basis = original_basis

output_root = os.environ["SMPL_ACUPOINT_EXPORT_ROOT"]
os.makedirs(output_root, exist_ok=True)
roundtrip_blend = os.path.join(output_root, "doctor_body_roundtrip.blend")
bpy.ops.wm.save_as_mainfile(filepath=roundtrip_blend, check_existing=False)
result = bpy.ops.smpl_acupoint.save_doctor_session("EXEC_DEFAULT")
assert "FINISHED" in result

formal_json = os.path.join(output_root, "TEST_BODY_SESSION_001_正式标注_最新.json")
with open(formal_json, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload["schema_version"] == "smpl-acupoint-annotation-v3"
assert len(payload["annotations"]) == 3
assert {item["point_id"] for item in payload["annotations"]} == {
    "GV14_MIDLINE",
    "BL23_LEFT",
    "BL23_RIGHT",
}

print("SMPL_ACUPOINT_DOCTOR_BODY_TEST=PASS")
print(f"DOCTOR_BODY_ROUNDTRIP_BLEND={roundtrip_blend}")
