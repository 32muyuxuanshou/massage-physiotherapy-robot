"""Non-destructive RGB, scene camera-Z depth, and visible skin-mask export."""

from __future__ import annotations

import glob
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bpy
import numpy as np
import OpenImageIO as oiio

from .camera_geometry import camera_intrinsics, matrix_rows, world_to_opencv_camera
from .depth_raycast import pixel_center_buffers


_RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "CURVES"}


@dataclass
class RenderBuffersResult:
    output_dir: Path
    rgb_path: Path
    scene_depth_path: Path
    valid_mask_path: Path
    skin_mask_path: Path
    metadata_path: Path
    scene_depth_z: np.ndarray
    depth_valid_mask: np.ndarray
    skin_mask: np.ndarray
    metadata: dict[str, Any]


def _read_float_image(path: Path) -> np.ndarray:
    image_input = oiio.ImageInput.open(str(path))
    if image_input is None:
        raise RuntimeError(f"OpenImageIO cannot open {path}")
    try:
        spec = image_input.spec()
        pixels = np.asarray(image_input.read_image(oiio.FLOAT), dtype=np.float32)
        return pixels.reshape(spec.height, spec.width, spec.nchannels)
    finally:
        image_input.close()


def _write_uint8_png(path: Path, array: np.ndarray) -> None:
    array = np.asarray(array, dtype=np.uint8)
    if array.ndim == 2:
        height, width = array.shape
        channels = 1
        array = np.ascontiguousarray(array[..., np.newaxis], dtype=np.uint8)
    elif array.ndim == 3:
        height, width, channels = array.shape
        array = np.ascontiguousarray(array, dtype=np.uint8)
    else:
        raise ValueError(f"PNG array must be HxW or HxWxC, got {array.shape}")
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


def _new_exr_output(tree, source_socket, output_dir: Path, node_name: str, prefix: str) -> None:
    node = tree.nodes.new("CompositorNodeOutputFile")
    node.name = node_name
    node.base_path = str(output_dir)
    node.format.file_format = "OPEN_EXR"
    node.format.color_depth = "32"
    node.format.color_mode = "RGB"
    node.format.exr_codec = "ZIP"
    node.file_slots[0].path = prefix
    if hasattr(node.format, "color_management"):
        node.format.color_management = "OVERRIDE"
        node.format.view_settings.view_transform = "Raw"
    tree.links.new(source_socket, node.inputs[0])


def _configure_compositor(scene: bpy.types.Scene, raw_dir: Path, *, include_position: bool) -> dict[str, str]:
    scene.render.use_compositing = True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_layers = tree.nodes.new("CompositorNodeRLayers")
    render_layers.scene = scene
    render_layers.layer = scene.view_layers[0].name
    composite = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(render_layers.outputs["Image"], composite.inputs["Image"])

    def socket_named(name: str):
        for socket in render_layers.outputs:
            if socket.name == name and not socket.is_unavailable:
                return socket
        raise RuntimeError(f"Render Layers output {name!r} is unavailable for {scene.render.engine}")

    _new_exr_output(tree, socket_named("Depth"), raw_dir, "TRAIN_DEPTH", "z_")
    patterns = {"depth": "z_*.exr"}
    if include_position:
        _new_exr_output(tree, socket_named("Position"), raw_dir, "TRAIN_POSITION", "position_")
        patterns["position"] = "position_*.exr"
    return patterns


def _only_file(directory: Path, pattern: str) -> Path:
    matches = [Path(path) for path in glob.glob(str(directory / pattern))]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {pattern} under {directory}, got {matches}")
    return matches[0]


