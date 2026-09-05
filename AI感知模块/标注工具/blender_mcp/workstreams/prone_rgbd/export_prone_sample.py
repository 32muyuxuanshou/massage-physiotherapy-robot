"""Export one prone-back RGB-D engineering sample from a frozen fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
import training_export_core as core


TARGET_NAME = "SKEL-skin-female"
CAMERA_NAME = "ACU_PRONE_BACK_CAMERA"


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _matrix_rows(matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def main() -> None:
    args = _arguments()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8-sig"))
    if fixture.get("medical_truth") is not False or fixture.get("acceptance_must_not_reselect") is not True:
        raise ValueError("fixture contract is not frozen engineering-only")
    target = bpy.data.objects.get(TARGET_NAME)
    camera = bpy.data.objects.get(CAMERA_NAME)
    scene = bpy.context.scene
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing {TARGET_NAME}")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError(f"missing {CAMERA_NAME}")
    expected_model = fixture["model"]
    actual_topology = _topology_signature(target.data)
    if (
        len(target.data.vertices) != int(expected_model["vertex_count"])
        or len(target.data.polygons) != int(expected_model["polygon_count"])
        or actual_topology != expected_model["topology_signature_sha256"]
    ):
        raise RuntimeError("frozen fixture does not match current SKEL topology")
    bindings = []
    for anchor in fixture["anchors"]:
        face_index = int(anchor["face_index"])
        current_vertices = [int(value) for value in target.data.polygons[face_index].vertices]
        if current_vertices != [int(value) for value in anchor["vertex_indices"]]:
            raise RuntimeError(f"frozen face mismatch for {anchor['point_id']}")
        bindings.append(
            {
                key: value
                for key, value in anchor.items()
                if key not in {"fixture_local_center_m", "fixture_local_normal", "construction_target_local_m", "construction_score"}
            }
        )

    snapshot = Path(bpy.data.filepath).resolve()
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    snapshot_hash = _sha256(snapshot)
    scene.camera = camera
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    exported = core.export_sample(
        scene=scene,
        depsgraph=depsgraph,
        camera=camera,
        skin_object=target,
        bindings=bindings,
        output_dir=args.output,
        frame=1,
        width=args.width,
        height=args.height,
        render_engine="BLENDER_EEVEE_NEXT",
        ray_tolerance_m=1e-4,
        mask_depth_tolerance_m=1e-4,
    )
    points = []
    for point in exported.points:
        normalized = dict(point)
        normalized["xyz_world_blender_m"] = normalized.pop("xyz_world_m")
        normalized.pop("object_name", None)
        points.append(normalized)
    buffers = exported.buffers
    intrinsics = buffers.metadata["camera"]["intrinsics"]
    projection = camera.calc_matrix_camera(
        depsgraph,
        x=args.width,
        y=args.height,
        scale_x=float(scene.render.pixel_aspect_x),
        scale_y=float(scene.render.pixel_aspect_y),
    )
    labels = {
        "schema_version": "acupoint-training-sample-v2",
        "created_at": _utc_now(),
        "medical_truth": False,
        "source_blend": str(snapshot),
        "source_blend_dirty": bool(bpy.data.is_dirty),
        "source_scene_snapshot_sha256": snapshot_hash,
        "source_fixture": str(args.fixture.resolve()),
        "source_fixture_sha256": _sha256(args.fixture),
        "scene": {
            "name": scene.name,
            "frame": 1,
            "snapshot_replayable": True,
            "snapshot_sha256": snapshot_hash,
            "dirty_at_export_start": bool(bpy.data.is_dirty),
            "unit": "m",
            "unit_scale_length": float(scene.unit_settings.scale_length),
            "contract": str(scene.get("acu_training_scene_contract") or ""),
            "prone_definition": str(scene.get("acu_prone_definition") or ""),
            "bed_top_z_m": float(scene.get("acu_bed_top_z_m", 0.0)),
            "native_pose_parameters_degrees": dict(scene.get("skel_pose_degrees", {})),
            "native_shape_betas": [float(value) for value in scene.get("skel_betas", [])],
            "native_pose_profile_sha256": str(scene.get("skel_pose_profile_sha256") or ""),
        },
        "model": expected_model,
        "camera": {
            "name": camera.name,
            "coordinate_convention": "OpenCV camera: +X right, +Y down, +Z forward; pixel origin top-left",
            "pixel_coordinate_note": "continuous edge coordinates; pixel center (column,row) is (column+0.5,row+0.5)",
            "intrinsics": intrinsics,
            "world_to_blender_camera": _matrix_rows(camera.matrix_world.inverted()),
            "world_to_opencv_camera": _matrix_rows(core.world_to_opencv_camera(camera)),
            "blender_projection_matrix": _matrix_rows(projection),
            "distortion": {
                "model": "NONE_SYNTHETIC_PINHOLE",
                "coefficients": [],
                "notice": "Real RGB-D intrinsics/distortion/noise remain uncalibrated.",
            },
        },
        "buffers": {
            "scene_depth_z": {
                "file": "scene_depth_z.npy",
                "dtype": "float32",
                "unit": "m",
                "meaning": "OPENCV_CAMERA_Z_FIRST_VISIBLE_SCENE_SURFACE",
                "background_value": 0.0,
            },
            "depth_valid_mask": {"file": "depth_valid_mask.png", "dtype": "uint8", "values": [0, 255]},
            "skin_mask": {
                "file": "skin_mask.png",
                "dtype": "uint8",
                "meaning": "VISIBLE_SKEL_SKIN_FIRST_SURFACE",
                "values": [0, 255],
            },
        },
        "render": buffers.metadata,
        "points": points,
        "notices": [
            "All ENG_* records are frozen engineering anchors, not medical acupoints.",
            (
                "This sample uses a nonzero native SKEL articulated pose followed by the rigid prone transform."
                if scene.get("skel_pose_profile_sha256")
                else "This pose is a rigid prone transform of canonical SKEL; articulated pose parameters remain canonical."
            ),
            "SKEL is a structural prior, not patient CT.",
            "Synthetic camera coordinates are not robot execution coordinates.",
        ],
    }
    labels_path = args.output / "labels.json"
    temporary = labels_path.with_suffix(".json.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(labels, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, labels_path)
    finally:
        temporary.unlink(missing_ok=True)
    result = {
        "passed": True,
        "sample": str(args.output),
        "point_count": len(points),
        "visible_count": sum(1 for point in points if point["visible"]),
        "visibility": {point["point_id"]: point["visibility_reason"] for point in points},
        "snapshot_sha256": snapshot_hash,
        "fixture_sha256": _sha256(args.fixture),
        "blend_saved_by_exporter": False,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_EXPORT_PRONE_SAMPLE=PASS")


if __name__ == "__main__":
    main()
