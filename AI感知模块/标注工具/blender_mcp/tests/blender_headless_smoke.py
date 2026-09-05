"""Headless smoke test run by the portable Blender executable."""

from __future__ import annotations

import json
import os

import bpy
import acupoint_blender_mcp_bridge as bridge


atlas_path = os.environ["ACUPOINT_MCP_TEST_ATLAS"]
output_dir = os.environ["ACUPOINT_MCP_TEST_OUTPUT"]

status = bridge.command_status({})
validation = bridge.command_validate_atlas({"atlas_path": atlas_path})
assert validation["valid"], validation
point = bridge.command_get_acupoint_3d(
    {"atlas_path": atlas_path, "point_id": "11_MIDLINE"}
)
assert point["face_index"] == 13745, point

camera = bridge.command_set_camera_view(
    {"preset": "front", "distance_scale": 1.0, "focal_length_mm": 50.0}
)
sample = bridge.command_export_training_sample(
    {
        "atlas_path": atlas_path,
        "output_dir": output_dir,
        "point_ids": ["11_MIDLINE", "2_MIDLINE", "3_MIDLINE"],
        "camera_name": camera["camera"],
        "width": 512,
        "height": 512,
    }
)

print(
    "ACUPOINT_MCP_SMOKE="
    + json.dumps(
        {
            "status": status,
            "validation": validation,
            "point": point,
            "camera": camera,
            "sample": sample,
            "blend_dirty": bpy.data.is_dirty,
        },
        ensure_ascii=False,
    )
)

