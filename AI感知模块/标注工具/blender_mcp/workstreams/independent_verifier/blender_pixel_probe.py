"""Independent pixel-center ray probe for the isolated RGB-D prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def _args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _first_rendered_hit(scene, depsgraph, origin: Vector, direction: Vector, ignored_objects: set[str]):
    travelled = 0.0
    current = origin.copy()
    for _ in range(32):
        hit, location, normal, face, obj, matrix = scene.ray_cast(
            depsgraph, current, direction, distance=1000.0 - travelled
        )
        if not hit:
            return False, None, None, None, None, None
        original = bpy.data.objects.get(obj.name) if obj else None
        excluded = obj is None or obj.name in ignored_objects or bool(original and original.hide_render)
        if not excluded:
            return hit, location, normal, face, obj, matrix
        step = max(1.0e-5, (location - current).length + 1.0e-5)
        travelled += step
        current = current + direction * step
    raise RuntimeError("Too many excluded ray hits")


def main() -> None:
    args = _args()
    metadata = _load(args.metadata)
    request = _load(args.requests)
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    intrinsics = metadata["camera"]["intrinsics"]
    fx, fy = float(intrinsics["fx"]), float(intrinsics["fy"])
    cx, cy = float(intrinsics["cx"]), float(intrinsics["cy"])
    world_to_cv = Matrix(metadata["camera"]["world_to_opencv_camera"])
    camera_to_world = world_to_cv.inverted()
    origin = camera_to_world.translation
    rotation = camera_to_world.to_3x3()
    ignored = set(str(name) for name in request.get("ignored_render_objects", []))
    results = []
    for item in request.get("pixels", []):
        u = float(item["column"]) + 0.5
        v = float(item["row"]) + 0.5
        direction_cv = Vector(((u - cx) / fx, (v - cy) / fy, 1.0))
        direction_world = (rotation @ direction_cv).normalized()
        hit, location, _normal, face, obj, _matrix = _first_rendered_hit(
            scene, depsgraph, origin, direction_world, ignored
        )
        result = {"request": item, "hit": bool(hit)}
        if hit:
            camera_hit = world_to_cv @ location.to_4d()
            result.update(
                {
                    "hit_object": obj.name,
                    "hit_face_index": int(face),
                    "hit_zc_m": float(camera_hit[2]),
                    "hit_world": list(location),
                }
            )
        results.append(result)
    output = {
        "schema": "independent-prototype-pixel-probe-v1",
        "blend_path": bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "ignored_render_objects": sorted(ignored),
        "results": results,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
