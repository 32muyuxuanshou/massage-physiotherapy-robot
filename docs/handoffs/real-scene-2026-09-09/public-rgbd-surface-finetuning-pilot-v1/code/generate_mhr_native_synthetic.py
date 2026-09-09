#!/usr/bin/env python3
"""Generate an exact-replayable RGB/Z-depth dataset from the real MHR model.

This is a geometry smoke generator. It does not run SAM inference and does not
train any network. Shape/scale are shared by identity; pose/camera vary by view.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import numpy as np
import torch
from PIL import Image


SCHEMA = "mhr-native-synthetic-v1"
AXIS_MHR_TO_OPENCV = np.array([1.0, -1.0, -1.0], dtype=np.float32)
BODY_HAND_PARAMETER_SLICE = slice(62, 116)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(value: np.ndarray) -> str:
    value = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
    digest.update(value.tobytes())
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sample_rng(master_seed: int, identity_index: int, view_index: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([master_seed, identity_index, view_index]))


def clipped_normal(rng: np.random.Generator, size: int, sigma: float, limit: float) -> np.ndarray:
    return np.clip(rng.normal(0.0, sigma, size), -limit, limit).astype(np.float32)


def identity_parameters(master_seed: int, identity_index: int) -> tuple[np.ndarray, np.ndarray, int]:
    seed = int(np.random.SeedSequence([master_seed, identity_index, 0x1D]).generate_state(1)[0])
    rng = np.random.default_rng(seed)
    shape = clipped_normal(rng, 45, sigma=0.65, limit=2.0)
    scale = clipped_normal(rng, 28, sigma=0.30, limit=1.25)
    return shape, scale, seed


def identity_split(identity_index: int, identity_count: int) -> str:
    train_end = int(identity_count * 0.8)
    validation_end = int(identity_count * 0.9)
    if identity_index < train_end:
        return "train"
    if identity_index < validation_end:
        return "validation"
    return "test"


def instance_parameters(
    master_seed: int,
    identity_index: int,
    view_index: int,
    shape: np.ndarray,
    scale: np.ndarray,
) -> tuple[dict[str, np.ndarray], int]:
    rng = sample_rng(master_seed, identity_index, view_index)
    seed = int(np.random.SeedSequence([master_seed, identity_index, view_index]).generate_state(1)[0])
    body_pose = np.zeros(133, dtype=np.float32)
    body_pose[:124] = clipped_normal(rng, 124, sigma=0.11, limit=0.32)
    body_pose[BODY_HAND_PARAMETER_SLICE] = 0.0
    body_pose[124:130] = 0.0
    body_pose[130:133] = 0.0
    params = {
        "global_trans": np.zeros(3, dtype=np.float32),
        "global_rot": clipped_normal(rng, 3, sigma=0.12, limit=0.30),
        "body_pose_params": body_pose,
        "hand_pose_params": clipped_normal(rng, 108, sigma=0.07, limit=0.22),
        "scale_params": scale.copy(),
        "shape_params": shape.copy(),
        "expr_params": np.zeros(72, dtype=np.float32),
    }
    return params, seed


def look_at_opencv(center: np.ndarray, azimuth: float, elevation: float, distance: float, roll: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera_center = center + distance * np.array(
        [math.sin(azimuth) * math.cos(elevation), -math.sin(elevation), -math.cos(azimuth) * math.cos(elevation)],
        dtype=np.float64,
    )
    forward = center.astype(np.float64) - camera_center
    forward /= np.linalg.norm(forward)
    up_world = np.array([0.0, -1.0, 0.0], dtype=np.float64)
    right = np.cross(forward, up_world)
    if np.linalg.norm(right) < 1e-6:
        up_world = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        right = np.cross(forward, up_world)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        right, down = c * right + s * down, -s * right + c * down
    rotation = np.stack([right, down, forward]).astype(np.float32)
    translation = (-rotation @ camera_center.astype(np.float32)).astype(np.float32)
    return rotation, translation, camera_center.astype(np.float32)


def choose_camera(vertices: np.ndarray, rng: np.random.Generator, width: int, height: int) -> dict:
    center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
    radius = float(np.linalg.norm(vertices - center, axis=1).max())
    fx = float(rng.uniform(620.0, 820.0) * width / 512.0)
    fy = float(fx * rng.uniform(0.985, 1.015))
    cx = float(width * 0.5 + rng.uniform(-0.025, 0.025) * width)
    cy = float(height * 0.5 + rng.uniform(-0.025, 0.025) * height)
    half_fov = min(math.atan(width / (2.0 * fx)), math.atan(height / (2.0 * fy)))
    distance = max(2.2, radius / max(math.sin(half_fov) * 0.78, 0.1))
    azimuth = math.radians(float(rng.uniform(-180.0, 180.0)))
    elevation = math.radians(float(rng.uniform(-25.0, 25.0)))
    roll = math.radians(float(rng.uniform(-5.0, 5.0)))
    rotation, translation, camera_center = look_at_opencv(center, azimuth, elevation, distance, roll)
    return {
        "K": np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float32),
        "R_camera_from_mhr_opencv": rotation,
        "T_camera_from_mhr_opencv_m": translation,
        "camera_center_mhr_opencv_m": camera_center,
        "azimuth_deg": math.degrees(azimuth),
        "elevation_deg": math.degrees(elevation),
        "roll_deg": math.degrees(roll),
        "distance_m": distance,
        "width": width,
        "height": height,
    }


def to_camera(points: np.ndarray, camera: dict) -> np.ndarray:
    return points @ camera["R_camera_from_mhr_opencv"].T + camera["T_camera_from_mhr_opencv_m"]


def render_rgb_depth(vertices_camera: np.ndarray, faces: np.ndarray, camera: dict, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import pyrender
    import trimesh

    vertices_gl = vertices_camera * AXIS_MHR_TO_OPENCV
    material_color = np.r_[rng.uniform(0.42, 0.88, 3), 1.0]
    material = pyrender.MetallicRoughnessMaterial(
        metallicFactor=0.0,
        roughnessFactor=0.78,
        alphaMode="OPAQUE",
        baseColorFactor=material_color,
    )
    tri = trimesh.Trimesh(vertices=vertices_gl, faces=faces, process=False)
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.34, 0.34, 0.34])
    scene.add(pyrender.Mesh.from_trimesh(tri, material=material, smooth=True))
    K = camera["K"]
    cam = pyrender.IntrinsicsCamera(
        fx=float(K[0, 0]), fy=float(K[1, 1]), cx=float(K[0, 2]), cy=float(K[1, 2]), znear=0.05, zfar=20.0
    )
    scene.add(cam, pose=np.eye(4, dtype=np.float32))
    light = pyrender.DirectionalLight(color=np.ones(3), intensity=2.4)
    scene.add(light, pose=np.eye(4, dtype=np.float32))
    renderer = pyrender.OffscreenRenderer(camera["width"], camera["height"])
    color_rgba, depth = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
    renderer.delete()
    depth = depth.astype(np.float32)
    mask = depth > 0.0
    yy, xx = np.mgrid[: camera["height"], : camera["width"]]
    c0, c1 = rng.integers(15, 90, 3), rng.integers(100, 210, 3)
    alpha = ((xx / max(camera["width"] - 1, 1)) * 0.55 + (yy / max(camera["height"] - 1, 1)) * 0.45)[..., None]
    background = ((1.0 - alpha) * c0 + alpha * c1).astype(np.uint8)
    rgb = background
    rgb[mask] = color_rgba[..., :3][mask]
    return rgb, depth, (mask.astype(np.uint8) * 255)


def project_keypoints(points_camera: np.ndarray, depth: np.ndarray, K: np.ndarray, tolerance_m: float = 0.08) -> dict[str, np.ndarray]:
    z = points_camera[:, 2]
    uv = np.full((len(points_camera), 2), np.nan, dtype=np.float32)
    positive = z > 0.0
    uv[positive, 0] = K[0, 0] * points_camera[positive, 0] / z[positive] + K[0, 2]
    uv[positive, 1] = K[1, 1] * points_camera[positive, 1] / z[positive] + K[1, 2]
    ui = np.rint(uv[:, 0]).astype(np.int64, casting="unsafe")
    vi = np.rint(uv[:, 1]).astype(np.int64, casting="unsafe")
    inside = positive & (ui >= 0) & (ui < depth.shape[1]) & (vi >= 0) & (vi < depth.shape[0])
    observed = np.zeros(len(points_camera), dtype=np.float32)
    observed[inside] = depth[vi[inside], ui[inside]]
    visible = inside & (observed > 0.0) & (z <= observed + tolerance_m)
    return {"uv": uv, "depth_at_pixel_m": observed, "visible": visible, "in_frame": inside}


def load_mhr(sam_repo: Path, checkpoint: Path, mhr_path: Path, device: str):
    sys.path.insert(0, str(sam_repo.resolve()))
    from sam_3d_body import load_sam_3d_body

    model, _ = load_sam_3d_body(str(checkpoint), device=device, mhr_path=str(mhr_path))
    model.eval().requires_grad_(False)
    return model


@torch.no_grad()
def mhr_forward(model, params: dict[str, np.ndarray], device: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = {key: torch.as_tensor(value[None], dtype=torch.float32, device=device) for key, value in params.items()}
    vertices, keypoints, joints = model.head_pose.mhr_forward(
        global_trans=values["global_trans"],
        global_rot=values["global_rot"],
        body_pose_params=values["body_pose_params"],
        hand_pose_params=values["hand_pose_params"],
        scale_params=values["scale_params"],
        shape_params=values["shape_params"],
        expr_params=values["expr_params"],
        return_keypoints=True,
        return_joint_coords=True,
    )
    sign = torch.tensor(AXIS_MHR_TO_OPENCV, device=device)
    return tuple((item[0] * sign).float().cpu().numpy() for item in (vertices, keypoints, joints))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam-repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--mhr", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identity-count", type=int, default=10)
    parser.add_argument("--samples-per-identity", type=int, default=10)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--master-seed", type=int, default=2026090903)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output}")
    args.output.mkdir(parents=True)
    (args.output / "samples").mkdir()

    torch.manual_seed(args.master_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.master_seed)
    model = load_mhr(args.sam_repo, args.checkpoint, args.mhr, args.device)
    faces = model.head_pose.faces.detach().cpu().numpy().astype(np.int32)
    if faces.shape != (36874, 3):
        raise RuntimeError(f"Unexpected MHR topology {faces.shape}")
    np.save(args.output / "topology_faces.npy", faces, allow_pickle=False)
    topology_hash = array_sha256(faces)
    model_hash = file_sha256(args.mhr)
    records = []
    for identity_index in range(args.identity_count):
        shape, scale, identity_seed = identity_parameters(args.master_seed, identity_index)
        for view_index in range(args.samples_per_identity):
            sample_index = identity_index * args.samples_per_identity + view_index
            sample_id = f"mhr_{sample_index:06d}"
            sample_dir = args.output / "samples" / sample_id
            sample_dir.mkdir()
            params, seed = instance_parameters(args.master_seed, identity_index, view_index, shape, scale)
            vertices, keypoints, joints = mhr_forward(model, params, args.device)
            rng = sample_rng(args.master_seed, identity_index, view_index)
            camera = choose_camera(vertices, rng, args.width, args.height)
            vertices_camera = to_camera(vertices, camera).astype(np.float32)
            keypoints_camera = to_camera(keypoints, camera).astype(np.float32)
            joints_camera = to_camera(joints, camera).astype(np.float32)
            if float(vertices_camera[:, 2].min()) <= 0.05:
                raise RuntimeError(f"{sample_id}: mesh crosses near plane")
            rgb, depth, mask = render_rgb_depth(vertices_camera, faces, camera, rng)
            if int((mask > 0).sum()) < 1000:
                raise RuntimeError(f"{sample_id}: rendered foreground too small")
            projection = project_keypoints(keypoints_camera, depth, camera["K"])

            np.savez(sample_dir / "params.npz", **params)
            np.save(sample_dir / "vertices_camera_m.npy", vertices_camera, allow_pickle=False)
            np.save(sample_dir / "keypoints_mhr308_camera_m.npy", keypoints_camera, allow_pickle=False)
            np.save(sample_dir / "joints127_camera_m.npy", joints_camera, allow_pickle=False)
            np.savez(sample_dir / "keypoints_mhr308_projection.npz", **projection)
            np.save(sample_dir / "depth_z_m.npy", depth, allow_pickle=False)
            Image.fromarray(rgb, mode="RGB").save(sample_dir / "rgb.png")
            Image.fromarray(mask, mode="L").save(sample_dir / "mask.png")
            preview_mm = np.clip(depth * 1000.0, 0, 65535).astype(np.uint16)
            Image.fromarray(preview_mm, mode="I;16").save(sample_dir / "depth_mm.png")
            camera_json = {
                "convention": "OpenCV +x right, +y down, +z forward; X_camera = R @ X_mhr_opencv + T",
                "raster_sample_coordinates": "OpenGL fragment centre (column+0.5, row+0.5) for pyrender depth",
                "depth_definition": "metric camera Z-depth",
                "depth_unit": "metres in depth_z_m.npy; rounded millimetres in depth_mm.png",
                **{key: value.tolist() if isinstance(value, np.ndarray) else value for key, value in camera.items()},
            }
            write_json(sample_dir / "camera.json", camera_json)
            artifact_names = [
                "params.npz", "vertices_camera_m.npy", "keypoints_mhr308_camera_m.npy",
                "joints127_camera_m.npy", "keypoints_mhr308_projection.npz", "depth_z_m.npy",
                "rgb.png", "mask.png", "depth_mm.png", "camera.json",
            ]
            artifacts = {name: file_sha256(sample_dir / name) for name in artifact_names}
            record = {
                "schema": SCHEMA,
                "sample_id": sample_id,
                "identity_id": f"identity_{identity_index:04d}",
                "identity_index": identity_index,
                "identity_disjoint_split": identity_split(identity_index, args.identity_count),
                "view_index": view_index,
                "master_seed": args.master_seed,
                "identity_seed": identity_seed,
                "sample_seed": seed,
                "mhr_model_sha256": model_hash,
                "topology_faces_array_sha256": topology_hash,
                "vertex_count": int(vertices_camera.shape[0]),
                "face_count": int(faces.shape[0]),
                "vertices_array_sha256": array_sha256(vertices_camera),
                "foreground_pixel_count": int((mask > 0).sum()),
                "visible_mhr70_count": int(projection["visible"][:70].sum()),
                "parameter_shapes": {key: list(value.shape) for key, value in params.items()},
                "artifacts": artifacts,
            }
            write_json(sample_dir / "sample.json", record)
            record["artifacts"]["sample.json"] = file_sha256(sample_dir / "sample.json")
            records.append(record)
            print(f"{sample_index + 1}/{args.identity_count * args.samples_per_identity} {sample_id}", flush=True)

    root = {
        "schema": SCHEMA,
        "status": "GENERATED_PENDING_INDEPENDENT_VALIDATION",
        "sample_count": len(records),
        "identity_count": args.identity_count,
        "samples_per_identity": args.samples_per_identity,
        "identity_split_rule": "first 80% train, next 10% validation, final 10% test; no identity crosses a split",
        "master_seed": args.master_seed,
        "mhr_model_sha256": model_hash,
        "topology_faces_array_sha256": topology_hash,
        "topology_file_sha256": file_sha256(args.output / "topology_faces.npy"),
        "mhr_parameter_dimensions": {
            "global_trans": 3, "global_rot": 3, "body_pose_params": 133,
            "hand_pose_params": 108, "scale_params": 28, "shape_params": 45, "expr_params": 72,
        },
        "sampling_claim": "bounded engineering coverage only; not a learned natural-pose distribution",
        "records": records,
    }
    write_json(args.output / "dataset_manifest.json", root)
    print(json.dumps({"output": str(args.output), "sample_count": len(records), "status": root["status"]}))


if __name__ == "__main__":
    main()
