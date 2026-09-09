"""Read-only audit: DEV Camera-A surface loss -> SAM pose/camera output heads.

No optimizer is constructed, no parameter is changed, and no Camera-B/sealed-test
key is read. The loss uses differentiable barycentric samples of MHR triangles.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch


POSE_SLICES = {
    "global_rotation_6d": (0, 6), "body_continuous": (6, 266),
    "shape": (266, 311), "scale_skeleton": (311, 339),
    "hands": (339, 447), "face_zeroed": (447, 519),
}


def norm_or_none(gradient: torch.Tensor | None) -> float | None:
    return None if gradient is None else float(torch.linalg.vector_norm(gradient.float()).cpu())


def parameter_group_norm(gradients, reference_parameters) -> float:
    terms = [(g if g is not None else torch.zeros_like(p)).float().square().sum()
             for g, p in zip(gradients, reference_parameters)]
    return float(torch.sqrt(torch.stack(terms).sum()).cpu())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--prepared-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model-tag", choices=("official", "v2_e5"), required=True)
    ap.add_argument("--v2-heads", type=Path)
    ap.add_argument("--observed-samples", type=int, default=1024)
    ap.add_argument("--triangle-samples", type=int, default=4096)
    ap.add_argument("--huber-delta-m", type=float, default=0.03)
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()
    if (args.model_tag == "v2_e5") != (args.v2_heads is not None):
        raise ValueError("--v2-heads required exactly for v2_e5")
    sys.path.insert(0, str(args.sam_repo.resolve()))
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to

    model, cfg = load_sam_3d_body(str(args.checkpoint), device="cuda", mhr_path=str(args.mhr))
    model.eval().requires_grad_(False)
    if args.v2_heads:
        state = torch.load(args.v2_heads, map_location="cpu", weights_only=False)
        model.head_pose.proj.load_state_dict(state["heads"]["pose"], strict=True)
        model.head_camera.proj.load_state_dict(state["heads"]["camera"], strict=True)
    model.head_pose.proj.requires_grad_(True)
    model.head_camera.proj.requires_grad_(True)
    trainable = list(model.head_pose.proj.parameters()) + list(model.head_camera.proj.parameters())
    estimator = SAM3DBodyEstimator(model, cfg)
    faces = model.head_pose.faces.detach().long()
    observations = sorted(args.prepared_dir.glob("*.npz"))
    if len(observations) != 5:
        raise RuntimeError(f"DEV audit requires exactly 5 observations, found {len(observations)}")
    rows = []
    for index, path in enumerate(observations):
        data = np.load(path)
        # Deliberately access only Camera A keys.
        rgb, bbox, K = data["rgb_a"], data["bbox_a"], data["K_a"]
        points = data["points_a"]
        rng = np.random.default_rng(args.seed + index)
        point_ids = rng.choice(len(points), min(len(points), args.observed_samples), replace=False)
        face_ids_np = rng.choice(len(faces), min(len(faces), args.triangle_samples), replace=False)
        bary = rng.dirichlet(np.ones(3), len(face_ids_np)).astype(np.float32)
        observed = torch.as_tensor(points[point_ids], device="cuda", dtype=torch.float32)
        face_ids = torch.as_tensor(face_ids_np, device="cuda", dtype=torch.long)
        bary_t = torch.as_tensor(bary, device="cuda")
        batch = prepare_batch(rgb, estimator.transform, bbox[None].astype(np.float32), None, None)
        batch = recursive_to(batch, "cuda")
        batch["cam_int"] = torch.as_tensor(K[None], device="cuda").to(batch["img"])
        pose_raw, camera_raw = [], []
        hp = model.head_pose.proj.register_forward_hook(lambda _m, _i, o: pose_raw.append(o))
        hc = model.head_camera.proj.register_forward_hook(lambda _m, _i, o: camera_raw.append(o))
        try:
            model._initialize_batch(batch)
            output = model.forward_step(batch, decoder_type="body")["mhr"]
        finally:
            hp.remove(); hc.remove()
        vertices = output["pred_vertices"] + output["pred_cam_t"][:, None, :]
        sampled_surface = (vertices[:, faces[face_ids]] * bary_t[None, :, :, None]).sum(2)
        distance = torch.cdist(observed[None], sampled_surface).amin(-1)[0]
        delta = args.huber_delta_m
        loss = torch.where(distance < delta, 0.5 * distance.square() / delta,
                           distance - 0.5 * delta).mean()
        targets = trainable + [pose_raw[-1], camera_raw[-1], vertices]
        grads = torch.autograd.grad(loss, targets, allow_unused=True)
        n_params = len(trainable)
        pose_grad, camera_grad, vertex_grad = grads[n_params:]
        pose_slice_norms = {}
        for name, (start, end) in POSE_SLICES.items():
            pose_slice_norms[name] = norm_or_none(
                None if pose_grad is None else pose_grad[..., start:end])
        pose_parameters = list(model.head_pose.proj.parameters())
        camera_parameters = list(model.head_camera.proj.parameters())
        pose_param_grads = grads[:len(pose_parameters)]
        camera_param_grads = grads[len(pose_param_grads):n_params]
        rows.append({
            "observation_id": path.stem, "loss_m": float(loss.detach().cpu()),
            "observed_samples": int(len(point_ids)), "triangle_surface_samples": int(len(face_ids_np)),
            "pose_head_parameter_gradient_norm": parameter_group_norm(pose_param_grads, pose_parameters),
            "camera_head_parameter_gradient_norm": parameter_group_norm(camera_param_grads, camera_parameters),
            "raw_pose_output_gradient_norm": norm_or_none(pose_grad),
            "raw_camera_output_gradient_norm": norm_or_none(camera_grad),
            "mesh_vertex_gradient_norm": norm_or_none(vertex_grad),
            "raw_pose_output_slice_gradient_norms": pose_slice_norms,
        })
        print("DONE", path.stem, flush=True)
    result = {
        "status": "COMPLETED_READ_ONLY_DEV5_SURFACE_GRADIENT_AUDIT",
        "model_tag": args.model_tag, "split": "DEV5_ONLY", "sealed_test_accessed": False,
        "optimizer_steps": 0, "checkpoint_written": False,
        "trainable_modules_during_audit": ["head_pose.proj", "head_camera.proj"],
        "trainable_parameter_count": int(sum(p.numel() for p in trainable)),
        "surface_loss": "robust observed-point to differentiable barycentric MHR triangle samples",
        "gradient_chain": "loss -> sampled triangle points -> MHR vertices/pred_cam_t -> raw pose/camera outputs -> projection head weights",
        "limitations": [
            "This proves a nonzero local gradient path; it does not prove optimization will generalize.",
            "Triangle sampling approximates the continuous surface training loss and is not the exact evaluation metric.",
            "The audit performs no optimizer step and is not a training run.",
        ],
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