def _copy_render_settings(
    source: bpy.types.Scene,
    target: bpy.types.Scene,
    *,
    width: int | None,
    height: int | None,
    render_engine: str,
) -> None:
    target.render.engine = render_engine
    if render_engine == "BLENDER_EEVEE_NEXT":
        # Eevee film jitter makes the Z/Position pass a subpixel sample, not
        # necessarily the pixel-centre first surface (notably at silhouettes).
        # In Blender 4.5 Film::init, one sample forces filter_radius=0; jitter
        # is then zero. Keep RGB and Z on that same unfiltered sampling grid.
        # This is an engineering pixel-centre export, not a beauty render.
        target.eevee.taa_render_samples = 1
        target.render.filter_size = 0.0
    target.render.resolution_x = int(width if width is not None else source.render.resolution_x)
    target.render.resolution_y = int(height if height is not None else source.render.resolution_y)
    target.render.resolution_percentage = 100
    target.render.pixel_aspect_x = source.render.pixel_aspect_x
    target.render.pixel_aspect_y = source.render.pixel_aspect_y
    target.render.film_transparent = False
    target.render.use_file_extension = True
    target.render.image_settings.file_format = "PNG"
    target.render.image_settings.color_mode = "RGB"
    target.render.image_settings.color_depth = "8"
    target.world = source.world
    target.unit_settings.system = source.unit_settings.system
    target.unit_settings.scale_length = source.unit_settings.scale_length
    target.view_settings.view_transform = source.view_settings.view_transform
    target.view_settings.look = source.view_settings.look
    target.view_settings.exposure = source.view_settings.exposure
    target.view_settings.gamma = source.view_settings.gamma


def _create_temp_scene(
    source_scene: bpy.types.Scene,
    camera: bpy.types.Object,
    *,
    width: int | None,
    height: int | None,
    render_engine: str,
    frame: int,
) -> bpy.types.Scene:
    source_use_nodes = bool(source_scene.use_nodes)
    source_node_tree = source_scene.node_tree
    temp_scene = source_scene.copy()
    temp_scene.name = "__ACU_TRAINING_EXPORT_TEMP__"
    try:
        if source_node_tree is not None and temp_scene.node_tree == source_node_tree:
            raise RuntimeError("source_scene.copy() shared the compositor node tree")
        temp_scene.use_nodes = True
        if bool(source_scene.use_nodes) != source_use_nodes:
            raise RuntimeError("enabling nodes on temporary scene mutated source_scene.use_nodes")
        if source_scene.node_tree is not None and temp_scene.node_tree == source_scene.node_tree:
            raise RuntimeError("temporary compositor node tree is not independent")
        _copy_render_settings(source_scene, temp_scene, width=width, height=height, render_engine=render_engine)
        temp_scene.camera = camera
        temp_scene.frame_set(frame)
        return temp_scene
    except Exception:
        bpy.data.scenes.remove(temp_scene)
        raise


def _render_scene(scene: bpy.types.Scene, *, write_still: bool) -> None:
    bpy.ops.render.render(write_still=write_still, scene=scene.name)


