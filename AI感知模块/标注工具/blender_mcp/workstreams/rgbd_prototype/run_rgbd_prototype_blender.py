"""Run analytical plane + canonical SKEL RGB-D/Mask experiments.

Run by Blender only.  The canonical blend is loaded read-only and never saved.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rgbd_core_experimental import (  # noqa: E402
    camera_intrinsics,
    file_sha256,
    render_scene_buffers,
    world_to_opencv,
    write_json,
    write_sha256sums,
)


SKIN_NAME = "SKEL-skin-female"
SKIN_INDEX = 1
POINT = {
    "point_id": "11_MIDLINE",
    "notice": "Engineering test point only; not a medically validated acupoint.",
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


def _configure_scene(scene: bpy.types.Scene, width: int, height: int) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.display.shading.light = "STUDIO"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("RGBD_WORLD")
    scene.world.color = (0.025, 0.025, 0.025)
    scene.camera = None
    scene.frame_start = 1
    scene.frame_end = 1
    scene.frame_set(1)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def _material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.6):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def _add_camera(scene: bpy.types.Scene, name: str, matrix_world: Matrix, width: int, height: int):
    data = bpy.data.cameras.new(name)
    data.type = "PERSP"
    data.lens = 55.0
    data.sensor_width = 36.0
    data.sensor_height = 24.0
    data.sensor_fit = "HORIZONTAL"
    data.shift_x = 0.0
    data.shift_y = 0.0
    data.clip_start = 0.01
    data.clip_end = 100.0
    camera = bpy.data.objects.new(name, data)
    scene.collection.objects.link(camera)
    camera.matrix_world = matrix_world
    scene.camera = camera
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    return camera


def _add_area_light(scene: bpy.types.Scene, location: tuple[float, float, float], energy: float, size: float):
    data = bpy.data.lights.new("RGBD_AREA", type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new("RGBD_AREA", data)
    scene.collection.objects.link(light)
    light.location = location
    return light


def _project_world(scene, camera, world_point: Vector) -> tuple[np.ndarray, np.ndarray]:
    intrinsics = camera_intrinsics(scene, camera)
    camera_point = world_to_opencv(camera) @ world_point
    xyz = np.array(camera_point[:3], dtype=np.float64)
    uv = np.array(
        [
            intrinsics["fx"] * xyz[0] / xyz[2] + intrinsics["cx"],
            intrinsics["fy"] * xyz[1] / xyz[2] + intrinsics["cy"],
        ],
        dtype=np.float64,
    )
    return xyz, uv


def _plane_experiment(root: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    _configure_scene(scene, 256, 256)
    camera = _add_camera(scene, "RGBD_KNOWN_PLANE_CAMERA", Matrix.Identity(4), 256, 256)

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, -2.0))
    plane = bpy.context.object
    plane.name = "KNOWN_ZC_2M_PLANE"
    plane.pass_index = SKIN_INDEX
    plane.data.materials.append(_material("PLANE_RED", (0.65, 0.06, 0.04, 1.0)))
    _add_area_light(scene, (0.0, 0.0, -0.2), 500.0, 5.0)

    metadata, arrays = render_scene_buffers(
        scene=scene, camera=camera, skin_object=plane, output_dir=root / "known_plane", frame=1
    )
    valid = arrays["valid"]
    depth = arrays["depth_z"]
    expected_zc = 2.0
    max_z_error = float(np.max(np.abs(depth[valid] - expected_zc)))
    mean_z_error = float(np.mean(np.abs(depth[valid] - expected_zc)))

    intrinsics = metadata["camera"]["intrinsics"]
    sample_pixels = [(128, 128), (16, 16), (239, 239), (16, 239), (239, 16)]
    samples = []
    for x, y in sample_pixels:
        zc = float(depth[y, x])
        ray_distance = zc * math.sqrt(
            1.0
            + ((x + 0.5 - intrinsics["cx"]) / intrinsics["fx"]) ** 2
            + ((y + 0.5 - intrinsics["cy"]) / intrinsics["fy"]) ** 2
        )
        samples.append(
            {
                "pixel_xy_top_left": [x, y],
                "z_pass_value_m": zc,
                "expected_camera_z_m": expected_zc,
                "derived_ray_distance_m": ray_distance,
            }
        )

    result = {
        "passed": max_z_error < 5e-5,
        "geometry": "fronto-parallel plane at Blender camera local z=-2 m; OpenCV camera Zc=+2 m",
        "expected_camera_z_m": expected_zc,
        "max_abs_z_error_m": max_z_error,
        "mean_abs_z_error_m": mean_z_error,
        "z_pass_vs_position_z_max_abs_m": metadata["statistics"]["z_pass_vs_position_z_max_abs_m"],
        "pixel_samples": samples,
        "conclusion": "The Blender 4.5.12 Z pass used here is camera-space Zc, not Euclidean ray length.",
    }
    write_json(root / "known_plane" / "verification.json", result)
    return result


def _surface_point_world(skin: bpy.types.Object) -> tuple[Vector, list[int]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = skin.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        polygon = mesh.polygons[POINT["face_index"]]
        vertices = list(polygon.vertices)
        if vertices != POINT["vertex_indices"]:
            raise RuntimeError(f"Frozen point topology mismatch: {vertices} != {POINT['vertex_indices']}")
        local = Vector((0.0, 0.0, 0.0))
        for weight, vertex_index in zip(POINT["barycentric"], vertices):
            local += float(weight) * mesh.vertices[vertex_index].co
        return evaluated.matrix_world @ local, vertices
    finally:
        evaluated.to_mesh_clear()


def _add_camera_aligned_occluder(scene, camera, target_world: Vector):
    target_camera_blender = camera.matrix_world.inverted() @ target_world
    center_camera = target_camera_blender * 0.5
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    occluder = bpy.context.object
    occluder.name = "__RGBD_EXTERNAL_OCCLUDER__"
    scale = Matrix.Diagonal((0.24, 0.24, 0.04, 1.0))
    occluder.matrix_world = camera.matrix_world @ Matrix.Translation(center_camera) @ scale
    occluder.data.materials.append(_material("OCCLUDER_RED", (0.8, 0.01, 0.01, 1.0), 0.35))
    return occluder, center_camera


def _window_min_abs(depth: np.ndarray, mask: np.ndarray, x: int, y: int, target: float, radius: int = 2):
    y0, y1 = max(0, y - radius), min(depth.shape[0], y + radius + 1)
    x0, x1 = max(0, x - radius), min(depth.shape[1], x + radius + 1)
    values = depth[y0:y1, x0:x1][mask[y0:y1, x0:x1]]
    if values.size == 0:
        return None
    return float(np.min(np.abs(values - target)))


def _independent_ray_depth_check(scene, camera, depth: np.ndarray, mask: np.ndarray, sample_count: int = 25):
    """Compare rendered Zc with scene.ray_cast at deterministic pixel centers."""
    intrinsics = camera_intrinsics(scene, camera)
    ys, xs = np.nonzero(mask)
    if len(xs) < sample_count:
        raise RuntimeError(f"Not enough visible skin pixels for ray checks: {len(xs)}")
    chosen = np.linspace(0, len(xs) - 1, sample_count, dtype=np.int64)
    origin = camera.matrix_world.translation.copy()
    rotation = camera.matrix_world.to_3x3()
    w2c = world_to_opencv(camera)
    rows = []
    for index in chosen:
        x = int(xs[index])
        y = int(ys[index])
        x_cv = (x + 0.5 - intrinsics["cx"]) / intrinsics["fx"]
        y_cv = (y + 0.5 - intrinsics["cy"]) / intrinsics["fy"]
        direction_blender_camera = Vector((x_cv, -y_cv, -1.0)).normalized()
        direction_world = (rotation @ direction_blender_camera).normalized()
        hit, location, _normal, face_index, obj, _matrix = scene.ray_cast(
            bpy.context.evaluated_depsgraph_get(), origin, direction_world
        )
        if not hit or obj is None:
            rows.append({"pixel_xy": [x, y], "hit": False})
            continue
        hit_camera = w2c @ location
        ray_z = float(hit_camera.z)
        render_z = float(depth[y, x])
        error = abs(ray_z - render_z)
        tolerance = max(0.002, 0.001 * abs(ray_z))
        rows.append(
            {
                "pixel_xy": [x, y],
                "hit": True,
                "hit_object": obj.name,
                "hit_face_index": int(face_index),
                "render_zc_m": render_z,
                "ray_cast_zc_m": ray_z,
                "abs_error_m": error,
                "tolerance_m": tolerance,
                "passed": error <= tolerance,
            }
        )
    errors = [row["abs_error_m"] for row in rows if row.get("hit")]
    passed = len(errors) == sample_count and all(row.get("passed", False) for row in rows)
    return {
        "passed": passed,
        "sample_count": sample_count,
        "tolerance_rule": "max(0.002 m, 0.001 * abs(ray_cast_zc))",
        "p50_abs_error_m": float(np.percentile(errors, 50.0)) if errors else None,
        "p99_abs_error_m": float(np.percentile(errors, 99.0)) if errors else None,
        "max_abs_error_m": float(max(errors)) if errors else None,
        "samples": rows,
    }


def _skel_experiment(root: Path, source_blend: Path) -> dict:
    bpy.ops.wm.open_mainfile(filepath=str(source_blend), load_ui=False)
    scene = bpy.context.scene
    _configure_scene(scene, 512, 512)
    skin = bpy.data.objects.get(SKIN_NAME)
    if skin is None or skin.type != "MESH":
        raise RuntimeError(f"Missing {SKIN_NAME}")
    skin.pass_index = SKIN_INDEX
    skin.hide_render = False

    hidden_non_skin = []
    for obj in scene.objects:
        if obj != skin and obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = True
            hidden_non_skin.append(obj.name)

    camera = _add_camera(scene, "RGBD_SKEL_CAMERA_TEST", WORLD_TO_BLENDER_CAMERA.inverted(), 512, 512)
    _add_area_light(scene, tuple(camera.location), 1200.0, 4.0)
    world_point, vertices = _surface_point_world(skin)
    point_camera, point_uv = _project_world(scene, camera, world_point)
    pixel_x = int(np.floor(point_uv[0]))
    pixel_y = int(np.floor(point_uv[1]))

    baseline_meta, baseline_arrays = render_scene_buffers(
        scene=scene, camera=camera, skin_object=skin, output_dir=root / "skel_baseline", frame=1
    )
    baseline_ray_check = _independent_ray_depth_check(
        scene, camera, baseline_arrays["depth_z"], baseline_arrays["skin_mask"]
    )
    occluder, center_camera_blender = _add_camera_aligned_occluder(scene, camera, world_point)
    occluder.hide_render = False
    occluded_meta, occluded_arrays = render_scene_buffers(
        scene=scene, camera=camera, skin_object=skin, output_dir=root / "skel_occluded", frame=1
    )
    occluded_ray_check = _independent_ray_depth_check(
        scene, camera, occluded_arrays["depth_z"], occluded_arrays["skin_mask"]
    )

    baseline_depth = baseline_arrays["depth_z"]
    baseline_skin = baseline_arrays["skin_mask"]
    occluded_depth = occluded_arrays["depth_z"]
    occluded_skin = occluded_arrays["skin_mask"]
    if not (0 <= pixel_x < 512 and 0 <= pixel_y < 512):
        raise RuntimeError(f"Frozen engineering point projects outside image: {point_uv}")

    baseline_point_depth_error = _window_min_abs(
        baseline_depth, baseline_skin, pixel_x, pixel_y, float(point_camera[2]), radius=2
    )
    center_depth = float(occluded_depth[pixel_y, pixel_x])
    center_skin = bool(occluded_skin[pixel_y, pixel_x])
    expected_occluder_front_z = float(-center_camera_blender.z - 0.02)
    occluder_depth_error = abs(center_depth - expected_occluder_front_z)
    newly_occluded_skin_pixels = int(np.count_nonzero(baseline_skin & ~occluded_skin))
    ray_origin = camera.matrix_world.translation.copy()
    ray_direction = (world_point - ray_origin).normalized()
    ray_hit, ray_location, _normal, ray_face, ray_object, _matrix = scene.ray_cast(
        bpy.context.evaluated_depsgraph_get(), ray_origin, ray_direction
    )
    ray_hit_object = ray_object.name if ray_hit and ray_object is not None else None

    same_intrinsics = baseline_meta["camera"]["intrinsics"] == occluded_meta["camera"]["intrinsics"]
    same_frame = baseline_meta["frame"] == occluded_meta["frame"] == 1
    same_shape = baseline_depth.shape == occluded_depth.shape == baseline_skin.shape == occluded_skin.shape
    passed = bool(
        baseline_point_depth_error is not None
        and baseline_point_depth_error < 0.01
        and ray_hit_object == occluder.name
        and not center_skin
        and center_depth < float(point_camera[2])
        and occluder_depth_error < 0.01
        and newly_occluded_skin_pixels > 0
        and same_intrinsics
        and same_frame
        and same_shape
        and baseline_meta["statistics"]["z_pass_vs_position_z_max_abs_m"] < 5e-4
        and occluded_meta["statistics"]["z_pass_vs_position_z_max_abs_m"] < 5e-4
        and baseline_ray_check["passed"]
        and occluded_ray_check["passed"]
    )
    result = {
        "passed": passed,
        "source_blend": str(source_blend),
        "source_blend_sha256_at_start": file_sha256(source_blend),
        "source_was_never_saved": True,
        "skin_object": skin.name,
        "hidden_non_skin_renderables": hidden_non_skin,
        "engineering_point": {
            **POINT,
            "evaluated_vertex_indices": vertices,
            "xyz_world_m": list(world_point),
            "xyz_camera_opencv_m": point_camera,
            "uv_top_left_px": point_uv,
            "sample_pixel_xy": [pixel_x, pixel_y],
            "baseline_5x5_min_depth_error_to_point_zc_m": baseline_point_depth_error,
        },
        "external_occlusion": {
            "occluder_name": occluder.name,
            "occluder_center_blender_camera": list(center_camera_blender),
            "expected_front_surface_zc_m": expected_occluder_front_z,
            "point_pixel_scene_depth_z_m": center_depth,
            "depth_error_to_expected_occluder_front_m": occluder_depth_error,
            "point_pixel_visible_skin_mask": 255 if center_skin else 0,
            "point_is_behind_occluder": center_depth < float(point_camera[2]),
            "newly_occluded_skin_pixel_count": newly_occluded_skin_pixels,
            "independent_scene_ray_cast": {
                "hit": bool(ray_hit),
                "hit_object": ray_hit_object,
                "hit_face_index": int(ray_face) if ray_hit else None,
                "hit_location_world_m": list(ray_location) if ray_hit else None,
            },
        },
        "alignment": {
            "same_camera_intrinsics": same_intrinsics,
            "same_frame": same_frame,
            "same_resolution_and_array_shape": same_shape,
        },
        "z_pass_checks": {
            "cross_pass_numeric_tolerance_m": 0.0005,
            "cross_pass_notice": (
                "Z vs Position is a float/interpolation consistency check, not the primary geometry proof."
            ),
            "baseline_vs_position_z_max_abs_m": baseline_meta["statistics"][
                "z_pass_vs_position_z_max_abs_m"
            ],
            "baseline_vs_position_z_error_percentiles": baseline_meta["statistics"][
                "z_pass_vs_position_z_error_percentiles"
            ],
            "occluded_vs_position_z_max_abs_m": occluded_meta["statistics"][
                "z_pass_vs_position_z_max_abs_m"
            ],
            "occluded_vs_position_z_error_percentiles": occluded_meta["statistics"][
                "z_pass_vs_position_z_error_percentiles"
            ],
            "baseline_independent_scene_ray_cast": baseline_ray_check,
            "occluded_independent_scene_ray_cast": occluded_ray_check,
        },
        "conclusion": (
            "scene_depth_z follows the first visible scene surface; visible_skin_mask is zero where the external "
            "occluder is first. The engineering point is not medical ground truth."
        ),
    }
    write_json(root / "skel_verification.json", result)
    return result


def _write_report(root: Path, summary: dict) -> None:
    plane = summary["known_plane"]
    skel = summary["skel"]
    report = f"""# 隔离 RGB-D / SKEL Skin Mask 原型报告

