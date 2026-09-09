"""Read-only Official-vs-finetuned evaluation on one VAL or SEALED manifest.

This program never constructs an optimizer and never calls backward. The 2D/3D
joint comparisons are stability proxies against Official predictions, not
ground-truth pose accuracy metrics.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

from surface_metrics import camera_to_world, point_to_triangle, rendered_depth, world_to_camera
from train_rgbd_surface import (aggregate_subject_macro, forward_observation, load_json,
                               sha256_file, subsample, validate_observation)


def validate_evaluation_manifest(manifest: dict, path: Path) -> tuple[str, list[dict]]:
    if manifest.get("final_split_frozen") is not True:
        raise RuntimeError("evaluation subject split is not frozen")
    if manifest.get("evaluation_only") is not True:
        raise RuntimeError("manifest must explicitly declare evaluation_only=true")
    samples = manifest.get("samples", [])
    if not samples:
        raise RuntimeError("evaluation manifest contains no samples")
    splits = {str(row.get("split", "")).upper() for row in samples}
    if len(splits) != 1 or next(iter(splits)) not in {"VAL", "SEALED"}:
        raise RuntimeError("manifest must contain exactly one split: VAL-only or SEALED-only")
    split = next(iter(splits))
    if str(manifest.get("evaluation_split", split)).upper() != split:
        raise RuntimeError("evaluation_split disagrees with sample rows")
    ids, rows = set(), []
    for row in samples:
        sample_id = str(row["id"])
        if sample_id in ids:
            raise RuntimeError(f"duplicate evaluation sample id: {sample_id}")
        ids.add(sample_id)
        observation = Path(row["observation_npz"])
        if not observation.is_absolute():
            observation = (path.parent / observation).resolve()
        if not observation.is_file():
            raise FileNotFoundError(observation)
        expected = row.get("observation_sha256")
        if not expected or sha256_file(observation) != expected:
            raise RuntimeError(f"observation checksum missing or mismatched: {sample_id}")
        validate_observation(observation, "VAL")
        rows.append(dict(row, split=split, resolved_path=observation))
    return split, rows


def cpu_prediction(output: dict) -> dict:
    keys = ("pred_vertices", "pred_cam_t", "pred_keypoints_2d", "pred_keypoints_3d",
            "global_rot", "body_pose")
    return {key: output[key].detach().float().cpu() for key in keys}


def geometry_metrics(prediction: dict, observation: np.lib.npyio.NpzFile,
                     faces: np.ndarray, maximum_points: int, seed: int) -> dict:
    vertices_a = (prediction["pred_vertices"] + prediction["pred_cam_t"][:, None, :])[
        0].numpy()
    vertices_b = world_to_camera(camera_to_world(vertices_a, observation["R_a"],
                                                 observation["T_a"]),
                                 observation["R_b"], observation["T_b"])
    points_b = subsample(observation["points_b"].astype(np.float64), maximum_points, seed)
    triangle = point_to_triangle(points_b, vertices_b, faces)
    depth = rendered_depth(points_b, vertices_b, faces, observation["K_b"],
                           observation["rgb_b"].shape[0], observation["rgb_b"].shape[1])
    if triangle.get("status") == "NO_VALID_OVERLAP" or depth.get("status") == "NO_VALID_OVERLAP":
        raise RuntimeError("evaluation observation has no valid mesh/depth overlap")
    return {"point_to_triangle": triangle, "rendered_depth": depth}


def stability_metrics(official: dict, finetuned: dict, bbox: np.ndarray,
                      pelvis_idx: torch.Tensor) -> dict:
    delta_2d = torch.linalg.vector_norm(
        finetuned["pred_keypoints_2d"] - official["pred_keypoints_2d"], dim=-1)[0].numpy()
    bbox = np.asarray(bbox).reshape(-1)
    # HuMMan cache bbox_a is xyxy, matching prepare_batch's box contract.
    scale = math.sqrt(float(bbox[2] - bbox[0]) * float(bbox[3] - bbox[1]))
    if scale <= 0:
        raise RuntimeError("invalid xyxy bbox for joint stability normalization")
    normalized = delta_2d / scale
    official_3d, finetuned_3d = official["pred_keypoints_3d"], finetuned["pred_keypoints_3d"]
    official_rel = official_3d - official_3d[:, pelvis_idx].mean(1, keepdim=True)
    finetuned_rel = finetuned_3d - finetuned_3d[:, pelvis_idx].mean(1, keepdim=True)
    delta_3d_mm = (torch.linalg.vector_norm(finetuned_rel - official_rel, dim=-1)[0].numpy()
                   * 1000.0)
    global_delta = torch.atan2(torch.sin(finetuned["global_rot"] - official["global_rot"]),
                               torch.cos(finetuned["global_rot"] - official["global_rot"]))
    parameter = {
        "camera_translation_delta_m": float(torch.linalg.vector_norm(
            finetuned["pred_cam_t"] - official["pred_cam_t"])),
        "global_rotation_rms_parameter": float(torch.sqrt(torch.mean(global_delta ** 2))),
        "body_pose_rms_parameter": float(torch.sqrt(torch.mean(
            (finetuned["body_pose"] - official["body_pose"]) ** 2))),
    }
    return {
        "joint_2d_stability_proxy": {
            "bbox_normalization": "sqrt((x2-x1) * (y2-y1)) for cached xyxy bbox",
            "nme": float(normalized.mean()),
            "median_normalized_change": float(np.median(normalized)),
            "p90_normalized_change": float(np.percentile(normalized, 90)),
            "pck05_stability": float((normalized <= 0.05).mean()),
            "meaning": "fraction of MHR70 joints changing by no more than 5% bbox scale",
            "is_ground_truth_accuracy": False,
        },
        "joint_3d_pelvis_relative_stability_proxy": {
            "mean_mm": float(delta_3d_mm.mean()), "median_mm": float(np.median(delta_3d_mm)),
            "p90_mm": float(np.percentile(delta_3d_mm, 90)),
            "p95_mm": float(np.percentile(delta_3d_mm, 95)),
            "is_ground_truth_accuracy": False,
        },
        "parameter_delta_from_official": parameter,
    }


def subject_macro_stability(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["subject_id"], []).append(row)
    subjects = []
    for subject_id, values in sorted(grouped.items()):
        subjects.append({
            "subject_id": subject_id,
            "joint_2d_nme": float(np.median(
                [v["stability"]["joint_2d_stability_proxy"]["nme"] for v in values])),
            "joint_2d_pck05_stability": float(np.median(
                [v["stability"]["joint_2d_stability_proxy"]["pck05_stability"] for v in values])),
            "joint_3d_pelvis_relative_mean_mm": float(np.median(
                [v["stability"]["joint_3d_pelvis_relative_stability_proxy"]["mean_mm"]
                 for v in values])),
            "joint_3d_pelvis_relative_p95_mm": float(np.median(
                [v["stability"]["joint_3d_pelvis_relative_stability_proxy"]["p95_mm"]
                 for v in values])),
        })
    return {
        "subject_count": len(subjects),
        "joint_2d_nme_mean": float(np.mean([v["joint_2d_nme"] for v in subjects])),
        "joint_2d_pck05_stability_mean": float(np.mean(
            [v["joint_2d_pck05_stability"] for v in subjects])),
        "joint_3d_pelvis_relative_mean_mm": float(np.mean(
            [v["joint_3d_pelvis_relative_mean_mm"] for v in subjects])),
        "joint_3d_pelvis_relative_p95_mm_mean": float(np.mean(
            [v["joint_3d_pelvis_relative_p95_mm"] for v in subjects])),
        "subjects": subjects,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--evaluation-manifest", type=Path, required=True)
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--official-checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--finetuned-checkpoint", type=Path, required=True)
    ap.add_argument("--finetuned-checkpoint-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    protocol = load_json(args.protocol)
    split, samples = validate_evaluation_manifest(load_json(args.evaluation_manifest),
                                                  args.evaluation_manifest)
    hashes = {
        "official_checkpoint": sha256_file(args.official_checkpoint),
        "mhr_model": sha256_file(args.mhr),
        "finetuned_checkpoint": sha256_file(args.finetuned_checkpoint),
        "evaluation_manifest": sha256_file(args.evaluation_manifest),
        "protocol": sha256_file(args.protocol),
    }
    if hashes["official_checkpoint"] != protocol["initialization"]["checkpoint_sha256"]:
        raise RuntimeError("Official checkpoint checksum mismatch")
    if hashes["mhr_model"] != protocol["initialization"]["mhr_model_sha256"]:
        raise RuntimeError("MHR asset checksum mismatch")
    if hashes["finetuned_checkpoint"] != args.finetuned_checkpoint_sha256:
        raise RuntimeError("finetuned checkpoint checksum mismatch")

    sys.path.insert(0, str(args.sam_repo.resolve()))
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    started = time.time()
    model, cfg = load_sam_3d_body(str(args.official_checkpoint), device="cuda", mhr_path=str(args.mhr))
    model.eval().requires_grad_(False)
    estimator = SAM3DBodyEstimator(model, cfg)
    faces = model.head_pose.faces.detach().cpu().numpy().astype(np.int64)
    official_predictions = {}
    with torch.inference_mode():
        for row in samples:
            output, _ = forward_observation(model, estimator, prepare_batch, recursive_to,
                                            row["resolved_path"])
            official_predictions[row["id"]] = cpu_prediction(output)

    checkpoint = torch.load(args.finetuned_checkpoint, map_location="cpu", weights_only=False)
    if set(checkpoint.get("heads", {})) != {"pose", "camera"}:
        raise RuntimeError("checkpoint must contain exactly pose and camera heads")
    model.head_pose.proj.load_state_dict(checkpoint["heads"]["pose"], strict=True)
    model.head_camera.proj.load_state_dict(checkpoint["heads"]["camera"], strict=True)
    model.eval().requires_grad_(False)
    rows, official_geometry_rows, finetuned_geometry_rows = [], [], []
    limits = protocol["validation"]["parameter_sanity_limits"]
    with torch.inference_mode():
        for index, row in enumerate(samples):
            output, _ = forward_observation(model, estimator, prepare_batch, recursive_to,
                                            row["resolved_path"])
            finetuned = cpu_prediction(output)
            official = official_predictions[row["id"]]
            with np.load(row["resolved_path"]) as observation:
                official_geometry = geometry_metrics(official, observation, faces,
                    protocol["validation"]["maximum_eval_points"], protocol["seed"] + index)
                finetuned_geometry = geometry_metrics(finetuned, observation, faces,
                    protocol["validation"]["maximum_eval_points"], protocol["seed"] + index)
                stability = stability_metrics(official, finetuned, observation["bbox_a"],
                                              model.pelvis_idx)
            item = {"id": row["id"], "subject_id": row["subject_id"], "split": split,
                    "official": official_geometry, "finetuned": finetuned_geometry,
                    "stability": stability}
            rows.append(item)
            official_geometry_rows.append({"id": row["id"], "subject_id": row["subject_id"],
                                            **official_geometry})
            finetuned_geometry_rows.append({"id": row["id"], "subject_id": row["subject_id"],
                                             **finetuned_geometry})

    official_macro = aggregate_subject_macro(official_geometry_rows)
    finetuned_macro = aggregate_subject_macro(finetuned_geometry_rows)
    geometry_delta = {key: finetuned_macro[key] - official_macro[key]
                      for key in official_macro
                      if key not in {"subjects", "subject_count"}
                      and isinstance(official_macro[key], (int, float))}
    parameter_maxima = {key: max(row["stability"]["parameter_delta_from_official"][key]
                                 for row in rows) for key in limits}
    primary = "point_to_triangle_mean_of_subject_frame_medians_mm"
    result = {
        "status": "COMPLETED_READ_ONLY_OFFICIAL_VS_FINETUNED",
        "evaluation_split": split,
        "sealed_data_accessed": split == "SEALED",
        "optimizer_constructed": False,
        "optimizer_steps": 0,
        "backward_calls": 0,
        "models": {"baseline": "Official SAM 3D Body", "candidate": str(args.finetuned_checkpoint)},
        "geometry_subject_macro": {"official": official_macro, "finetuned": finetuned_macro,
            "finetuned_minus_official": geometry_delta,
            "finetuned_minus_official_primary_mm": finetuned_macro[primary] - official_macro[primary]},
        "joint_stability_subject_macro": subject_macro_stability(rows),
        "joint_stability_interpretation": "2D and pelvis-relative 3D changes are stability proxies against Official predictions, not ground-truth accuracy.",
        "parameter_sanity": {"limits": limits, "maximum_over_evaluation_observations": parameter_maxima,
            "within_all_limits": all(parameter_maxima[key] <= limits[key] for key in limits)},
        "rows": rows,
        "input_sha256": hashes,
        "checkpoint_metadata": {key: checkpoint.get(key) for key in
                                ("status", "epoch", "protocol_sha256", "workset_sha256")},
        "elapsed_seconds": time.time() - started,
        "claim_limit": "This evaluation reports public geometry and Official-relative stability. Joint deltas are not GT accuracy; a SEALED run is a one-time final evaluation, not a tuning signal.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