def render_scene_buffers(
    *,
    source_scene: bpy.types.Scene,
    camera: bpy.types.Object,
    skin_object: bpy.types.Object,
    output_dir: str | Path,
    frame: int | None = None,
    width: int | None = None,
    height: int | None = None,
    render_engine: str = "BLENDER_EEVEE_NEXT",
    mask_depth_tolerance_m: float = 1e-4,
    debug_keep_intermediates: bool = False,
) -> RenderBuffersResult:
    """Export aligned RGB, first-surface camera-Z, valid mask, and visible skin mask.

    RGB is rendered without jitter. Depth and skin ownership use pixel-centre
    scene rays on identical camera/frame/geometry; the GPU Z passes are kept
    only as diagnostics because silhouette coverage can differ. Source nodes are never
    touched.  Shared object ``hide_render`` values are restored in ``finally``.
    """

    if camera.type != "CAMERA":
        raise ValueError("camera must be a CAMERA object")
    if skin_object.type != "MESH":
        raise ValueError("skin_object must be a MESH object")
    if source_scene.objects.get(camera.name) != camera:
        raise ValueError("camera must belong to source_scene")
    if source_scene.objects.get(skin_object.name) != skin_object:
        raise ValueError("skin_object must belong to source_scene")
    if source_scene.unit_settings.system != "METRIC" or abs(source_scene.unit_settings.scale_length - 1.0) > 1e-9:
        raise ValueError(
            "training export writes metres and therefore requires METRIC units with scale_length == 1.0"
        )
    if mask_depth_tolerance_m <= 0.0:
        raise ValueError("mask_depth_tolerance_m must be positive")
    output = Path(output_dir).resolve()
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(f"output path exists and is not a directory: {output}")
        if any(output.iterdir()):
            raise FileExistsError(f"output directory must be empty; refusing overwrite: {output}")
    else:
        output.mkdir(parents=True, exist_ok=False)
    raw_context = None
    if debug_keep_intermediates:
        raw_root = output / "debug_intermediates"
        raw_root.mkdir()
    else:
        raw_context = tempfile.TemporaryDirectory(prefix="acu_training_render_passes_")
        raw_root = Path(raw_context.name)
    raw_full = raw_root / "full_scene"
    raw_body = raw_root / "body_only"
    raw_full.mkdir()
    raw_body.mkdir()
    frame = int(source_scene.frame_current if frame is None else frame)

    temp_scene = _create_temp_scene(
        source_scene,
        camera,
        width=width,
        height=height,
        render_engine=render_engine,
        frame=frame,
    )
    hide_state = {
        obj.name: bool(obj.hide_render) for obj in source_scene.objects if obj.type in _RENDERABLE_TYPES
    }
    try:
        temp_scene.render.filepath = str(output / "rgb.png")
        view_layer = temp_scene.view_layers[0]
        view_layer.use_pass_z = True
        view_layer.use_pass_position = True
        patterns = _configure_compositor(temp_scene, raw_full, include_position=True)
        _render_scene(temp_scene, write_still=True)
        depth_path = _only_file(raw_full, patterns["depth"])
        position_path = _only_file(raw_full, patterns["position"])

        try:
            for obj in source_scene.objects:
                if obj.type in _RENDERABLE_TYPES:
                    obj.hide_render = obj != skin_object
            skin_object.hide_render = False
            body_patterns = _configure_compositor(temp_scene, raw_body, include_position=False)
            _render_scene(temp_scene, write_still=False)
        finally:
            for name, hidden in hide_state.items():
                obj = bpy.data.objects.get(name)
                if obj is not None:
                    obj.hide_render = hidden
        body_depth_path = _only_file(raw_body, body_patterns["depth"])

        depth_raw = _read_float_image(depth_path)[..., 0]
        body_depth_raw = _read_float_image(body_depth_path)[..., 0]
        position_world = _read_float_image(position_path)[..., :3]
        intrinsics = camera_intrinsics(temp_scene, camera)
        expected_shape = (intrinsics.height, intrinsics.width)
        if depth_raw.shape != body_depth_raw.shape or depth_raw.shape != expected_shape:
            raise RuntimeError("RGB-D render passes do not share the configured dimensions")
        if position_world.shape[:2] != expected_shape:
            raise RuntimeError("Position pass is not aligned with depth")

        clip_start = float(camera.data.clip_start)
        clip_end = float(camera.data.clip_end)
        # Eevee may encode background at a value slightly below clip_end.
        # Use a conservative relative guard so far-plane quantization cannot be
        # mistaken for valid scene/body depth (and therefore visible skin).
        far_guard = max(1e-3, clip_end * 1e-3)
        valid = (
            np.isfinite(depth_raw)
            & (depth_raw > clip_start * 0.999)
            & (depth_raw < clip_end - far_guard)
        )
        body_valid = (
            np.isfinite(body_depth_raw)
            & (body_depth_raw > clip_start * 0.999)
            & (body_depth_raw < clip_end - far_guard)
        )
        scene_depth_z = np.where(valid, depth_raw, 0.0).astype(np.float32)
        body_depth_z = np.where(body_valid, body_depth_raw, 0.0).astype(np.float32)
        skin_mask = valid & body_valid & (
            np.abs(scene_depth_z - body_depth_z) <= float(mask_depth_tolerance_m)
        )
        raster_depth = scene_depth_z
        raster_skin = skin_mask
        scene_depth_z, valid, skin_mask = pixel_center_buffers(source_scene, camera, skin_object, intrinsics)
        ownership_differences = int(np.count_nonzero(raster_skin != skin_mask))
        ray_raster_max_error = float(np.max(np.abs(raster_depth-scene_depth_z)))

        scene_depth_path = output / "scene_depth_z.npy"
        valid_mask_path = output / "depth_valid_mask.png"
        skin_mask_path = output / "skin_mask.png"
        np.save(scene_depth_path, scene_depth_z, allow_pickle=False)
        if debug_keep_intermediates:
            np.save(output / "debug_intermediates" / "body_only_depth_z.npy", body_depth_z, allow_pickle=False)
        _write_uint8_png(valid_mask_path, valid.astype(np.uint8) * 255)
        _write_uint8_png(skin_mask_path, skin_mask.astype(np.uint8) * 255)

        metadata = {
            "schema": "training-export-render-buffers-v1",
            "blender_version": bpy.app.version_string,
            "source_scene": source_scene.name,
            "temporary_scene_used": True,
            "temporary_scene_is_source_scene_copy": True,
            "source_scene_nodes_modified": False,
            "frame": frame,
            "render_engine": render_engine,
            "camera": {
                "name": camera.name,
                "intrinsics": intrinsics.to_dict(),
                "world_to_opencv_camera": matrix_rows(world_to_opencv_camera(camera)),
                "coordinate_convention": "OpenCV +X right, +Y down, +Z forward; image origin top-left",
            },
            "depth": {
                "file": scene_depth_path.name,
                "dtype": "float32",
                "unit": "m",
                "meaning": "camera-space Zc of first visible scene surface",
                "background_invalid_value": 0.0,
                "far_clip_guard_m": float(far_guard),
                "backend": "SCENE_RAY_CAST_PIXEL_CENTER",
                "clip_rule": "clip_start <= camera_Z < clip_end; far_clip_guard applies only to diagnostic raster pass",
            },
            "valid_mask": {"file": valid_mask_path.name, "values": {"valid": 255, "invalid": 0}},
            "skin_mask": {
                "file": skin_mask_path.name,
                "meaning": "visible SKEL skin is the first scene surface",
                "values": {"visible_skin": 255, "other": 0},
                "derivation": "first pixel-centre scene ray hit is the SKEL skin object",
                "depth_match_tolerance_m": None,
                "second_render_required": False,
                "diagnostic_body_render_performed": True,
            },
            "alignment": {
                "width": intrinsics.width,
                "height": intrinsics.height,
                "same_camera": camera.name,
                "same_frame": frame,
                "rgb_and_scene_z_same_render": False,
                "rgb_and_scene_z_same_camera_frame_geometry": True,
                "body_only_z_same_camera_frame_resolution_geometry": True,
                "pixel_sampling": "PIXEL_CENTER_UNFILTERED" if render_engine == "BLENDER_EEVEE_NEXT" else "ENGINE_DEFAULT_UNVALIDATED",
                "eevee_render_samples": int(temp_scene.eevee.taa_render_samples) if render_engine == "BLENDER_EEVEE_NEXT" else None,
                "rgb_antialiasing": False if render_engine == "BLENDER_EEVEE_NEXT" else None,
            },
            "debug_intermediates_kept": bool(debug_keep_intermediates),
            "raster_diagnostic": {
                "skin_ownership_disagreement_pixels": ownership_differences,
                "max_depth_disagreement_m": ray_raster_max_error,
                "notice": "GPU silhouette coverage can differ at subpixel boundaries; labels/depth use centre rays, RGB uses raster coverage.",
            },
            "statistics": {
                "valid_pixel_count": int(valid.sum()),
                "skin_pixel_count": int(skin_mask.sum()),
                "depth_min_m": float(scene_depth_z[valid].min()) if np.any(valid) else None,
                "depth_max_m": float(scene_depth_z[valid].max()) if np.any(valid) else None,
            },
            "limitations": [
                "Eevee exports use one unfiltered pixel-centre sample; RGB edges are not antialiased.",
                "Synthetic pinhole camera has no real-sensor distortion or noise.",
                "RGB raster coverage and centre-ray surface ownership may differ at individual silhouette pixels.",
                "Only opaque geometry with matching viewport/render geometry is validated; coplanar ties are undefined.",
                "Transparent materials, motion blur, and depth of field require separate validation.",
            ],
        }
        metadata_path = output / "render_metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return RenderBuffersResult(
            output_dir=output,
            rgb_path=output / "rgb.png",
            scene_depth_path=scene_depth_path,
            valid_mask_path=valid_mask_path,
            skin_mask_path=skin_mask_path,
            metadata_path=metadata_path,
            scene_depth_z=scene_depth_z,
            depth_valid_mask=valid,
            skin_mask=skin_mask,
            metadata=metadata,
        )
    finally:
        for name, hidden in hide_state.items():
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_render = hidden
        bpy.data.scenes.remove(temp_scene)
        if raw_context is not None:
            raw_context.cleanup()