生成时间：{summary['created_at']}  
Blender：{bpy.app.version_string}  
总体结果：**{'PASS' if summary['passed'] else 'FAIL'}**

## 已证明

1. 在本机便携 Blender 4.5.12 LTS 中，正对相机且 OpenCV `Zc=2 m` 的已知大平面，原生 Z Pass 的最大绝对误差为 `{plane['max_abs_z_error_m']:.9g} m`。角落像素的 Z Pass 仍为 2 m，而由内参计算的射线距离更长，因此本实验所用 Z Pass 是 camera-space Zc，不是欧氏射线长度。
2. Z Pass 与 Position Pass 变换到 OpenCV 相机坐标后的 Z 在数值上相符。SKEL 基线 P50/P99/max 为 `{skel['z_pass_checks']['baseline_vs_position_z_error_percentiles']['p50_m']:.9g}` / `{skel['z_pass_checks']['baseline_vs_position_z_error_percentiles']['p99_m']:.9g}` / `{skel['z_pass_checks']['baseline_vs_position_z_error_percentiles']['max_m']:.9g} m`；遮挡场景 P50/P99/max 为 `{skel['z_pass_checks']['occluded_vs_position_z_error_percentiles']['p50_m']:.9g}` / `{skel['z_pass_checks']['occluded_vs_position_z_error_percentiles']['p99_m']:.9g}` / `{skel['z_pass_checks']['occluded_vs_position_z_error_percentiles']['max_m']:.9g} m`。这是 EXR/插值的交叉通道数值一致性，不作为主几何证据。
3. RGB 与 `scene_depth_z.npy` 来自同一次渲染；`visible_skin_mask.png` 由同 Camera、同帧、同分辨率和同几何状态的第二次 body-only Z 渲染派生，尺寸严格相同。这里不冒充“所有通道同一次 render”。
4. 外部遮挡物覆盖工程测试点后，独立 `scene.ray_cast` 首个命中 `{skel['external_occlusion']['independent_scene_ray_cast']['hit_object']}`，Skin Mask 为 `{skel['external_occlusion']['point_pixel_visible_skin_mask']}`，Depth 为前方遮挡物 `{skel['external_occlusion']['point_pixel_scene_depth_z_m']:.6f} m`，不是后方皮肤 `{skel['engineering_point']['xyz_camera_opencv_m'][2]:.6f} m`。
5. canonical SKEL 文件只读加载、未调用保存；外部进程仍需在结束后复核哈希。
6. 独立 `scene.ray_cast` 对 25 个确定性可见皮肤像素复算 Zc：基线最大误差 `{skel['z_pass_checks']['baseline_independent_scene_ray_cast']['max_abs_error_m']:.9g} m`，遮挡场景最大误差 `{skel['z_pass_checks']['occluded_independent_scene_ray_cast']['max_abs_error_m']:.9g} m`；验收规则为 `max(2 mm, 深度的 0.1%)`。

