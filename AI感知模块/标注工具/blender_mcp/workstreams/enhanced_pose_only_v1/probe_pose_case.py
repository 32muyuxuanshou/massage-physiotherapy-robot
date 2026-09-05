"""Probe one fixed-shape native SKEL pose using the shared training export core."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TARGET = "SKEL-skin-female"
CAMERA = "ACU_PRONE_BACK_CAMERA"
BED = "ACU_PRONE_BED"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
POSE_NAMES = (
    "pelvis_tilt", "pelvis_list", "pelvis_rotation", "hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
    "knee_angle_r", "ankle_angle_r", "subtalar_angle_r", "mtp_angle_r", "hip_flexion_l", "hip_adduction_l",
    "hip_rotation_l", "knee_angle_l", "ankle_angle_l", "subtalar_angle_l", "mtp_angle_l", "lumbar_bending",
    "lumbar_extension", "lumbar_twist", "thorax_bending", "thorax_extension", "thorax_twist", "head_bending",
    "head_extension", "head_twist", "scapula_abduction_r", "scapula_elevation_r", "scapula_upward_rot_r",
    "shoulder_r_x", "shoulder_r_y", "shoulder_r_z", "elbow_flexion_r", "pro_sup_r", "wrist_flexion_r",
    "wrist_deviation_r", "scapula_abduction_l", "scapula_elevation_l", "scapula_upward_rot_l", "shoulder_l_x",
    "shoulder_l_y", "shoulder_l_z", "elbow_flexion_l", "pro_sup_l", "wrist_flexion_l", "wrist_deviation_l",
)


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--native-parameters", required=True, type=Path)
    parser.add_argument("--core-parent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def matrix_rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def main() -> None:
    args = arguments()
    sys.path.insert(0, str(args.core_parent.resolve()))
    from training_export_core.camera_geometry import project_world_point  # noqa: PLC0415
    from training_export_core.surface_binding import sample_surface_binding  # noqa: PLC0415
    from training_export_core.visibility import evaluate_visibility  # noqa: PLC0415

    atlas, profile, native = read(args.atlas), read(args.profile), read(args.native_parameters)
    requested = [float(value) for value in profile["pose_vector_degrees"]]
    effective = [math.degrees(float(value)) for value in native["pose"]]
    scene_map = dict(bpy.context.scene.get("skel_pose_degrees", {}))
    recorded = [float(scene_map.get(name, 0.0)) for name in POSE_NAMES]
    if len(requested) != 46 or len(effective) != 46 or len(recorded) != 46:
        raise ValueError("requested/effective/scene pose vectors must each contain 46 values")
    max_chain_error = max(abs(a - b) for vectors in ((requested, effective), (requested, recorded)) for a, b in zip(*vectors))
    if max_chain_error > 1e-6:
        raise ValueError(f"46D pose control-chain mismatch: {max_chain_error} deg")
    if [float(value) for value in profile["betas"]] != [0.0] * 10 or [float(value) for value in native["betas"]] != [0.0] * 10:
        raise ValueError("POSE_ONLY requires beta=0")

    scene = bpy.context.scene
    target, camera, bed = (bpy.data.objects.get(name) for name in (TARGET, CAMERA, BED))
    if target is None or camera is None or bed is None:
        raise RuntimeError("fixed SKEL/camera/bed scene is incomplete")
    scene.camera = camera
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        signature = topology_signature(mesh)
        if signature != EXPECTED_TOPOLOGY:
            raise RuntimeError(f"topology mismatch: {signature}")
        local_vertices = [vertex.co.copy() for vertex in mesh.vertices]
        polygon_vertices = [[int(value) for value in polygon.vertices] for polygon in mesh.polygons]
        world_vertices = [evaluated.matrix_world @ coordinate for coordinate in local_vertices]
        vertex_digest = hashlib.sha256()
        for coordinate in local_vertices:
            vertex_digest.update(struct.pack("<fff", float(coordinate.x), float(coordinate.y), float(coordinate.z)))
    finally:
        evaluated.to_mesh_clear()

    points = []
    annotations = atlas.get("annotations", atlas.get("anchors"))
    if not isinstance(annotations, list) or len(annotations) != 20:
        raise ValueError("expected 20 frozen engineering-reference annotations")
    for annotation in annotations:
        face_index = int(annotation["face_index"])
        expected_vertices = [int(value) for value in annotation["vertex_indices"]]
        vertices = polygon_vertices[face_index]
        weights = [float(value) for value in annotation["barycentric"]]
        if vertices != expected_vertices or abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError(f"frozen binding mismatch: {annotation.get('point_id')}")
        local = sum((local_vertices[index] * weight for index, weight in zip(vertices, weights)), Vector())
        surface = sample_surface_binding(target, face_index, weights, depsgraph=depsgraph, expected_vertex_indices=expected_vertices)
        world, normal = Vector(surface.xyz_world_m), Vector(surface.world_normal).normalized()
        projection = project_world_point(scene, camera, world, width=args.width, height=args.height)
        visibility = evaluate_visibility(
            scene=scene, depsgraph=depsgraph, camera=camera, target_object=target,
            point_world=world, world_normal=normal, width=args.width, height=args.height, ray_tolerance_m=1e-4,
        )
        triangle = [local_vertices[index] for index in vertices]
        edges = [float((triangle[1] - triangle[0]).length), float((triangle[2] - triangle[1]).length), float((triangle[0] - triangle[2]).length)]
        area = float((triangle[1] - triangle[0]).cross(triangle[2] - triangle[0]).length * 0.5)
        points.append({
            "point_id": annotation.get("point_id"), "code": annotation.get("code"), "side": annotation.get("side"),
            "face_index": face_index, "vertex_indices": vertices, "barycentric": weights,
            "xyz_body_local_m": list(local), "xyz_world_m": list(surface.xyz_world_m),
            "xyz_camera_opencv_m": projection["xyz_camera_opencv_m"], "uv_pixel_opencv": projection["uv_pixel_opencv"],
            "normal_world": list(normal), "triangle_area_m2": area, "triangle_edge_lengths_m": edges,
            **visibility.to_dict(),
        })
    bed_top = max(float((bed.matrix_world @ Vector(corner)).z) for corner in bed.bound_box)
    clearance = min(float(vertex.z) for vertex in world_vertices) - bed_top
    payload = {
        "schema": "enhanced-skel-pose-case-probe-v1",
        "medical_truth": False,
        "medical_validated": False,
        "profile_id": profile["profile_id"],
        "requested_pose_degrees_46": requested,
        "effective_pose_degrees_46": effective,
        "scene_recorded_pose_degrees_46": recorded,
        "pose_parameter_names_46": list(POSE_NAMES),
        "pose_control_chain_max_error_deg": max_chain_error,
        "pose_control_chain_verified": max_chain_error <= 1e-6,
        "betas": [0.0] * 10,
        "model": {
            "vertex_count": len(local_vertices), "face_count": len(polygon_vertices),
            "topology_signature_sha256": signature,
            "evaluated_local_vertices_float32_sha256": vertex_digest.hexdigest(),
            "matrix_world": matrix_rows(target.matrix_world),
        },
        "camera": {"name": camera.name, "type": camera.type, "matrix_world": matrix_rows(camera.matrix_world)},
        "bed": {"name": bed.name, "type": bed.type, "matrix_world": matrix_rows(bed.matrix_world),
                "top_z_m": bed_top, "minimum_body_clearance_m": clearance, "penetration_depth_m": max(0.0, -clearance)},
        "points": points,
        "visibility_count": sum(bool(point["visible"]) for point in points),
        "self_intersection": {
            "f_gate_connected": False,
            "status": "BLOCKED_PENDING_F_SELF_INTERSECTION_GATE",
            "notice": "This B-line probe does not claim an exact self-intersection result."
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_ENHANCED_POSE_PROBE=PASS")


if __name__ == "__main__":
    main()
