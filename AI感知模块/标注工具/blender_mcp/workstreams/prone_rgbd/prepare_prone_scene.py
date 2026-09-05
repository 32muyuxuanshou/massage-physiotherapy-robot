"""Create a frozen, replayable prone-back SKEL engineering scene.

The canonical Blend is opened read-only by the orchestrator.  This script applies
a rigid prone transform only in the new snapshot, adds a bed/camera/lights, and
saves that independent snapshot.  It does not alter shape, topology, or Atlas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SKIN_NAME = "SKEL-skin-female"
SKELETON_NAME = "SKEL-skeleton-female"
CAMERA_NAME = "ACU_PRONE_BACK_CAMERA"
BED_NAME = "ACU_PRONE_BED"
RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "CURVES"}


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--native-pose-dir", type=Path)
    parser.add_argument("--pose-profile", type=Path)
    parser.add_argument("--fixed-scene-contract", type=Path)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.55):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def _read_obj_vertices(path: Path) -> list[tuple[float, float, float]]:
    vertices = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                values = line.split()
                vertices.append((float(values[1]), float(values[2]), float(values[3])))
    return vertices


def _replace_vertices(obj, path: Path) -> None:
    vertices = _read_obj_vertices(path)
    if len(vertices) != len(obj.data.vertices):
        raise RuntimeError(f"vertex count mismatch for {obj.name}: {len(vertices)} != {len(obj.data.vertices)}")
    for vertex, coordinate in zip(obj.data.vertices, vertices):
        vertex.co = coordinate
    obj.data.update()


def _load_native_pose(scene, skin, pose_dir: Path) -> dict:
    skin_path = pose_dir / "skin_female.obj"
    skeleton_path = pose_dir / "skeleton_female.obj"
    joints_path = pose_dir / "joints_female.json"
    for required in (skin_path, skeleton_path, joints_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    _replace_vertices(skin, skin_path)
    skeleton = bpy.data.objects.get(SKELETON_NAME)
    if skeleton is None or skeleton.type != "MESH":
        raise RuntimeError(f"missing {SKELETON_NAME}")
    _replace_vertices(skeleton, skeleton_path)
    joints = json.loads(joints_path.read_text(encoding="utf-8-sig"))
    for name, coordinate in zip(joints["joint_names"], joints["joints"]):
        marker = bpy.data.objects.get(f"SKEL-joint-{name}")
        if marker is not None:
            marker.location = coordinate
    scene["skel_native_pose_output_dir"] = str(pose_dir.resolve())
    return {
        "skin_obj_sha256": _sha256(skin_path),
        "skeleton_obj_sha256": _sha256(skeleton_path),
        "joints_json_sha256": _sha256(joints_path),
    }


def _evaluated_world_bounds(target) -> tuple[Vector, Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()
    return (
        Vector(tuple(min(float(point[i]) for point in points) for i in range(3))),
        Vector(tuple(max(float(point[i]) for point in points) for i in range(3))),
    )


def _apply_prone_transform(scene, skin, fixed_translation_z_m: float | None = None) -> Matrix:
    # Upright SKEL faces -Y and has its back toward +Y.  +90 degrees about X
    # maps back to +Z; the following 180-degree Z turn puts the head at image top.
    rotation = Matrix.Rotation(math.radians(180.0), 4, "Z") @ Matrix.Rotation(math.radians(90.0), 4, "X")
    if fixed_translation_z_m is None:
        rotated_points = [rotation @ (skin.matrix_world @ Vector(corner)) for corner in skin.bound_box]
        rotated_min_z = min(float(point.z) for point in rotated_points)
        clearance_m = 0.008
        translation_z = -rotated_min_z + clearance_m
    else:
        translation_z = float(fixed_translation_z_m)
    transform = Matrix.Translation((0.0, 0.0, translation_z)) @ rotation
    for obj in scene.objects:
        if obj.name.startswith("SKEL-"):
            obj.matrix_world = transform @ obj.matrix_world
    bpy.context.view_layer.update()
    return transform


def _add_bed(scene, body_min: Vector, body_max: Vector, contract: dict | None = None):
    if contract:
        width, length, thickness = (float(value) for value in contract["bed_dimensions_m"])
        center = Vector(tuple(float(value) for value in contract["bed_location_world_m"]))
    else:
        width = max(2.0, float(body_max.x - body_min.x) + 0.28)
        length = max(2.05, float(body_max.y - body_min.y) + 0.35)
        thickness = 0.12
        center = Vector(((body_min.x + body_max.x) * 0.5, (body_min.y + body_max.y) * 0.5, -thickness * 0.5))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    bed = bpy.context.object
    bed.name = BED_NAME
    bed.dimensions = (width, length, thickness)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bed.data.materials.append(_material("ACU_BED_MATERIAL", (0.08, 0.20, 0.24, 1.0), 0.72))
    bed["training_role"] = "bed_first_surface_non_skin"
    return bed


def _add_camera(scene, body_min: Vector, body_max: Vector, contract: dict | None = None):
    center = (body_min + body_max) * 0.5
    data = bpy.data.cameras.new(f"{CAMERA_NAME}_DATA")
    data.type = "PERSP"
    data.lens = float(contract["camera_lens_mm"]) if contract else 42.0
    data.sensor_width = 36.0
    data.sensor_height = 24.0
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = float(contract["camera_clip_start_m"]) if contract else 0.01
    # Keep the already-validated far plane used by the canonical RGB-D gate.
    # A short 20 m far plane exposed Eevee Z-pass quantization close to clip_end.
    data.clip_end = float(contract["camera_clip_end_m"]) if contract else 100.0
    camera = bpy.data.objects.new(CAMERA_NAME, data)
    scene.collection.objects.link(camera)
    if contract:
        camera.matrix_world = Matrix(contract["camera_matrix_world"])
        look_at = Vector((camera.location.x, camera.location.y, 0.10))
    else:
        camera.location = Vector((center.x, center.y, body_max.z + 2.60))
        look_at = Vector((center.x, center.y, max(0.06, body_max.z * 0.45)))
        camera.rotation_euler = (look_at - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera["acupoint_mcp_camera"] = True
    camera["synthetic_only"] = True
    scene.camera = camera
    return camera, look_at


def _add_area(scene, name: str, location: Vector, energy: float, size: float, look_at: Vector):
    data = bpy.data.lights.new(f"{name}_DATA", type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (look_at - location).to_track_quat("-Z", "Y").to_euler()
    return light


def main() -> None:
    args = _arguments()
    if not (128 <= args.width <= 4096 and 128 <= args.height <= 4096):
        raise ValueError("resolution must be within 128..4096")
    scene = bpy.context.scene
    skin = bpy.data.objects.get(SKIN_NAME)
    if skin is None or skin.type != "MESH":
        raise RuntimeError(f"missing canonical target {SKIN_NAME}")

    native_pose_hashes = None
    pose_profile = None
    if args.native_pose_dir is not None:
        native_pose_hashes = _load_native_pose(scene, skin, args.native_pose_dir.resolve())
        if args.pose_profile is None or not args.pose_profile.is_file():
            raise ValueError("--pose-profile is required with --native-pose-dir")
        pose_profile = json.loads(args.pose_profile.read_text(encoding="utf-8-sig"))
        scene["skel_pose_degrees"] = pose_profile.get("pose_degrees", {})
        scene["skel_betas"] = [float(value) for value in pose_profile.get("betas", [0.0] * 10)]
        scene["skel_pose_profile_sha256"] = _sha256(args.pose_profile)

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.frame_set(1)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ACU_PRONE_WORLD")
    scene.world.color = (0.025, 0.025, 0.025)

    fixed_contract = None
    if args.fixed_scene_contract is not None:
        fixed_contract = json.loads(args.fixed_scene_contract.read_text(encoding="utf-8-sig"))
    prone_transform = _apply_prone_transform(
        scene,
        skin,
        float(fixed_contract["prone_translation_z_m"]) if fixed_contract and "prone_translation_z_m" in fixed_contract else None,
    )
    body_min, body_max = _evaluated_world_bounds(skin)
    bed = _add_bed(scene, body_min, body_max, fixed_contract)
    camera, look_at = _add_camera(scene, body_min, body_max, fixed_contract)
    _add_area(scene, "ACU_PRONE_KEY", camera.location + Vector((-0.65, -0.25, 0.10)), 90.0, 2.2, look_at)
    _add_area(scene, "ACU_PRONE_FILL", Vector((0.75, body_max.y + 0.25, 1.35)), 45.0, 1.8, look_at)

    # Snapshot-only neutral materials keep the engineering render readable and
    # do not touch the canonical file on disk.
    skin.data.materials.clear()
    skin.data.materials.append(_material("ACU_SKIN_MATERIAL", (0.30, 0.10, 0.055, 1.0), 0.62))
    for obj in scene.objects:
        if obj.type in RENDERABLE_TYPES:
            obj.hide_render = obj not in {skin, bed}
    skin.hide_render = False
    bed.hide_render = False
    skeleton = bpy.data.objects.get(SKELETON_NAME)
    if skeleton is not None:
        skeleton.hide_render = True

    settings = getattr(scene, "smpl_acupoint_settings", None)
    if settings is not None:
        settings.target_mesh = skin
    scene["acu_training_scene_contract"] = (
        "SKEL_NATIVE_POSE_PRONE_BACK_RGBD_ENGINEERING_V1"
        if args.native_pose_dir is not None
        else "SKEL_PRONE_BACK_RGBD_ENGINEERING_V1"
    )
    scene["acu_medical_truth"] = False
    scene["acu_prone_definition"] = "rigid +90deg X then 180deg Z from canonical; back +Z; face toward bed; head at image top"
    scene["acu_bed_top_z_m"] = 0.0
    scene["acu_body_clearance_m"] = float(body_min.z)
    bpy.context.view_layer.update()

    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.snapshot), check_existing=False)
    result = {
        "passed": True,
        "medical_truth": False,
        "snapshot": str(args.snapshot),
        "snapshot_sha256": _sha256(args.snapshot),
        "canonical_source_was_overwritten": False,
        "scene_contract": scene["acu_training_scene_contract"],
        "target": skin.name,
        "camera": camera.name,
        "bed": bed.name,
        "resolution": [args.width, args.height],
        "body_bounds_world_m": {"min": list(body_min), "max": list(body_max)},
        "prone_transform": [[float(value) for value in row] for row in prone_transform],
        "pose_scope": (
            "native SKEL articulated pose plus rigid prone transform"
            if args.native_pose_dir is not None
            else "rigid prone transform; canonical SKEL shape and articulated pose unchanged"
        ),
        "native_pose_hashes": native_pose_hashes,
        "pose_profile": pose_profile,
        "fixed_scene_contract": fixed_contract,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_PREPARE_PRONE_SCENE=PASS")


if __name__ == "__main__":
    main()