## 未证明

- 没有验证真实 RGB-D 相机的畸变、深度尺度、噪声、空洞或边缘飞点。
- 没有验证俯卧场景、床面、半透明物体、毛发、运动模糊、景深或材质透明度。
- 没有证明医学穴位传播；使用的 `11_MIDLINE / 111` 只是工程测试点。
- 这是隔离原型，尚未接入 `training_export_core`、正式插件、MCP bridge 或批量生成器。

## 权威输出契约

- `scene_depth_z.npy`：`float32`，单位米，OpenCV 相机 `+Z` 前向，保存相机射线上第一个可见场景表面的 Zc；背景/无效值固定为 `0.0`。
- `visible_skin_mask.png`：`uint8`，只有 scene Z 与 body-only Z 都有效且深度相等时为 `255`，遮挡物、骨架和背景为 `0`。
- `depth_valid_mask.png`：`uint8`，有效场景深度为 `255`，背景为 `0`。
- `rgb.png` 与 scene Depth 来自同一次 render；Mask 的 body-only Z 来自第二次 render，但必须保持同一 Camera、帧、分辨率和几何状态。

## 建议集成的最小 API

```python
render_scene_buffers(
    *,
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    skin_object: bpy.types.Object,
    output_dir: pathlib.Path,
    frame: int,
) -> tuple[metadata, arrays]
```

