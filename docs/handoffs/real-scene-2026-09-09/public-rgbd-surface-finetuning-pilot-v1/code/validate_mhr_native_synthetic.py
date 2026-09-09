#!/usr/bin/env python3
"""Independently validate MHR params->mesh and mesh->depth->backprojection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from generate_mhr_native_synthetic import array_sha256, file_sha256, load_mhr, mhr_forward


PARAM_REPLAY_MAX_M = 1.0e-6
RAY_SURFACE_MAX_M = 5.0e-3
REPROJECTION_MAX_PX = 1.0e-5


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    def convert(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"Cannot JSON-encode {type(item).__name__}")

    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=convert) + "\n", encoding="utf-8")


def camera_arrays(camera: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(camera["K"], dtype=np.float32),
        np.asarray(camera["R_camera_from_mhr_opencv"], dtype=np.float32),
        np.asarray(camera["T_camera_from_mhr_opencv_m"], dtype=np.float32),
    )


def to_camera(points: np.ndarray, camera: dict) -> np.ndarray:
    _, rotation, translation = camera_arrays(camera)
    return points @ rotation.T + translation


def choose_interior_pixels(mask: np.ndarray, depth: np.ndarray, count: int, seed: int) -> np.ndarray:
    try:
        import cv2

        mask_u8 = mask.astype(np.uint8)
        interior = cv2.erode(mask_u8, np.ones((7, 7), np.uint8), iterations=1) > 0
        # Exclude internal z-buffer boundaries (e.g. arm crossing torso), not only
        # the outer silhouette. Continuous surfaces remain in the sampling pool.
        local_max = cv2.dilate(depth, np.ones((3, 3), np.uint8))
        local_min = cv2.erode(depth, np.ones((3, 3), np.uint8))
        interior &= (local_max - local_min) < 0.03
    except ImportError:
        interior = mask.copy()
    pixels = np.argwhere(interior)
    if len(pixels) < count:
        pixels = np.argwhere(mask)
    rng = np.random.default_rng(seed)
    chosen = pixels if len(pixels) <= count else pixels[rng.choice(len(pixels), count, replace=False)]
    return chosen.astype(np.int64)


def ray_mesh_depth(vertices: np.ndarray, faces: np.ndarray, u: int, v: int, K: np.ndarray) -> float:
    """Return nearest triangle intersection Z for one OpenCV pinhole ray."""
    # pyrender/OpenGL evaluates the fragment at the pixel-square centre.
    sample_u, sample_v = u + 0.5, v + 0.5
    direction = np.array([(sample_u - K[0, 2]) / K[0, 0], (sample_v - K[1, 2]) / K[1, 1], 1.0], dtype=np.float64)
    triangles = vertices[faces].astype(np.float64)
    v0 = triangles[:, 0]
    edge1 = triangles[:, 1] - v0
    edge2 = triangles[:, 2] - v0
    h = np.cross(np.broadcast_to(direction, edge2.shape), edge2)
    a = np.einsum("ij,ij->i", edge1, h)
    # Match OpenGL's default back-face culling. In OpenCV camera coordinates,
    # outward front-face normals oppose the +Z camera ray, yielding a > 0.
    valid = a > 1.0e-10
    f = np.zeros_like(a)
    f[valid] = 1.0 / a[valid]
    s = -v0
    bary_u = f * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, edge1)
    bary_v = f * np.einsum("ij,j->i", q, direction)
    t = f * np.einsum("ij,ij->i", edge2, q)
    hit = valid & (bary_u >= -1.0e-7) & (bary_v >= -1.0e-7) & ((bary_u + bary_v) <= 1.0 + 1.0e-7) & (t > 0.0)
    return float(t[hit].min()) if np.any(hit) else float("nan")


def backproject_and_reproject(pixels_vu: np.ndarray, depth: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, float]:
    v = pixels_vu[:, 0].astype(np.float64) + 0.5
    u = pixels_vu[:, 1].astype(np.float64) + 0.5
    z = depth[pixels_vu[:, 0], pixels_vu[:, 1]].astype(np.float64)
    points = np.stack([(u - K[0, 2]) * z / K[0, 0], (v - K[1, 2]) * z / K[1, 1], z], axis=1)
    projected = np.stack([K[0, 0] * points[:, 0] / points[:, 2] + K[0, 2], K[1, 1] * points[:, 1] / points[:, 2] + K[1, 2]], axis=1)
    expected = np.stack([u, v], axis=1)
    return points, float(np.abs(projected - expected).max(initial=0.0))


def validate_sample(model, root: Path, record: dict, faces: np.ndarray, device: str, rays_per_sample: int) -> dict:
    sample_dir = root / "samples" / record["sample_id"]
    artifact_hashes = {
        name: file_sha256(sample_dir / name) == expected
        for name, expected in record["artifacts"].items()
    }
    params_npz = np.load(sample_dir / "params.npz")
    params = {key: params_npz[key] for key in params_npz.files}
    replay_vertices, replay_keypoints, replay_joints = mhr_forward(model, params, device)
    camera = read_json(sample_dir / "camera.json")
    replay_vertices = to_camera(replay_vertices, camera).astype(np.float32)
    replay_keypoints = to_camera(replay_keypoints, camera).astype(np.float32)
    replay_joints = to_camera(replay_joints, camera).astype(np.float32)
    stored_vertices = np.load(sample_dir / "vertices_camera_m.npy")
    stored_keypoints = np.load(sample_dir / "keypoints_mhr308_camera_m.npy")
    stored_joints = np.load(sample_dir / "joints127_camera_m.npy")
    replay_deltas = {
        "vertices_max_abs_m": float(np.max(np.abs(replay_vertices - stored_vertices))),
        "keypoints_max_abs_m": float(np.max(np.abs(replay_keypoints - stored_keypoints))),
        "joints_max_abs_m": float(np.max(np.abs(replay_joints - stored_joints))),
    }
    depth = np.load(sample_dir / "depth_z_m.npy")
    mask = np.asarray(Image.open(sample_dir / "mask.png")) > 0
    rgb = np.asarray(Image.open(sample_dir / "rgb.png"))
    depth_mm = np.asarray(Image.open(sample_dir / "depth_mm.png"))
    K, _, _ = camera_arrays(camera)
    pixels = choose_interior_pixels(mask, depth, rays_per_sample, record["sample_seed"] ^ 0x51A7)
    points, reprojection_max_px = backproject_and_reproject(pixels, depth, K)
    ray_z = np.array([ray_mesh_depth(stored_vertices, faces, int(u), int(v), K) for v, u in pixels])
    raster_z = depth[pixels[:, 0], pixels[:, 1]].astype(np.float64)
    ray_valid = np.isfinite(ray_z)
    ray_error = np.abs(ray_z[ray_valid] - raster_z[ray_valid])
    ray_error_3d = ray_error * np.linalg.norm(points[ray_valid] / points[ray_valid, 2:3], axis=1)
    ray_max_m = float(ray_error_3d.max()) if len(ray_error_3d) else float("inf")
    checks = {
        "all_artifact_hashes": all(artifact_hashes.values()),
        "topology_hash": array_sha256(faces) == record["topology_faces_array_sha256"],
        "stored_vertices_hash": array_sha256(stored_vertices) == record["vertices_array_sha256"],
        "parameter_replay": max(replay_deltas.values()) <= PARAM_REPLAY_MAX_M,
        "depth_mask_identity": np.array_equal(mask, depth > 0.0),
        "depth_mm_rounding": np.max(np.abs(depth_mm.astype(np.float64) - np.clip(depth * 1000.0, 0, 65535).astype(np.uint16))) == 0,
        "rgb_shape": tuple(rgb.shape) == (camera["height"], camera["width"], 3),
        "finite_positive_depth": bool(np.all(np.isfinite(depth[mask])) and np.all(depth[mask] > 0.0)),
        "ray_intersection_count": int(ray_valid.sum()) == len(pixels),
        "mesh_depth_surface": bool(len(ray_error_3d) == len(pixels) and ray_max_m <= RAY_SURFACE_MAX_M),
        "backprojection_reprojection": reprojection_max_px <= REPROJECTION_MAX_PX,
    }
    return {
        "sample_id": record["sample_id"],
        "identity_id": record["identity_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "artifact_hashes": artifact_hashes,
        "parameter_replay": replay_deltas,
        "ray_samples": len(pixels),
        "ray_intersections": int(ray_valid.sum()),
        "mesh_depth_backprojection_max_m": ray_max_m,
        "mesh_depth_backprojection_p95_m": float(np.percentile(ray_error_3d, 95)) if len(ray_error_3d) else None,
        "backprojection_reprojection_max_px": reprojection_max_px,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam-repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--mhr", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--rays-per-sample", type=int, default=16)
    args = parser.parse_args()

    manifest = read_json(args.dataset / "dataset_manifest.json")
    faces = np.load(args.dataset / "topology_faces.npy")
    model = load_mhr(args.sam_repo, args.checkpoint, args.mhr, args.device)
    if file_sha256(args.mhr) != manifest["mhr_model_sha256"]:
        raise RuntimeError("MHR model hash differs from the generator manifest")
    results = []
    for index, record in enumerate(manifest["records"]):
        result = validate_sample(model, args.dataset, record, faces, args.device, args.rays_per_sample)
        results.append(result)
        print(f"{index + 1}/{len(manifest['records'])} {result['sample_id']} {'PASS' if result['passed'] else 'FAIL'}", flush=True)

    sample_ids = [record["sample_id"] for record in manifest["records"]]
    sample_seeds = [record["sample_seed"] for record in manifest["records"]]
    identities: dict[str, list[dict]] = {}
    for record in manifest["records"]:
        identities.setdefault(record["identity_id"], []).append(record)
    identity_shared = True
    split_disjoint = True
    for records in identities.values():
        reference = np.load(args.dataset / "samples" / records[0]["sample_id"] / "params.npz")
        splits = {record.get("identity_disjoint_split") for record in records}
        split_disjoint &= len(splits) == 1
        for record in records[1:]:
            params = np.load(args.dataset / "samples" / record["sample_id"] / "params.npz")
            identity_shared &= np.array_equal(reference["shape_params"], params["shape_params"])
            identity_shared &= np.array_equal(reference["scale_params"], params["scale_params"])
    dataset_checks = {
        "manifest_sample_count": len(results) == manifest["sample_count"],
        "unique_sample_ids": len(sample_ids) == len(set(sample_ids)),
        "unique_sample_seeds": len(sample_seeds) == len(set(sample_seeds)),
        "identity_count": len(identities) == manifest["identity_count"],
        "shape_scale_shared_within_identity": identity_shared,
        "identity_split_disjoint": split_disjoint,
        "topology_file_hash": file_sha256(args.dataset / "topology_faces.npy") == manifest["topology_file_sha256"],
    }
    passed = all(dataset_checks.values()) and all(item["passed"] for item in results)
    report = {
        "schema": "mhr-native-synthetic-validation-v1",
        "status": "PASS" if passed else "FAIL_DO_NOT_USE",
        "passed": passed,
        "sample_count": len(results),
        "pass_count": sum(item["passed"] for item in results),
        "fail_count": sum(not item["passed"] for item in results),
        "identity_count": manifest["identity_count"],
        "dataset_checks": dataset_checks,
        "thresholds": {
            "parameter_replay_max_m": PARAM_REPLAY_MAX_M,
            "mesh_depth_backprojection_max_m": RAY_SURFACE_MAX_M,
            "backprojection_reprojection_max_px": REPROJECTION_MAX_PX,
        },
        "aggregate": {
            "parameter_replay_max_abs_m": max(max(item["parameter_replay"].values()) for item in results),
            "mesh_depth_backprojection_max_m": max(item["mesh_depth_backprojection_max_m"] for item in results),
            "mesh_depth_backprojection_p95_of_sample_p95_m": float(np.percentile([item["mesh_depth_backprojection_p95_m"] for item in results], 95)),
            "backprojection_reprojection_max_px": max(item["backprojection_reprojection_max_px"] for item in results),
        },
        "claim_limit": "Validates generator replay and synthetic rendering geometry only. It does not validate pose realism, real-image transfer, bare-back geometry or medical labels.",
        "samples": results,
    }
    write_json(args.output, report)
    print(json.dumps({"output": str(args.output), "status": report["status"], "sample_count": len(results)}))
    if not passed:
        sys.exit(2)


if __name__ == "__main__":
    main()
