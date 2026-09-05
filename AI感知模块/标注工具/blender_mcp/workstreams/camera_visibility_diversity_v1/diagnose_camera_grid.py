from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args_after_dash() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--core-parent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(args_after_dash())
    sys.path.insert(0, str(args.core_parent))
    from training_export_core.surface_binding import sample_surface_binding
    from training_export_core.visibility import evaluate_visibility

    fixture = json.loads(args.fixture.read_text(encoding="utf-8-sig"))
    scene = bpy.context.scene
    camera = scene.camera
    skin = bpy.data.objects["SKEL-skin-female"]
    target = Vector((0.0, -0.2, 0.2))
    positions = []
    for side in (1.0, -1.0):
        for x_abs in (0.8, 1.1, 1.4, 1.7, 2.0):
            for z in (0.65, 0.9, 1.15, 1.4, 1.7, 2.0):
                positions.append((side * x_abs, -0.2, z))
    rows = []
    for location_values in positions:
        location = Vector(location_values)
        camera.location = location
        camera.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = 35.0
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        reasons = []
        for anchor in fixture["anchors"]:
            surface = sample_surface_binding(
                skin, anchor["face_index"], anchor["barycentric"], depsgraph=depsgraph,
                expected_vertex_indices=anchor["vertex_indices"],
            )
            visibility = evaluate_visibility(
                scene=scene, depsgraph=depsgraph, camera=camera, target_object=skin,
                point_world=Vector(surface.xyz_world_m), world_normal=Vector(surface.world_normal),
                width=1280, height=1024,
            )
            reasons.append(visibility.visibility_reason)
        counts = {reason: reasons.count(reason) for reason in sorted(set(reasons))}
        rows.append({"location_world_m": list(location_values), "reason_counts": counts})
    rows.sort(key=lambda item: (item["reason_counts"].get("SELF_OCCLUDED", 0), item["reason_counts"].get("VISIBLE", 0)), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "camera-grid-diagnostic-v1", "lens_mm": 35.0, "target_world_m": list(target), "candidates": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_CAMERA_GRID_DIAGNOSTIC=PASS")


if __name__ == "__main__":
    main()
