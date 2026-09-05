from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view


def args_after_dash() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-name", required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(args_after_dash())

    scene = bpy.context.scene
    camera = scene.camera
    obj = bpy.data.objects.get(args.mesh_name)
    if camera is None or camera.type != "CAMERA" or obj is None or obj.type != "MESH":
        raise RuntimeError("Active camera or target mesh is missing")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        projected = []
        for vertex in mesh.vertices:
            world = evaluated.matrix_world @ vertex.co
            ndc = world_to_camera_view(scene, camera, world)
            if not all(math.isfinite(float(value)) for value in (ndc.x, ndc.y, ndc.z)) or ndc.z <= 0:
                continue
            projected.append((float(ndc.x) * args.width, (1.0 - float(ndc.y)) * args.height))
    finally:
        evaluated.to_mesh_clear()

    if not projected:
        raise RuntimeError("No target vertices project in front of camera")
    values_u = [value[0] for value in projected]
    values_v = [value[1] for value in projected]
    min_u, max_u = min(values_u), max(values_u)
    min_v, max_v = min(values_v), max(values_v)
    full_width = max(max_u - min_u, 0.0)
    full_height = max(max_v - min_v, 0.0)
    full_area = full_width * full_height
    clipped_min_u, clipped_max_u = max(0.0, min_u), min(float(args.width), max_u)
    clipped_min_v, clipped_max_v = max(0.0, min_v), min(float(args.height), max_v)
    intersection_area = max(0.0, clipped_max_u - clipped_min_u) * max(0.0, clipped_max_v - clipped_min_v)
    in_frame = sum(0.0 <= u < args.width and 0.0 <= v < args.height for u, v in projected)
    payload = {
        "schema": "truncation-severity-projection-v2",
        "passed": True,
        "mesh_name": args.mesh_name,
        "vertex_count_in_front": len(projected),
        "projected_vertex_in_frame_count": in_frame,
        "projected_vertex_in_frame_fraction": in_frame / len(projected),
        "full_projected_bbox_edge_coordinates": {"min_u": min_u, "max_u": max_u, "min_v": min_v, "max_v": max_v},
        "full_projected_bbox_area_px2": full_area,
        "bbox_intersection_with_frame_area_px2": intersection_area,
        "bbox_area_truncation_fraction": 1.0 - intersection_area / full_area if full_area > 0 else None,
        "clipped_edges": {
            "LEFT": min_u < 0.0,
            "RIGHT": max_u > args.width,
            "TOP": min_v < 0.0,
            "BOTTOM": max_v > args.height,
        },
        "resolution": [args.width, args.height],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_TRUNCATION_SEVERITY=PASS")


if __name__ == "__main__":
    main()
