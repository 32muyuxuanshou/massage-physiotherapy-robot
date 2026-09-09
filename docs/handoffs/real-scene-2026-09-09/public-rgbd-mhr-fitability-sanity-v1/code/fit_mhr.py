"""Frozen-network, per-frame MHR parameter-group fit against Camera A depth.

Camera B is loaded only after optimizer.step has finished. The primary metric is
therefore a genuinely held-out, observed-depth-to-MHR distance. vertex_offsets is
never passed to MHR and is deliberately unavailable as a CLI option.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch


GROUPS = {
    "camera": ("camera",),
    "pose": ("global_rot", "body_pose"),
    "shape_scale": ("shape", "scale"),
    "combined": ("camera", "global_rot", "body_pose", "shape", "scale"),
}
SANITY_LIMITS = {
    "camera_translation_delta_m": 0.50,
    "global_rotation_rms_rad": 0.75,
    "body_pose_rms_parameter": 0.75,
    "shape_rms_coefficient": 3.0,
    "scale_rms_coefficient": 3.0,
}


def choose_indices(n: int, maximum: int, seed: int) -> np.ndarray:
    if n <= maximum:
        return np.arange(n)
    return np.random.default_rng(seed).choice(n, maximum, replace=False)


def nearest_distances(query: np.ndarray, reference: np.ndarray) -> np.ndarray:
    try:
        from scipy.spatial import cKDTree
        return cKDTree(reference).query(query, workers=-1)[0]
    except ImportError:
        chunks = []
        for start in range(0, len(query), 1024):
            q = query[start:start + 1024]
            chunks.append(np.sqrt(((q[:, None] - reference[None]) ** 2).sum(-1).min(1)))
        return np.concatenate(chunks)


def metrics(observed: np.ndarray, vertices: np.ndarray, max_points: int, seed: int) -> dict:
    sampled = observed[choose_indices(len(observed), max_points, seed)]
    d = nearest_distances(sampled.astype(np.float64), vertices.astype(np.float64)) * 1000.0
    return {"direction": "observed_visible_surface_to_full_MHR_surface",
            "sample_count": int(len(d)), "mean_mm": float(d.mean()),
            "median_mm": float(np.median(d)), "p90_mm": float(np.percentile(d, 90)),
            "p95_mm": float(np.percentile(d, 95)), "max_mm": float(d.max())}


def camera_to_world(points: np.ndarray, R: np.ndarray, T: np.ndarray) -> np.ndarray:
    return (points - T) @ R


def world_to_camera(points: np.ndarray, R: np.ndarray, T: np.ndarray) -> np.ndarray:
    return points @ R.T + T


def delta_rms(after: torch.Tensor, before: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean((after.detach() - before) ** 2)).cpu())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--observation", type=Path, required=True)
    ap.add_argument("--prediction", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--group", choices=tuple(GROUPS), required=True)
    ap.add_argument("--model-tag", required=True)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--surface-samples", type=int, default=2048)
    ap.add_argument("--mesh-samples", type=int, default=4096)
    ap.add_argument("--max-eval-points", type=int, default=100000)
    ap.add_argument("--huber-delta-m", type=float, default=0.03)
    ap.add_argument("--prior-weight", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()
    if args.steps <= 0:
        raise ValueError("steps must be positive")

    sys.path.insert(0, str(args.sam_repo.resolve()))
    from sam_3d_body import load_sam_3d_body
    model, _ = load_sam_3d_body(str(args.checkpoint), device="cuda", mhr_path=str(args.mhr))
    model.eval().requires_grad_(False)
    assert sum(p.numel() for p in model.parameters() if p.requires_grad) == 0

    raw = np.load(args.prediction)
    obs = np.load(args.observation)
    device = torch.device("cuda")
    initial = {
        "camera": torch.as_tensor(raw["pred_cam_t"], dtype=torch.float32, device=device).reshape(1, 3),
        "global_rot": torch.as_tensor(raw["global_rot"], dtype=torch.float32, device=device).reshape(1, -1),
        "body_pose": torch.as_tensor(raw["body_pose_params"], dtype=torch.float32, device=device).reshape(1, -1),
        "hand": torch.as_tensor(raw["hand_pose_params"], dtype=torch.float32, device=device).reshape(1, -1),
        "scale": torch.as_tensor(raw["scale_params"], dtype=torch.float32, device=device).reshape(1, -1),
        "shape": torch.as_tensor(raw["shape_params"], dtype=torch.float32, device=device).reshape(1, -1),
        "face": torch.as_tensor(raw["expr_params"], dtype=torch.float32, device=device).reshape(1, -1),
    }
    current = {key: value.detach().clone() for key, value in initial.items()}
    for key in GROUPS[args.group]:
        current[key].requires_grad_(True)
    optimizer = torch.optim.Adam([current[k] for k in GROUPS[args.group]], lr=args.lr)

    def vertices_camera() -> torch.Tensor:
        # MHR wrapper convention: raw model output is metres, then Y/Z are flipped.
        vertices = model.head_pose.mhr_forward(
            global_trans=torch.zeros_like(current["global_rot"]),
            global_rot=current["global_rot"], body_pose_params=current["body_pose"],
            hand_pose_params=current["hand"], scale_params=current["scale"],
            shape_params=current["shape"], expr_params=current["face"])
        sign = torch.tensor([1.0, -1.0, -1.0], device=device)
        return vertices * sign + current["camera"][:, None, :]

    with torch.no_grad():
        regenerated = vertices_camera()[0].cpu().numpy()
    cached = raw["pred_vertices"].reshape(-1, 3) + raw["pred_cam_t"].reshape(1, 3)
    regeneration_max_delta_m = float(np.max(np.abs(regenerated - cached)))
    if regeneration_max_delta_m > 1e-4:
        raise RuntimeError(f"cached/direct MHR mismatch {regeneration_max_delta_m:.6g} m")

    points_a_np = obs["points_a"].astype(np.float32)
    point_idx = choose_indices(len(points_a_np), args.surface_samples, args.seed)
    points_a = torch.as_tensor(points_a_np[point_idx], device=device)
    mesh_count = regenerated.shape[0]
    mesh_idx = torch.as_tensor(choose_indices(mesh_count, args.mesh_samples, args.seed + 1),
                               dtype=torch.long, device=device)
    history = []
    first_step_gradient_norms = {}
    for step in range(args.steps):
        optimizer.zero_grad(set_to_none=True)
        mesh = vertices_camera()[0, mesh_idx]
        nearest = torch.cdist(points_a[None], mesh[None]).amin(dim=-1)[0]
        delta = args.huber_delta_m
        surface = torch.where(nearest < delta, 0.5 * nearest.square() / delta,
                              nearest - 0.5 * delta).mean()
        prior = torch.zeros((), device=device)
        prior_scales = {"camera": 0.10, "global_rot": 0.25, "body_pose": 0.25,
                        "shape": 1.0, "scale": 1.0}
        for key in GROUPS[args.group]:
            prior = prior + ((current[key] - initial[key]) / prior_scales[key]).square().mean()
        loss = surface + args.prior_weight * prior
        loss.backward()
        if step == 0:
            for key in GROUPS[args.group]:
                grad = current[key].grad
                if grad is None or not torch.isfinite(grad).all() or not torch.any(grad != 0):
                    raise RuntimeError(f"{key} has no finite non-zero MHR fitting gradient")
                first_step_gradient_norms[key] = float(torch.linalg.vector_norm(grad).detach().cpu())
        optimizer.step()
        if step == 0 or (step + 1) % 10 == 0 or step + 1 == args.steps:
            history.append({"step": step + 1, "loss_m": float(loss.detach().cpu()),
                            "surface_huber_m": float(surface.detach().cpu()),
                            "prior": float(prior.detach().cpu())})

    with torch.no_grad():
        refined_a = vertices_camera()[0].cpu().numpy()
    initial_a = regenerated
    initial_world = camera_to_world(initial_a, obs["R_a"], obs["T_a"])
    refined_world = camera_to_world(refined_a, obs["R_a"], obs["T_a"])
    initial_b = world_to_camera(initial_world, obs["R_b"], obs["T_b"])
    refined_b = world_to_camera(refined_world, obs["R_b"], obs["T_b"])

    deltas = {
        "camera_translation_delta_m": float(torch.linalg.vector_norm(
            current["camera"] - initial["camera"]).detach().cpu()),
        "global_rotation_rms_rad": delta_rms(current["global_rot"], initial["global_rot"]),
        "body_pose_rms_parameter": delta_rms(current["body_pose"], initial["body_pose"]),
        "shape_rms_coefficient": delta_rms(current["shape"], initial["shape"]),
        "scale_rms_coefficient": delta_rms(current["scale"], initial["scale"]),
    }
    sanity = {"pre_registered_limits": SANITY_LIMITS, "deltas": deltas,
              "within_all_limits": all(deltas[k] <= SANITY_LIMITS[k] for k in SANITY_LIMITS)}
    result = {
        "status": "COMPLETED_FROZEN_PER_FRAME_FIT", "model_tag": args.model_tag,
        "observation_id": args.observation.stem,
        "subject_id": args.observation.stem.split("_a", 1)[0],
        "group": args.group, "camera_a_role": "fit", "camera_b_role": "held_out_evaluation_only",
        "network_trainable_parameter_count": 0, "vertex_offsets": "DISABLED_AND_NOT_PASSED",
        "regeneration_max_delta_m": regeneration_max_delta_m,
        "loss": {"surface": "one-sided observed-to-subsampled-MHR robust point-to-point",
                 "reason": "Kinect depth normals and silhouette boundaries are noisy; point-to-plane is deferred",
                 "huber_delta_m": args.huber_delta_m, "prior_weight": args.prior_weight,
                 "fit_surface_samples": len(point_idx), "fit_mesh_samples": len(mesh_idx)},
        "optimization": {"steps": args.steps, "lr": args.lr, "seed": args.seed,
                         "first_step_gradient_norms": first_step_gradient_norms, "history": history},
        "metrics": {
            "camera_a_fit_view": {"initial": metrics(obs["points_a"], initial_a, args.max_eval_points, args.seed + 2),
                                  "refined": metrics(obs["points_a"], refined_a, args.max_eval_points, args.seed + 2)},
            "camera_b_held_out": {"initial": metrics(obs["points_b"], initial_b, args.max_eval_points, args.seed + 3),
                                  "refined": metrics(obs["points_b"], refined_b, args.max_eval_points, args.seed + 3)},
        },
        "parameter_sanity": sanity,
        "interpretation_limit": "person-mask sensor depth measures clothed/person surface, not bare-back skin",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    np.savez_compressed(args.output.with_suffix(".npz"), vertices_camera_a=refined_a,
                        vertices_camera_b=refined_b,
                        **{f"after_{k}": v.detach().cpu().numpy() for k, v in current.items()},
                        **{f"before_{k}": v.detach().cpu().numpy() for k, v in initial.items()})


if __name__ == "__main__":
    main()
