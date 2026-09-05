from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def args_after_dash() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def cube_mesh(name: str, dimensions: list[float]):
    hx, hy, hz = (float(value) * 0.5 for value in dimensions)
    vertices = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--save", required=True, type=Path)
    args = parser.parse_args(args_after_dash())
    config = read_json(args.config)
    scenario = next(item for item in config["scenarios"] if item["camera_id"] == args.camera_id)
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Active Blender Camera is missing")

    for obj in list(bpy.data.objects):
        if obj.name.startswith("__ACU_EXTERNAL_OCCLUDER__"):
            bpy.data.objects.remove(obj, do_unlink=True)

    if "matrix_world" in scenario:
        camera.matrix_world = Matrix(scenario["matrix_world"])
    else:
        location = Vector(scenario["location_world_m"])
        target = Vector(scenario["target_world_m"])
        camera.location = location
        camera.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = float(scenario.get("lens_mm", camera.data.lens))
    camera.data.clip_start = min(float(camera.data.clip_start), 0.01)
    camera.data.clip_end = max(float(camera.data.clip_end), 10.0)

    occluder_name = None
    if scenario.get("occluder"):
        spec = scenario["occluder"]
        occluder = bpy.data.objects.new(spec["name"], cube_mesh(spec["name"], spec["dimensions_m"]))
        scene.collection.objects.link(occluder)
        occluder.location = Vector(spec["location_world_m"])
        occluder["acu_external_occluder"] = True
        material = bpy.data.materials.new("ACU_EXTERNAL_OCCLUDER_MATERIAL")
        material.diffuse_color = (0.08, 0.22, 0.55, 1.0)
        material.roughness = 0.7
        occluder.data.materials.append(material)
        occluder_name = occluder.name

    scene["acu_camera_scenario_id"] = args.camera_id
    scene["acu_camera_scenario_config"] = str(args.config)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.save), check_existing=False)
    result = {
        "passed": True,
        "camera_id": args.camera_id,
        "camera_name": camera.name,
        "camera_matrix_world": [[float(value) for value in row] for row in camera.matrix_world],
        "lens_mm": float(camera.data.lens),
        "occluder_name": occluder_name,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_APPLY_CAMERA_SCENARIO=PASS")


if __name__ == "__main__":
    main()
