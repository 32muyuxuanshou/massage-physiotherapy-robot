"""Measure current V2 loss scales, gradient pathways, and gradient conflicts.

Read-only diagnostic on a deterministic set of training records. No optimizer
step and no checkpoint write are performed.
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

O = Path(__file__).resolve().parent
P = Path("/raid5/xuhd/sam3d_s01_pilot_20260906")
RUN = Path("/raid5/xuhd/nlf_pilot_20260908/visible_ab_v2")
IMAGES = Path("/raid5/xuhd/datasets/coco2014_person_seed20260908/images/train2014")
sys.path.insert(0, str(P / "sam-3d-body"))

from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.metadata import MHR70_TO_OPENPOSE, OPENPOSE_TO_COCO
from sam_3d_body.utils import recursive_to


MAPPING = [MHR70_TO_OPENPOSE[i] for i in OPENPOSE_TO_COCO][5:17]
SLICES = {
    "global_rotation": (0, 6),
    "body_pose": (6, 266),
    "shape": (266, 311),
    "scale_skeleton": (311, 339),
    "hands": (339, 447),
    "face_zeroed": (447, 519),
}


def vectorize(grads, params):
    return torch.cat([
        (g if g is not None else torch.zeros_like(p)).detach().float().flatten()
        for g, p in zip(grads, params)
    ])


def cosine(a, b):
    denom = a.norm() * b.norm()
    return float((a @ b / denom).cpu()) if denom > 0 else None


def main():
    protocol = json.loads((RUN / "protocol.json").read_text())
    rows = json.loads((RUN / "samples.json").read_text())
    eligible = [r for r in rows if r["split"] == "train" and r["manual_eligible"]]
    selected = sorted(
        eligible,
        key=lambda r: hashlib.sha256(("gradient-audit-v1:" + r["id"]).encode()).hexdigest(),
    )[:12]

    model, cfg = load_sam_3d_body(
        str(P / "weights/model.ckpt"), device="cuda",
        mhr_path=str(P / "weights/assets/mhr_model.pt"),
    )
    model.eval()
    model.requires_grad_(False)
    model.head_pose.proj.requires_grad_(True)
    model.head_camera.proj.requires_grad_(True)
    pose_params = list(model.head_pose.proj.parameters())
    camera_params = list(model.head_camera.proj.parameters())
    params = pose_params + camera_params
    estimator = SAM3DBodyEstimator(model, cfg)
    pelvis = model.pelvis_idx
    raw_outputs = []

    def hook(_module, _inputs, output):
        raw_outputs.append(output)

    handle = model.head_pose.proj.register_forward_hook(hook)
    details = []
    try:
        for row in selected:
            source = IMAGES / row["image"]
            assert hashlib.sha256(source.read_bytes()).hexdigest() == row["source_sha256"]
            rgb = np.asarray(Image.open(source).convert("RGB")).copy()
            batch = prepare_batch(
                rgb, estimator.transform, np.asarray([row["bbox"]], np.float32), None, None
            )
            batch = recursive_to(batch, "cuda")
            batch["cam_int"] = torch.tensor([row["cam_int"]], device="cuda").to(batch["img"])
            model._initialize_batch(batch)
            raw_outputs.clear()
            output = model.forward_step(batch, decoder_type="body")["mhr"]

            pred2 = output["pred_keypoints_2d"]
            pred3 = output["pred_keypoints_3d"]
            target2 = pred2.new_tensor(row["keypoints_2d"])[None, :, :2]
            target3 = pred3.new_tensor(row["keypoints_3d"])[None, :, :3]
            target3 = (
                target3 + pred3.new_tensor(row["model_params"][:3]) / 10
            ) * pred3.new_tensor([1, -1, -1])
            size = pred2.new_tensor(row["original_hw"][::-1])
            pred3_relative = pred3 - pred3[:, pelvis].mean(1, keepdim=True)
            target3_relative = target3 - target3[:, pelvis].mean(1, keepdim=True)
            manual = pred2.new_tensor(row["coco_annotation"]["keypoints"]).reshape(17, 3)[5:17]
            visible = manual[:, 2] == 2
            losses = {
                "fitted_2d": F.smooth_l1_loss(pred2 / size, target2 / size),
                "fitted_relative_3d": F.smooth_l1_loss(pred3_relative, target3_relative),
                "manual_visible_2d": F.smooth_l1_loss(
                    pred2[0, MAPPING][visible] / size, manual[visible, :2] / size
                ) * protocol["manual_weight"],
            }
            loss_rows = {}
            vectors = {}
            for name, loss in losses.items():
                param_grads = torch.autograd.grad(
                    loss, params, retain_graph=True, allow_unused=True
                )
                raw_grads = torch.autograd.grad(
                    loss, raw_outputs, retain_graph=True, allow_unused=True
                )
                vector = vectorize(param_grads, params)
                vectors[name] = vector
                raw_norms = {}
                for group, (start, end) in SLICES.items():
                    total = sum(
                        g[..., start:end].float().square().sum()
                        for g in raw_grads if g is not None
                    )
                    raw_norms[group] = float(total.sqrt().cpu())
                pose_vector = vectorize(param_grads[:len(pose_params)], pose_params)
                camera_vector = vectorize(param_grads[len(pose_params):], camera_params)
                loss_rows[name] = {
                    "loss": float(loss.detach().cpu()),
                    "parameter_gradient_norm": float(vector.norm().cpu()),
                    "pose_projection_parameter_gradient_norm": float(pose_vector.norm().cpu()),
                    "camera_projection_parameter_gradient_norm": float(camera_vector.norm().cpu()),
                    "raw_pose_output_gradient_norms": raw_norms,
                }
            details.append({
                "id": row["id"],
                "image": row["image"],
                "visible_manual_joints": int(visible.sum()),
                "losses": loss_rows,
                "gradient_cosine": {
                    "manual_vs_fitted_2d": cosine(vectors["manual_visible_2d"], vectors["fitted_2d"]),
                    "manual_vs_fitted_relative_3d": cosine(vectors["manual_visible_2d"], vectors["fitted_relative_3d"]),
                    "fitted_2d_vs_fitted_relative_3d": cosine(vectors["fitted_2d"], vectors["fitted_relative_3d"]),
                },
            })
            print("DONE", row["id"], flush=True)
    finally:
        handle.remove()

    aggregate = {}
    for loss_name in ["fitted_2d", "fitted_relative_3d", "manual_visible_2d"]:
        fields = [
            "loss", "parameter_gradient_norm",
            "pose_projection_parameter_gradient_norm",
            "camera_projection_parameter_gradient_norm",
        ]
        aggregate[loss_name] = {}
        for field in fields:
            values = np.asarray([r["losses"][loss_name][field] for r in details])
            aggregate[loss_name][field] = {
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "min": float(values.min()),
                "max": float(values.max()),
            }
        aggregate[loss_name]["raw_pose_output_gradient_norm_mean"] = {
            group: float(np.mean([
                r["losses"][loss_name]["raw_pose_output_gradient_norms"][group]
                for r in details
            ]))
            for group in SLICES
        }
    conflict = {}
    for pair in [
        "manual_vs_fitted_2d", "manual_vs_fitted_relative_3d",
        "fitted_2d_vs_fitted_relative_3d",
    ]:
        values = np.asarray([
            r["gradient_cosine"][pair] for r in details
            if r["gradient_cosine"][pair] is not None
        ])
        conflict[pair] = {
            "mean_cosine": float(values.mean()),
            "median_cosine": float(np.median(values)),
            "negative_count": int((values < 0).sum()),
            "sample_count": int(values.size),
        }

    result = {
        "status": "COMPLETED_READ_ONLY_GRADIENT_AUDIT",
        "samples": len(details),
        "sample_selection": "12 deterministic hash-selected eligible training people",
        "checkpoint": "official pretrained initialization",
        "optimizer_steps": 0,
        "manual_weight": protocol["manual_weight"],
        "trainable_parameters": sum(p.numel() for p in params),
        "trainable_modules": ["head_pose.proj", "head_camera.proj"],
        "direct_surface_supervision": False,
        "normalization": {
            "fitted_2d": "pred and target xy divided elementwise by [image width, image height]",
            "manual_visible_2d": "same image width/height normalization; v=2 only",
            "fitted_relative_3d": "pelvis-relative meters, SmoothL1 mean",
        },
        "aggregate": aggregate,
        "gradient_conflict": conflict,
        "details": details,
        "limitations": [
            "Gradient norms are local to 12 selected samples and the official initialization.",
            "Raw pose-output slice norms describe pathways, not independent trainable modules.",
            "A scalar weight of 1 does not equal equal influence because reduction counts, units, and residuals differ.",
        ],
    }
    (O / "LOSS_GRADIENT_AUDIT_V1.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
