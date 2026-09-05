"""Create a replayable SKEL RGB-D verification scene without saving the canonical Blend."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SKIN_NAME = "SKEL-skin-female"
CAMERA_NAME = "ACU_TRAIN_CAMERA_TEST"
POINT = {
    "point_id": "11_MIDLINE",
    "face_index": 13745,
    "vertex_indices": [6332, 3506, 6498],
    "barycentric": [0.38897332549095154, 0.5540136098861694, 0.05701303854584694],
}
WORLD_TO_BLENDER_CAMERA = Matrix(
    (
        (1.0, -0.0, 0.0, -0.000365525484085083),
        (-0.0, -1.6292068494294654e-07, 1.0, 0.29153555631637573),
        (0.0, -1.0, -1.6292068494294654e-07, -3.1974761486053467),
        (-0.0, 0.0, -0.0, 1.0),
    )
)
RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "CURVES"}


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--occluded", action="store_true")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _material(name: str, rgba: tuple[float, float, float, float]):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.5
    return material


def _surface_point(target) -> Vector:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        polygon = mesh.polygons[POINT["face_index"]]
        vertices = [int(value) for value in polygon.vertices]
        if vertices != POINT["vertex_indices"]:
            raise RuntimeError(f"Frozen topology mismatch: {vertices} != {POINT['vertex_indices']}")
        local = Vector((0.0, 0.0, 0.0))
        for weight, vertex_index in zip(POINT["barycentric"], vertices):
            local += float(weight) * mesh.vertices[vertex_index].co
        return evaluated.matrix_world @ local
    finally:
        evaluated.to_mesh_clear()


def _add_camera(scene):
    data = bpy.data.cameras.new(f"{CAMERA_NAME}_DATA")
    data.type = "PERSP"
    data.lens = 55.0
    data.sensor_width = 36.0
    data.sensor_height = 24.0
    data.sensor_fit = "HORIZONTAL"
    data.shift_x = 0.0
    data.shift_y = 0.0
    data.clip_start = 0.01
    data.clip_end = 100.0
    camera = bpy.data.objects.new(CAMERA_NAME, data)
    scene.collection.objects.link(camera)
    camera.matrix_world = WORLD_TO_BLENDER_CAMERA.inverted()
    camera["acupoint_mcp_camera"] = True
    scene.camera = camera
    return camera


def _add_light(scene, camera):
    data = bpy.data.lights.new("ACU_TRAIN_AREA_DATA", type="AREA")
    data.energy = 1200.0
    data.shape = "DISK"
    data.size = 4.0
    light = bpy.data.objects.new("ACU_TRAIN_AREA", data)
    scene.collection.objects.link(light)
    light.location = camera.location
    return light


def _add_occluder(scene, camera, target_world: Vector):
    target_camera = camera.matrix_world.inverted() @ target_world
    center_camera = target_camera * 0.5
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    occluder = bpy.context.object
    occluder.name = "__RGBD_EXTERNAL_OCCLUDER__"
    occluder.matrix_world = (
        camera.matrix_world
        @ Matrix.Translation(center_camera)
        @ Matrix.Diagonal((0.24, 0.24, 0.04, 1.0))
    )
    occluder.data.materials.append(_material("ACU_OCCLUDER_RED", (0.8, 0.01, 0.01, 1.0)))
    occluder.hide_render = False
    return occluder


def main() -> None:
    args = _arguments()
    if not (128 <= args.width <= 4096 and 128 <= args.height <= 4096):
        raise ValueError("resolution must be within 128..4096")
    scene = bpy.context.scene
    skin = bpy.data.objects.get(SKIN_NAME)
    if skin is None or skin.type != "MESH":
        raise RuntimeError(f"Missing canonical target {SKIN_NAME}")

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.frame_set(1)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ACU_TRAIN_WORLD")
    scene.world.color = (0.025, 0.025, 0.025)

    for obj in scene.objects:
        if obj.type in RENDERABLE_TYPES:
            obj.hide_render = obj != skin
    skin.hide_render = False
    bpy.context.view_layer.objects.active = skin
    skin.select_set(True)
    settings = getattr(scene, "smpl_acupoint_settings", None)
    if settings is not None:
        settings.target_mesh = skin

    camera = _add_camera(scene)
    _add_light(scene, camera)
    occluder = _add_occluder(scene, camera, _surface_point(skin)) if args.occluded else None
    scene["acu_training_scene_contract"] = "SKEL_CANONICAL_RGBD_SINGLE_POINT_V1"
    scene["acu_medical_truth"] = False
    scene["acu_external_occlusion_diagnostic"] = bool(args.occluded)
    bpy.context.view_layer.update()

    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.snapshot), check_existing=False)
    result = {
        "passed": True,
        "snapshot": str(args.snapshot),
        "snapshot_sha256": _sha256(args.snapshot),
        "blender_dirty_after_save": bool(bpy.data.is_dirty),
        "canonical_source_was_overwritten": False,
        "scene": scene.name,
        "target": skin.name,
        "camera": camera.name,
        "resolution": [args.width, args.height],
        "occluded": bool(args.occluded),
        "occluder": occluder.name if occluder else None,
        "medical_truth": False,
    }
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ACU_PREPARE_INTEGRATION_SCENE=PASS")


if __name__ == "__main__":
    main()
