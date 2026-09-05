"""Isolated RGB-D/visible-skin-mask prototype for Blender 4.5.

This module deliberately has no dependency on the production annotator, MCP bridge,
or MCP server.  It is an experimental reference implementation only.
"""

from __future__ import annotations

import glob
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Matrix


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_jsonable) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_image(path: Path) -> np.ndarray:
    image_input = oiio.ImageInput.open(str(path))
    if image_input is None:
        raise RuntimeError(f"OpenImageIO cannot open {path}")
    try:
        spec = image_input.spec()
        pixels = image_input.read_image(oiio.FLOAT)
        array = np.asarray(pixels, dtype=np.float32)
        return array.reshape(spec.height, spec.width, spec.nchannels)
    finally:
        image_input.close()


def _write_uint8_png(path: Path, array: np.ndarray) -> None:
    array = np.ascontiguousarray(array, dtype=np.uint8)
    if array.ndim == 2:
        height, width = array.shape
        channels = 1
        array = np.ascontiguousarray(array[..., np.newaxis], dtype=np.uint8)
    elif array.ndim == 3:
        height, width, channels = array.shape
    else:
        raise ValueError(f"Expected HxW or HxWxC array, got {array.shape}")
    output = oiio.ImageOutput.create(str(path))
    if output is None:
        raise RuntimeError(f"OpenImageIO cannot create {path}")
    spec = oiio.ImageSpec(width, height, channels, oiio.UINT8)
    if not output.open(str(path), spec):
        raise RuntimeError(output.geterror())
    try:
        if not output.write_image(array):
            raise RuntimeError(output.geterror())
    finally:
        output.close()


