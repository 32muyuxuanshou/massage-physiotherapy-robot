#!/usr/bin/env python3
"""Recompute point labels for one already-rendered snapshot without rendering.

This script is launched by Blender in background mode.  It deliberately calls
only the shared surface binding, camera projection and visibility functions.  It
must never import or call ``render_scene_buffers``/``export_sample``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


EXPECTED = {
    "family": "SKEL",
    "gender": "female",
    "template_id": "skel-female-trunk-limb-v2.3",
    "object_name": "SKEL-skin-female",
    "vertex_count": 6890,
    "polygon_count": 13776,
    "topology_signature_sha256": "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--parent-labels", required=True, type=Path)
    parser.add_argument("--render-metadata", required=True, type=Path)
    parser.add_argument("--output-labels", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--core-parent", required=True, type=Path)
    parser.add_argument(
        "--truth-status",
        choices=("engineering_reference", "doctor_confirmed"),
        default="engineering_reference",
    )
    return parser.parse_args(values)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def topology_signature(mesh: bpy.types.Mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update(",".join(str(int(index)) for index in polygon.vertices).encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()


def matrix_rows(matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def close(a: float, b: float, tolerance: float = 1e-8) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance)


def assert_nested_numeric_close(actual, expected, label: str, tolerance: float = 1e-8) -> None:
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{label} shape mismatch")
        for index, (left, right) in enumerate(zip(actual, expected)):
            assert_nested_numeric_close(left, right, f"{label}[{index}]", tolerance)
        return
    if not close(actual, expected, tolerance):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    args = arguments()
    sys.path.insert(0, str(args.core_parent.resolve()))
    # Import the package, not sample_export: this keeps the no-render boundary explicit.
    from training_export_core.camera_geometry import (  # noqa: PLC0415
        camera_intrinsics,
        project_world_point,
        world_to_opencv_camera,
    )
    from training_export_core.surface_binding import sample_surface_binding  # noqa: PLC0415
    from training_export_core.visibility import evaluate_visibility  # noqa: PLC0415

    atlas = read_json(args.atlas)
    parent = read_json(args.parent_labels)
    render_metadata = read_json(args.render_metadata)
    annotations = atlas["annotations"]
    snapshot = Path(bpy.data.filepath).resolve()
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)

    scene = bpy.context.scene
    target = bpy.data.objects.get(EXPECTED["object_name"])
    camera_name = str(parent["camera"]["name"])
    camera = bpy.data.objects.get(camera_name)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing mesh {EXPECTED['object_name']}")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError(f"missing camera {camera_name}")
    if scene.unit_settings.system != "METRIC" or not close(scene.unit_settings.scale_length, 1.0):
        raise ValueError("snapshot must use METRIC units with scale_length=1")
    actual_signature = topology_signature(target.data)
    actual_model = {
        "family": "SKEL",
        "gender": str(target.get("gender", "female")).lower(),
        "template_id": str(target.get("acupoint_template_id", EXPECTED["template_id"])),
        "object_name": target.name,
        "vertex_count": len(target.data.vertices),
        "polygon_count": len(target.data.polygons),
        "topology_signature_sha256": actual_signature,
    }
    for key in ("family", "gender", "object_name", "vertex_count", "polygon_count", "topology_signature_sha256"):
        if actual_model[key] != EXPECTED[key]:
            raise ValueError(f"snapshot model mismatch for {key}: {actual_model[key]!r}")

    width = int(parent["camera"]["intrinsics"]["width"])
    height = int(parent["camera"]["intrinsics"]["height"])
    scene.camera = camera
    scene.frame_set(int(parent["scene"]["frame"]))
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    intrinsics = camera_intrinsics(scene, camera, width=width, height=height).to_dict()
    for key in ("width", "height", "fx", "fy", "cx", "cy"):
        assert_nested_numeric_close(intrinsics[key], parent["camera"]["intrinsics"][key], f"intrinsics.{key}")
    world_to_cv = matrix_rows(world_to_opencv_camera(camera))
    assert_nested_numeric_close(
        world_to_cv,
        parent["camera"]["world_to_opencv_camera"],
        "world_to_opencv_camera",
        1e-7,
    )

    points = []
    for index, annotation in enumerate(annotations):
        face_index = int(annotation["face_index"])
        expected_vertices = [int(value) for value in annotation["vertex_indices"]]
        base_vertices = [int(value) for value in target.data.polygons[face_index].vertices]
        if base_vertices != expected_vertices:
            raise ValueError(f"Atlas face vertex order mismatch for {annotation['point_id']}")
        surface = sample_surface_binding(
            target,
            face_index,
            annotation["barycentric"],
            depsgraph=depsgraph,
            expected_vertex_indices=expected_vertices,
        )
        point_world = Vector(surface.xyz_world_m)
        world_normal = Vector(surface.world_normal)
        projection = project_world_point(
            scene, camera, point_world, width=width, height=height
        )
        visibility = evaluate_visibility(
            scene=scene,
            depsgraph=depsgraph,
            camera=camera,
            target_object=target,
            point_world=point_world,
            world_normal=world_normal,
            width=width,
            height=height,
            ray_tolerance_m=1e-4,
        )
        passthrough_keys = (
            "point_id",
            "code",
            "name_zh",
            "meridian",
            "side",
            "notes",
            "confidence",
            "body_region",
            "review_status",
        )
        record = {key: annotation.get(key) for key in passthrough_keys if key in annotation}
        record.update(
            {
                "annotation_id": annotation.get("id"),
                "source_annotation_index": index,
                "object_name": surface.object_name,
                "face_index": surface.face_index,
                "vertex_indices": list(surface.vertex_indices),
                "barycentric": list(surface.barycentric),
                "xyz_world_blender_m": list(surface.xyz_world_m),
                "world_normal": list(surface.world_normal),
                "xyz_camera_opencv_m": projection["xyz_camera_opencv_m"],
                "uv_pixel_opencv": projection["uv_pixel_opencv"],
                "camera_depth_z_m": projection["camera_depth_z_m"],
                "ray_tolerance_m": 1e-4,
                **visibility.to_dict(),
            }
        )
        points.append(record)

    labels = dict(parent)
    labels.update(
        {
            "schema_version": "acupoint-training-sample-v2",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "medical_truth": args.truth_status == "doctor_confirmed",
            "source_blend": str(snapshot),
            "source_blend_dirty": bool(bpy.data.is_dirty),
            "source_scene_snapshot_sha256": sha256(snapshot),
            "source_fixture": str(args.atlas.resolve()),
            "source_fixture_sha256": sha256(args.atlas),
            "model": {
                **parent["model"],
                "family": "SKEL",
                "gender": "female",
                "template_id": EXPECTED["template_id"],
                "object_name": target.name,
                "vertex_count": len(target.data.vertices),
                "polygon_count": len(target.data.polygons),
                "topology_signature_sha256": actual_signature,
            },
            "camera": {
                **parent["camera"],
                "intrinsics": intrinsics,
                "world_to_blender_camera": matrix_rows(camera.matrix_world.inverted()),
                "world_to_opencv_camera": world_to_cv,
            },
            "render": render_metadata,
            "points": points,
            "derivation": {
                "schema": "atlas-v5-label-only-derivation-v1",
                "truth_status": args.truth_status,
                "parent_labels": str(args.parent_labels.resolve()),
                "parent_labels_sha256": sha256(args.parent_labels),
                "render_metadata_sha256": sha256(args.render_metadata),
                "render_scene_buffers_called": False,
                "shared_core_functions": [
                    "sample_surface_binding",
                    "project_world_point",
                    "evaluate_visibility",
                ],
                "snapshot_opened_in_fresh_blender_process": True,
            },
            "notices": [
                "Labels were recomputed from a plugin schema-v5 Atlas; RGB/Depth/Mask were not rerendered.",
                "Invisible points are preserved with their actual visibility_reason; 20/20 visibility is not assumed.",
                (
                    "Atlas is explicitly doctor-confirmed for this run."
                    if args.truth_status == "doctor_confirmed"
                    else "Atlas is an engineering/reference simulation and is not doctor-confirmed medical truth."
                ),
                "SKEL is a structural prior, not patient CT.",
                "Synthetic camera coordinates are not robot execution coordinates.",
            ],
        }
    )
    atomic_json(args.output_labels, labels)
    result = {
        "passed": True,
        "snapshot": str(snapshot),
        "snapshot_sha256": sha256(snapshot),
        "point_count": len(points),
        "visible_count": sum(bool(point["visible"]) for point in points),
        "visibility_reason_counts": {
            reason: sum(point["visibility_reason"] == reason for point in points)
            for reason in sorted({point["visibility_reason"] for point in points})
        },
        "render_scene_buffers_called": False,
    }
    atomic_json(args.result, result)
    print("ACU_DERIVE_LABELS_ONLY=PASS", flush=True)


if __name__ == "__main__":
    main()
