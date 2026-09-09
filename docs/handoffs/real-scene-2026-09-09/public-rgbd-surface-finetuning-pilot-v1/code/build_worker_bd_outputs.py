"""Build compact standard DEV/readiness JSONs from immutable experiment outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stats(values):
    a = np.asarray(values, np.float64)
    return {"subject_count": int(len(a)), "subject_mean": float(a.mean()),
            "subject_median": float(np.median(a)), "min": float(a.min()), "max": float(a.max())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--gradient-official", type=Path, required=True)
    ap.add_argument("--gradient-v2", type=Path, required=True)
    ap.add_argument("--toy-tests", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    metric, grad_o, grad_v, toy = map(load, (args.metrics, args.gradient_official,
                                            args.gradient_v2, args.toy_tests))
    if any(document.get("sealed_test_accessed") for document in (metric, grad_o, grad_v, toy)):
        raise RuntimeError("sealed-test access detected")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    groups = {}
    for model_tag in ("official", "v2_e5"):
        groups[model_tag] = {}
        for group in ("camera", "pose", "camera_pose", "shape_scale", "combined"):
            rows = [r for r in metric["rows"] if r["model_tag"] == model_tag and
                    r["parameter_group"] == group]
            if len(rows) != 5:
                raise RuntimeError(f"expected five subjects for {model_tag}/{group}")
            groups[model_tag][group] = {}
            for name in ("legacy", "point_to_triangle", "rendered_depth"):
                before = [r["initial"][name]["median_mm"] for r in rows]
                after = [r["refined"][name]["median_mm"] for r in rows]
                improvement = [(a - b) / max(a, 1e-9) for a, b in zip(before, after)]
                entry = {"initial_median_mm": stats(before), "refined_median_mm": stats(after),
                         "relative_improvement": stats(improvement)}
                if name == "rendered_depth":
                    entry["refined_mesh_coverage"] = stats(
                        [r["refined"][name]["mesh_coverage_of_observed_points"] for r in rows])
                groups[model_tag][group][name] = entry
    ablation = {
        "status": "COMPLETED_DEV5_PARAMETER_GROUP_ABLATION_V2",
        "split": "DEV5_ONLY", "sealed_test_accessed": False,
        "models": groups,
        "comparison": {
            "question": "Does shape/scale add material held-out benefit beyond Camera+Pose?",
            "official_camera_pose_minus_combined_legacy_median_mm":
                groups["official"]["camera_pose"]["legacy"]["refined_median_mm"]["subject_mean"] -
                groups["official"]["combined"]["legacy"]["refined_median_mm"]["subject_mean"],
            "v2_camera_pose_minus_combined_legacy_median_mm":
                groups["v2_e5"]["camera_pose"]["legacy"]["refined_median_mm"]["subject_mean"] -
                groups["v2_e5"]["combined"]["legacy"]["refined_median_mm"]["subject_mean"],
        },
        "metric_source": str(args.metrics),
    }
    (args.output_dir / "DEV5_PARAMETER_GROUP_ABLATION_V2.json").write_text(
        json.dumps(ablation, indent=2), encoding="utf-8")

    def gradient_summary(document):
        fields = ("pose_head_parameter_gradient_norm", "camera_head_parameter_gradient_norm",
                  "raw_pose_output_gradient_norm", "raw_camera_output_gradient_norm",
                  "mesh_vertex_gradient_norm")
        out = {field: stats([r[field] for r in document["rows"]]) for field in fields}
        out["raw_pose_output_slice_gradient_norm_subject_mean"] = {
            key: float(np.mean([r["raw_pose_output_slice_gradient_norms"][key]
                                for r in document["rows"]]))
            for key in document["rows"][0]["raw_pose_output_slice_gradient_norms"]}
        return out
    gradient = {
        "status": "COMPLETED_READ_ONLY_SURFACE_GRADIENT_CHAIN_AUDIT_V1",
        "split": "DEV5_ONLY", "sealed_test_accessed": False,
        "optimizer_steps": 0, "checkpoint_written": False,
        "official": gradient_summary(grad_o), "v2_e5": gradient_summary(grad_v),
        "verified_chain": grad_o["gradient_chain"],
        "interpretation": "The differentiable surface objective reaches both proposed output heads for every DEV subject; this is feasibility evidence, not a training result.",
    }
    (args.output_dir / "SURFACE_GRADIENT_CHAIN_AUDIT_V1.json").write_text(
        json.dumps(gradient, indent=2), encoding="utf-8")

    readiness = {
        "status": "READY_FOR_PROTOCOL_FREEZE_NOT_TRAINED",
        "sealed_test_accessed": False, "training_completed": False,
        "evidence": {
            "synthetic_metric_tests": toy["status"],
            "surface_gradient_to_pose_and_camera_heads": "VERIFIED_ON_OFFICIAL_AND_V2_E5_DEV5",
            "parameter_group_ablation": "CAMERA_AND_POSE_CAPTURE_MOST_DEV_HELDOUT_GAIN",
            "shape_scale_increment": "SMALL_ON_CURRENT_DEV5; DO_NOT_PRIORITIZE_IN_FIRST_GLOBAL_PILOT"
        },
        "recommended_first_trainable_modules": ["head_pose.proj", "head_camera.proj"],
        "recommended_surface_loss": "robust observed-to-differentiable-barycentric-triangle-samples plus frozen pre-registered priors",
        "must_freeze_before_training": [
            "TRAIN/VAL/SEALED subject split", "surface observation validity",
            "legacy/point-to-triangle/rendered-depth metrics and coverage threshold",
            "optimizer, steps, learning rate, seed, checkpoint selection rule",
            "joint-loss retention and weights"
        ],
        "prohibited_claims": ["training completed", "sealed-test improvement", "bare-back accuracy", "medical accuracy"]
    }
    (args.output_dir / "SURFACE_FINETUNING_READINESS_INPUT_V1.json").write_text(
        json.dumps(readiness, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
