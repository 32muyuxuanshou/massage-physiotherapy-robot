"""Reopen verification for QA copies created by qa_workflow_test.py."""

import sys
from pathlib import Path

import bpy


ai_root = Path(__file__).resolve().parents[1]
addon_parent = ai_root / "标注工具" / "blender_addons"
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))
import smpl_acupoint_annotator as annotator

# Background QA does not load the doctor's isolated Blender user resources.
# Registering the same add-on class definitions materializes the saved RNA data.
try:
    annotator.unregister()
except Exception:
    pass
annotator.register()

scene = bpy.context.scene
assert hasattr(scene, "smpl_acupoint_annotations")
assert len(scene.smpl_acupoint_annotations) == 3
for item in scene.smpl_acupoint_annotations:
    marker = bpy.data.objects.get(item.marker_name)
    assert marker is not None
    assert marker.empty_display_type == "PLAIN_AXES"
    assert marker.show_name is True
print("TUTORIAL_REOPEN=PASS")
print(f"ANNOTATIONS={len(scene.smpl_acupoint_annotations)}")
