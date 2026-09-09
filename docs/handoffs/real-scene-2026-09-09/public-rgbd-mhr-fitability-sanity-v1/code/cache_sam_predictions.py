"""Cache frozen Official or V2-E5 SAM 3D Body predictions for prepared RGB A."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch


PARAMETER_KEYS = ("pred_cam_t", "global_rot", "body_pose_params", "hand_pose_params",
                  "scale_params", "shape_params", "expr_params", "pred_vertices")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--prepared-manifest", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--model-tag", choices=("official", "v2_e5"), required=True)
    ap.add_argument("--v2-heads", type=Path,
                    help="required for v2_e5; checkpoint containing heads.pose and heads.camera")
    args = ap.parse_args()
    if (args.model_tag == "v2_e5") != (args.v2_heads is not None):
        raise ValueError("--v2-heads is required exactly when --model-tag=v2_e5")
    sys.path.insert(0, str(args.sam_repo.resolve()))
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body

    model, cfg = load_sam_3d_body(str(args.checkpoint), device="cuda", mhr_path=str(args.mhr))
    model.eval().requires_grad_(False)
    if args.v2_heads:
        state = torch.load(args.v2_heads, map_location="cpu", weights_only=False)
        model.head_pose.proj.load_state_dict(state["heads"]["pose"], strict=True)
        model.head_camera.proj.load_state_dict(state["heads"]["camera"], strict=True)
    estimator = SAM3DBodyEstimator(model, cfg)
    manifest = json.loads(args.prepared_manifest.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for row in manifest["observations"]:
        obs = np.load(row["observation_npz"])
        prediction = estimator.process_one_image(
            obs["rgb_a"], bboxes=obs["bbox_a"][None],
            cam_int=torch.from_numpy(obs["K_a"][None]).float(), inference_type="body")[0]
        out = args.output_dir / f"{row['id']}__{args.model_tag}.npz"
        np.savez_compressed(out, **{k: np.asarray(prediction[k]) for k in PARAMETER_KEYS})
        outputs.append({"id": row["id"], "model_tag": args.model_tag,
                        "prediction_npz": str(out.resolve()), "sha256": sha256(out)})
    record = {
        "status": "FROZEN_INFERENCE_CACHED", "model_tag": args.model_tag,
        "network_trainable_parameter_count": 0,
        "checkpoint": {"path": str(args.checkpoint.resolve()), "sha256": sha256(args.checkpoint)},
        "mhr": {"path": str(args.mhr.resolve()), "sha256": sha256(args.mhr)},
        "v2_heads": None if not args.v2_heads else {"path": str(args.v2_heads.resolve()),
                                                       "sha256": sha256(args.v2_heads)},
        "predictions": outputs,
    }
    (args.output_dir / f"predictions_{args.model_tag}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
