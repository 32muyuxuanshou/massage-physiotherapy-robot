"""Legacy RGB-only/v1 delivery fixture; not part of the current RGB-D gate."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy
import acupoint_blender_mcp_bridge as bridge


atlas_path = os.environ["ACU_DELIVERY_ATLAS"]
sample_dir = os.environ["ACU_DELIVERY_SAMPLE_DIR"]
result_path = Path(os.environ["ACU_DELIVERY_EXPORT_RESULT"])

validation = bridge.command_validate_atlas({"atlas_path": atlas_path})
assert validation["valid"], validation
camera = bridge.command_set_camera_view(
    {
        "preset": "front",
        "distance_scale": 1.0,
        "focal_length_mm": 55.0,
        "camera_name": "ACU_TRAIN_CAMERA_TEST",
    }
)
assert camera["camera"] == "ACU_TRAIN_CAMERA_TEST", camera
assert abs(bpy.data.objects[camera["camera"]].data.sensor_width - 36.0) < 1e-12

sample = bridge.command_export_training_sample(
    {
        "atlas_path": atlas_path,
        "output_dir": sample_dir,
        "point_ids": ["11_MIDLINE"],
        "camera_name": camera["camera"],
        "width": 1024,
        "height": 1024,
    }
)
assert sample["point_count"] == 1, sample
assert sample["visible_count"] == 1, sample

result = {
    "validation": validation,
    "camera": camera,
    "sample": sample,
    "blend_path": bpy.data.filepath,
    "blend_dirty_after_unsaved_camera": bpy.data.is_dirty,
    "blend_saved_by_test": False,
}
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("ACU_DELIVERY_EXPORT=PASS")