集成时应把实现迁入独立 `training_export_core.render_buffers`，由内部研究面板、MCP 与批量生成器共同调用；不要复制三份代码，也不要放进医生主标注流程。

## 一手依据

- Blender Manual, Render Layers Passes（Z、Position、Index 等数据 Pass 的官方定义）：https://docs.blender.org/manual/en/latest/render/layers/passes.html
- Blender Python API：https://docs.blender.org/api/current/
- BlenderProc RendererUtility（原生 Z Pass 作为 depth；需要时再转 distance）：https://github.com/DLR-RM/BlenderProc/blob/main/blenderproc/python/renderer/RendererUtility.py
- BlenderProc PostProcessingUtility（depth / distance 解析转换公式）：https://github.com/DLR-RM/BlenderProc/blob/main/blenderproc/python/postprocessing/PostProcessingUtility.py

## 文件说明

- `known_plane/`：解析 Zc=2 m 平面实验及 RGB/Depth/Mask/原始 EXR。
- `skel_baseline/`：无遮拦 canonical SKEL 输出。
- `skel_occluded/`：同一相机、同一帧下增加外部遮挡物的输出。
- `skel_verification.json`、`run_summary.json`：机器可读验收结果。
- `SHA256SUMS.txt`：本交付目录全部文件校验。
"""
    (root / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 2:
        raise SystemExit("Usage: blender --background --python run_rgbd_prototype_blender.py -- OUTPUT_DIR SOURCE_BLEND")
    output_root = Path(argv[0]).resolve()
    source_blend = Path(argv[1]).resolve()
    output_root.mkdir(parents=True, exist_ok=False)

    plane_result = _plane_experiment(output_root)
    skel_result = _skel_experiment(output_root, source_blend)
    source_hash_end = file_sha256(source_blend)
    source_hash_unchanged = source_hash_end == skel_result["source_blend_sha256_at_start"]
    summary = {
        "schema": "isolated-rgbd-prototype-run-v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": bool(plane_result["passed"] and skel_result["passed"] and source_hash_unchanged),
        "known_plane": plane_result,
        "skel": skel_result,
        "source_blend_sha256_at_end": source_hash_end,
        "source_blend_hash_unchanged_within_process": source_hash_unchanged,
        "production_files_modified": False,
        "notes": [
            "No save operation is called.",
            "The source blend is loaded read-only and all scene changes remain in process memory.",
            "The engineering point is not a medical acupoint.",
        ],
    }
    write_json(output_root / "run_summary.json", summary)
    _write_report(output_root, summary)
    write_sha256sums(output_root)
    print("RGBD_PROTOTYPE_RESULT=" + json.dumps({"passed": summary["passed"], "output": str(output_root)}))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
