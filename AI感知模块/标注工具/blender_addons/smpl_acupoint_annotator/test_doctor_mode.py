"""Headless acceptance test for the constrained SMPL-X doctor workflow."""

import json
import os

import bpy
import smpl_acupoint_annotator as annotator


scene = bpy.context.scene
settings = scene.smpl_acupoint_settings
annotator._initialize_session(scene)
target = settings.target_mesh

assert annotator.bl_info["version"] == (0, 4, 0)
assert settings.workflow_mode == "DOCTOR_ATLAS"
assert target is not None
assert annotator._model_family(target) == "SMPL-X"
assert target.get("smplx_template_topology_sha256") == annotator._topology_signature(target)
assert settings.session_id == "TEST_SESSION_001"
assert settings.doctor_id == "TEST_DOCTOR"
assert settings.task_id == "TEST_TASK"
assert settings.template_gender in {"neutral", "female", "male"}

annotator.clear_annotations(scene)
samples = (
    ("GV14", "大椎", "MIDLINE", 100),
    ("BL23", "肾俞", "LEFT", 1000),
    ("BL23", "肾俞", "RIGHT", 2000),
)
for code, name, side, face_index in samples:
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

assert len(scene.smpl_acupoint_annotations) == 3
settings.draft_code = "BL23"
settings.draft_name_zh = "肾俞"
settings.draft_side = "LEFT"
try:
    annotator._validate_draft(scene)
except ValueError as error:
    assert "已经标注" in str(error)
else:
    raise AssertionError("Duplicate doctor point was not rejected")

shape_key = target.data.shape_keys.key_blocks.get("Shape001")
original_shape = shape_key.value
shape_key.value = 0.1
try:
    annotator._validate_scene(scene)
except ValueError as error:
    assert "体型" in str(error)
else:
    raise AssertionError("Doctor shape tampering was not rejected")
shape_key.value = original_shape

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
roundtrip_blend = os.path.join(output_root, "doctor_roundtrip.blend")
bpy.ops.wm.save_as_mainfile(filepath=roundtrip_blend, check_existing=False)
result = bpy.ops.smpl_acupoint.save_doctor_session("EXEC_DEFAULT")
assert "FINISHED" in result

formal_json = os.path.join(output_root, "TEST_SESSION_001_正式标注_最新.json")
autosave_json = os.path.join(output_root, "TEST_SESSION_001_自动保存_最新.json")
assert os.path.isfile(formal_json)
assert os.path.isfile(autosave_json)
with open(formal_json, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload["schema_version"] == "smpl-acupoint-annotation-v3"
assert payload["plugin_version"] == "0.4.0"
assert payload["session"]["doctor_id"] == "TEST_DOCTOR"
assert payload["session"]["task_id"] == "TEST_TASK"
assert len(payload["annotations"]) == 3
assert {item["point_id"] for item in payload["annotations"]} == {
    "GV14_MIDLINE", "BL23_LEFT", "BL23_RIGHT"
}
assert all("canonical_local_position_m" in item for item in payload["annotations"])

print("SMPL_ACUPOINT_DOCTOR_TEST=PASS")
print(f"DOCTOR_ROUNDTRIP_BLEND={roundtrip_blend}")
print(f"DOCTOR_FORMAL_JSON={formal_json}")
