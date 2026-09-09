"""Evaluate official SAM and every Visible A/B V2 checkpoint per joint.

This is a read-only postmortem. It does not train, select, or overwrite weights.
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"

import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
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


JOINTS = [
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
MAPPING = [MHR70_TO_OPENPOSE[i] for i in OPENPOSE_TO_COCO][5:17]


def summarize(records, visibility):
    selected = [r for r in records if r["visibility"] in visibility]
    errors = np.asarray([r["normalized_error"] for r in selected], np.float64)
    by_image = {}
    for row in selected:
        by_image.setdefault(row["image"], []).append(row["normalized_error"])
    image_means = np.asarray([np.mean(v) for v in by_image.values()], np.float64)
    return {
        "joint_observations": int(errors.size),
        "images": len(by_image),
        "image_macro_nme": float(image_means.mean()) if image_means.size else None,
        "pooled_nme": float(errors.mean()) if errors.size else None,
        "pck05": float((errors < 0.05).mean()) if errors.size else None,
        "percentiles": {
            f"p{q}": float(np.percentile(errors, q)) if errors.size else None
            for q in [50, 90, 95, 99]
        },
        "bad_tail_threshold": 0.1,
        "bad_tail_count": int((errors >= 0.1).sum()),
        "bad_tail_ratio": float((errors >= 0.1).mean()) if errors.size else None,
    }


def main():
    rows = json.loads((RUN / "samples.json").read_text())
    val = [r for r in rows if r["split"] == "validation"]
    assert len(val) == 82
    assert len({r["image"] for r in val}) == 69
    expected_manifest = hashlib.sha256((RUN / "samples.json").read_bytes()).hexdigest()

    model, cfg = load_sam_3d_body(
        str(P / "weights/model.ckpt"), device="cuda",
        mhr_path=str(P / "weights/assets/mhr_model.pt"),
    )
    model.eval()
    model.requires_grad_(False)
    estimator = SAM3DBodyEstimator(model, cfg)
    initial = {
        "pose": {k: v.detach().cpu().clone() for k, v in model.head_pose.proj.state_dict().items()},
        "camera": {k: v.detach().cpu().clone() for k, v in model.head_camera.proj.state_dict().items()},
    }
    verified = set()

    def predict(row):
        source = IMAGES / row["image"]
        if source not in verified:
            assert hashlib.sha256(source.read_bytes()).hexdigest() == row["source_sha256"]
            verified.add(source)
        rgb = np.asarray(Image.open(source).convert("RGB")).copy()
        batch = prepare_batch(
            rgb, estimator.transform, np.asarray([row["bbox"]], np.float32), None, None
        )
        batch = recursive_to(batch, "cuda")
        batch["cam_int"] = torch.tensor([row["cam_int"]], device="cuda").to(batch["img"])
        model._initialize_batch(batch)
        with torch.no_grad():
            return model.forward_step(batch, decoder_type="body")["mhr"]["pred_keypoints_2d"][0].float().cpu().numpy()

    details = []
    epoch_summaries = []
    for epoch in range(0, 11):
        tag = "official" if epoch == 0 else f"epoch{epoch}"
        if epoch == 0:
            model.head_pose.proj.load_state_dict(initial["pose"])
            model.head_camera.proj.load_state_dict(initial["camera"])
        else:
            checkpoint = torch.load(RUN / f"heads_epoch{epoch}.pt", map_location="cpu", weights_only=False)
            assert checkpoint["epoch"] == epoch
            assert checkpoint["manifest_sha256"] == expected_manifest
            model.head_pose.proj.load_state_dict(checkpoint["heads"]["pose"])
            model.head_camera.proj.load_state_dict(checkpoint["heads"]["camera"])

        started = time.time()
        current = []
        for index, row in enumerate(val):
            prediction = predict(row)[MAPPING]
            annotation = np.asarray(row["coco_annotation"]["keypoints"], np.float64).reshape(17, 3)[5:17]
            normalization = math.sqrt(
                row["coco_annotation"]["bbox"][2] * row["coco_annotation"]["bbox"][3]
            )
            for joint_index, joint_name in enumerate(JOINTS):
                visibility = int(annotation[joint_index, 2])
                if visibility == 0:
                    continue
                current.append({
                    "epoch": epoch,
                    "tag": tag,
                    "id": row["id"],
                    "image": row["image"],
                    "joint": joint_name,
                    "visibility": visibility,
                    "normalized_error": float(
                        np.linalg.norm(prediction[joint_index] - annotation[joint_index, :2]) / normalization
                    ),
                })
            if (index + 1) % 20 == 0:
                print(tag, index + 1, len(val), flush=True)
        details.extend(current)
        per_joint = {}
        for joint in JOINTS:
            joint_rows = [r for r in current if r["joint"] == joint]
            per_joint[joint] = {
                "all_labeled": summarize(joint_rows, {1, 2}),
                "visible_v2": summarize(joint_rows, {2}),
                "labeled_not_visible_v1": summarize(joint_rows, {1}),
            }
        epoch_summaries.append({
            "epoch": epoch,
            "tag": tag,
            "all_labeled": summarize(current, {1, 2}),
            "visible_v2": summarize(current, {2}),
            "labeled_not_visible_v1": summarize(current, {1}),
            "per_joint": per_joint,
            "seconds": time.time() - started,
        })
        (O / "progress.json").write_text(json.dumps(epoch_summaries, indent=2))
        print("DONE", tag, epoch_summaries[-1]["all_labeled"], flush=True)

    output = {
        "status": "COMPLETED_READ_ONLY_POSTMORTEM",
        "contract": {
            "train_manual_visibility": "v=2 only",
            "legacy_primary_evaluation_visibility": "v>0 (v=1 and v=2)",
            "normalization": "Euclidean pixel error / sqrt(COCO annotation bbox area)",
            "aggregation": "image-macro NME; pooled labeled-joint PCK and percentiles",
            "bad_tail": "normalized joint error >= 0.1",
            "selection_warning": "This validation set selected epochs and is not an untouched test.",
        },
        "validation_images": 69,
        "validation_people": 82,
        "epochs": epoch_summaries,
        "details": details,
    }
    (O / "VISIBLE_AB_V2_POSTMORTEM_RAW.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