def _matrix_rows(matrix: Matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def camera_intrinsics(scene: bpy.types.Scene, camera: bpy.types.Object) -> dict[str, Any]:
    width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
    pixel_aspect = scene.render.pixel_aspect_y / scene.render.pixel_aspect_x
    camera_data = camera.data

    if camera_data.type != "PERSP":
        raise ValueError("Prototype supports perspective cameras only")

    sensor_fit = camera_data.sensor_fit
    if sensor_fit == "AUTO":
        sensor_fit = "HORIZONTAL" if width >= height * pixel_aspect else "VERTICAL"

    if sensor_fit == "VERTICAL":
        sensor_size = camera_data.sensor_height
        view_fac = height * pixel_aspect
    else:
        sensor_size = camera_data.sensor_width
        view_fac = width

    pixel_size_mm = sensor_size / camera_data.lens / view_fac
    fx = 1.0 / pixel_size_mm
    fy = fx / pixel_aspect
    cx = width * (0.5 - camera_data.shift_x)
    cy = height * (0.5 + camera_data.shift_y)
    return {
        "width": width,
        "height": height,
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(cx),
        "cy": float(cy),
        "K": [[float(fx), 0.0, float(cx)], [0.0, float(fy), float(cy)], [0.0, 0.0, 1.0]],
        "lens_mm": float(camera_data.lens),
        "sensor_width_mm": float(camera_data.sensor_width),
        "sensor_height_mm": float(camera_data.sensor_height),
        "sensor_fit": sensor_fit,
        "pixel_aspect_x": float(scene.render.pixel_aspect_x),
        "pixel_aspect_y": float(scene.render.pixel_aspect_y),
        "shift_x": float(camera_data.shift_x),
        "shift_y": float(camera_data.shift_y),
    }


def world_to_opencv(camera: bpy.types.Object) -> Matrix:
    blender_to_opencv = Matrix(
        (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, -1.0, 0.0, 0.0),
            (0.0, 0.0, -1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return blender_to_opencv @ camera.matrix_world.inverted()


def _new_file_output(
    tree: bpy.types.NodeTree,
    source_socket: bpy.types.NodeSocket,
    raw_dir: Path,
    node_name: str,
    file_prefix: str,
) -> bpy.types.Node:
    node = tree.nodes.new("CompositorNodeOutputFile")
    node.name = node_name
    node.base_path = str(raw_dir)
    node.format.file_format = "OPEN_EXR"
    node.format.color_depth = "32"
    node.format.color_mode = "RGB"
    node.format.exr_codec = "ZIP"
    node.file_slots[0].path = file_prefix
    if hasattr(node.format, "color_management"):
        node.format.color_management = "OVERRIDE"
        node.format.view_settings.view_transform = "Raw"
    tree.links.new(source_socket, node.inputs[0])
    return node


def _setup_compositor(
    scene: bpy.types.Scene, raw_dir: Path, *, include_position: bool
) -> dict[str, str]:
    scene.render.use_compositing = True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_layers = tree.nodes.new("CompositorNodeRLayers")
    composite = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(render_layers.outputs["Image"], composite.inputs["Image"])

    socket_names = [socket.name for socket in render_layers.outputs]
    required = {"Depth"}
    if include_position:
        required.add("Position")
    missing = required.difference(socket_names)
    if missing:
        raise RuntimeError(f"Render Layers node lacks outputs: {sorted(missing)}; has {socket_names}")

    def socket_named(name: str):
        return next(socket for socket in render_layers.outputs if socket.name == name)

    _new_file_output(tree, socket_named("Depth"), raw_dir, "RGBD_DEPTH", "z_")
    patterns = {"depth": "z_*.exr"}
    if include_position:
        _new_file_output(tree, socket_named("Position"), raw_dir, "RGBD_POSITION", "position_")
        patterns["position"] = "position_*.exr"
    return patterns


def _only_file(raw_dir: Path, pattern: str) -> Path:
    matches = [Path(path) for path in glob.glob(str(raw_dir / pattern))]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern} under {raw_dir}, got {matches}")
    return matches[0]


def _depth_preview(scene_depth_z: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    preview = np.zeros(scene_depth_z.shape, dtype=np.uint8)
    if not np.any(valid):
        return preview, {"near_m": 0.0, "far_m": 0.0}
    values = scene_depth_z[valid]
    near = float(np.percentile(values, 1.0))
    far = float(np.percentile(values, 99.0))
    if far <= near:
        far = near + 1e-6
    normalized = np.clip((scene_depth_z - near) / (far - near), 0.0, 1.0)
    preview[valid] = np.round((1.0 - normalized[valid]) * 255.0).astype(np.uint8)
    return preview, {"near_m": near, "far_m": far}


def render_scene_buffers(
    *,
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    skin_object: bpy.types.Object,
    output_dir: Path,
    frame: int,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Render one frame and derive aligned RGB, camera-Z, masks and metadata.

    scene_depth_z is the first visible scene surface. visible_skin_mask is one
    exactly where scene depth agrees with a second body-only depth render.
    """

    output_dir.mkdir(parents=True, exist_ok=False)
    raw_dir = output_dir / "raw_full_scene_passes"
    raw_dir.mkdir()
    body_raw_dir = output_dir / "raw_body_only_passes"
    body_raw_dir.mkdir()
    scene.frame_set(frame)
    scene.camera = camera
    scene.render.filepath = str(output_dir / "rgb.png")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False

    view_layer = scene.view_layers[0]
    view_layer.use_pass_z = True
    view_layer.use_pass_position = True
    patterns = _setup_compositor(scene, raw_dir, include_position=True)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)

    depth_path = _only_file(raw_dir, patterns["depth"])
    position_path = _only_file(raw_dir, patterns["position"])
    depth_raw = _read_image(depth_path)[..., 0]
    position_world = _read_image(position_path)[..., :3]

    renderable_types = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "CURVES"}
    hide_render_state = {
        obj.name: bool(obj.hide_render) for obj in scene.objects if obj.type in renderable_types
    }
    try:
        for obj in scene.objects:
            if obj.type in renderable_types:
                obj.hide_render = obj != skin_object
        skin_object.hide_render = False
        body_patterns = _setup_compositor(scene, body_raw_dir, include_position=False)
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=False)
    finally:
        for name, hidden in hide_render_state.items():
            obj = scene.objects.get(name)
            if obj is not None:
                obj.hide_render = hidden
        bpy.context.view_layer.update()
    body_depth_path = _only_file(body_raw_dir, body_patterns["depth"])
    body_depth_raw = _read_image(body_depth_path)[..., 0]

    intrinsics = camera_intrinsics(scene, camera)
    expected_shape = (intrinsics["height"], intrinsics["width"])
    if depth_raw.shape != expected_shape:
        raise RuntimeError(f"Depth shape {depth_raw.shape} != {expected_shape}")
    if position_world.shape[:2] != expected_shape or body_depth_raw.shape != expected_shape:
        raise RuntimeError("Render passes are not pixel-aligned")

    clip_start = float(camera.data.clip_start)
    clip_end = float(camera.data.clip_end)
    far_background_guard = max(1e-4, clip_end * 1e-6)
    valid = (
        np.isfinite(depth_raw)
        & (depth_raw > clip_start * 0.999)
        & (depth_raw < clip_end - far_background_guard)
    )
    body_valid = (
        np.isfinite(body_depth_raw)
        & (body_depth_raw > clip_start * 0.999)
        & (body_depth_raw < clip_end - far_background_guard)
    )
    scene_depth_z = np.where(valid, depth_raw, 0.0).astype(np.float32)
    body_only_depth_z = np.where(body_valid, body_depth_raw, 0.0).astype(np.float32)
    mask_depth_tolerance_m = 1e-4
    skin_mask = valid & body_valid & (np.abs(scene_depth_z - body_only_depth_z) <= mask_depth_tolerance_m)

    w2c = np.asarray(world_to_opencv(camera), dtype=np.float64)
    homogeneous = np.concatenate(
        [position_world.astype(np.float64), np.ones((*expected_shape, 1), dtype=np.float64)], axis=2
    )
    position_camera = homogeneous @ w2c.T
    position_depth_z = position_camera[..., 2]
    z_vs_position = np.abs(position_depth_z - scene_depth_z)
    z_position_errors = z_vs_position[valid]
    z_error_percentiles = (
        {
            "p50_m": float(np.percentile(z_position_errors, 50.0)),
            "p99_m": float(np.percentile(z_position_errors, 99.0)),
            "p999_m": float(np.percentile(z_position_errors, 99.9)),
            "max_m": float(z_position_errors.max()),
        }
        if z_position_errors.size
        else None
    )

    np.save(output_dir / "scene_depth_z.npy", scene_depth_z, allow_pickle=False)
    np.save(output_dir / "body_only_depth_z.npy", body_only_depth_z, allow_pickle=False)
    _write_uint8_png(output_dir / "visible_skin_mask.png", skin_mask.astype(np.uint8) * 255)
    _write_uint8_png(output_dir / "depth_valid_mask.png", valid.astype(np.uint8) * 255)
    preview, preview_range = _depth_preview(scene_depth_z, valid)
    _write_uint8_png(output_dir / "scene_depth_preview.png", preview)

    metadata = {
        "schema": "isolated-rgbd-prototype-v1",
        "blender_version": bpy.app.version_string,
        "render_engine": scene.render.engine,
        "frame": int(frame),
        "camera": {
            "name": camera.name,
            "intrinsics": intrinsics,
            "world_to_opencv_camera": _matrix_rows(world_to_opencv(camera)),
            "coordinate_convention": "OpenCV camera +X right, +Y down, +Z forward; image origin top-left",
            "distortion": {"model": "NONE_SYNTHETIC_PINHOLE", "coefficients": []},
        },
        "depth_contract": {
            "name": "scene_depth_z",
            "dtype": "float32",
            "unit": "metre (Blender unit scale is assumed 1 m)",
            "meaning": "OpenCV camera-space Z of first visible scene surface",
            "background_invalid_value": 0.0,
            "not_ray_distance": True,
        },
        "mask_contract": {
            "name": "visible_skin_mask",
            "dtype": "uint8 PNG",
            "values": {"skin_first_visible_surface": 255, "all_other_pixels": 0},
            "skin_object": skin_object.name,
            "derivation": "scene depth and body-only depth both valid and abs difference <= tolerance",
            "depth_match_tolerance_m": mask_depth_tolerance_m,
        },
        "pass_alignment": {
            "width": int(intrinsics["width"]),
            "height": int(intrinsics["height"]),
            "same_camera": camera.name,
            "same_frame": int(frame),
            "rgb_and_scene_depth_same_render_invocation": True,
            "visible_skin_mask_uses_second_body_only_render": True,
            "body_only_render_keeps_camera_frame_resolution_and_geometry_state": True,
        },
        "statistics": {
            "valid_pixel_count": int(valid.sum()),
            "skin_pixel_count": int(skin_mask.sum()),
            "depth_min_m": float(scene_depth_z[valid].min()) if np.any(valid) else None,
            "depth_max_m": float(scene_depth_z[valid].max()) if np.any(valid) else None,
            "z_pass_vs_position_z_max_abs_m": float(z_position_errors.max()) if z_position_errors.size else None,
            "z_pass_vs_position_z_mean_abs_m": float(z_position_errors.mean()) if z_position_errors.size else None,
            "z_pass_vs_position_z_error_percentiles": z_error_percentiles,
            "z_pass_vs_position_notice": (
                "Cross-pass float/interpolation consistency only; independent scene.ray_cast is the geometric check."
            ),
            "preview_range": preview_range,
        },
        "files": {
            "rgb": "rgb.png",
            "scene_depth_z": "scene_depth_z.npy",
            "body_only_depth_z_debug": "body_only_depth_z.npy",
            "visible_skin_mask": "visible_skin_mask.png",
            "depth_valid_mask": "depth_valid_mask.png",
            "scene_depth_preview": "scene_depth_preview.png",
            "raw_z_exr": str(depth_path.relative_to(output_dir)),
            "raw_position_exr": str(position_path.relative_to(output_dir)),
            "raw_body_only_z_exr": str(body_depth_path.relative_to(output_dir)),
        },
    }
    write_json(output_dir / "metadata.json", metadata)
    arrays = {
        "depth_z": scene_depth_z,
        "body_only_depth_z": body_only_depth_z,
        "valid": valid,
        "body_valid": body_valid,
        "skin_mask": skin_mask,
        "position_world": position_world,
        "position_depth_z": position_depth_z,
    }
    return metadata, arrays


def write_sha256sums(root: Path) -> None:
    rows: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{file_sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
