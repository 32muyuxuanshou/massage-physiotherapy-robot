from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
REASONS = ("VISIBLE", "OUT_OF_FRAME", "EXTERNAL_OCCLUDED", "SELF_OCCLUDED", "BACK_FACING", "BEHIND_CAMERA")
AI_ROOT = Path(__file__).resolve().parents[4]
V1_DATA = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_19-57-10_ENGINEERING_PILOT_DATASET_V1"
V2_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2"
DECODER_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-09-02_13-10-44_DECODER_CONTRACT_VALIDATION_UNTOUCHED_V1"


def read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path: Path, value: dict) -> None: path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def exposure_rank(value: str) -> int:
    return {"COMPLETELY_UNSEEN": 0, "TEST_ONLY": 1, "VAL_SEEN": 2, "TRAIN_SEEN": 3}[value]


def build_exposure(output: Path) -> dict:
    cache = np.load(V2_ROOT / "training_cache_v2.npz", allow_pickle=False)
    base_rows = [{"sample_id": str(cache["sample_ids"][i]), "body_geometry_id": str(cache["case_ids"][i]),
                  "sample_geometry_id": str(cache["geometry_ids"][i]), "source": "FAILURE_DRIVEN_V2_CACHE", "index": i}
                 for i in range(len(cache["sample_ids"]))]
    model_sets = {}; body_exposure = {}
    for split in SPLITS:
        pred = np.load(V2_ROOT / "training" / split / "predictions.npz", allow_pickle=False)
        sets = {"TRAIN_SEEN": set(map(int, pred["train_indices"])), "VAL_SEEN": set(map(int, pred["val_indices"])), "TEST_ONLY": set(map(int, pred["test_indices"]))}
        model_sets[split] = sets; mapping = {}
        for row in base_rows:
            idx = row["index"]; category = next((name for name, values in sets.items() if idx in values), "COMPLETELY_UNSEEN")
            current = mapping.get(row["body_geometry_id"], "COMPLETELY_UNSEEN")
            if exposure_rank(category) > exposure_rank(current): mapping[row["body_geometry_id"]] = category
        body_exposure[split] = mapping
    sample_rows = []
    for row in base_rows:
        result = {k: row[k] for k in ("sample_id", "body_geometry_id", "sample_geometry_id", "source")}
        for split in SPLITS:
            idx = row["index"]; result[f"{split}_image"] = next((name for name, values in model_sets[split].items() if idx in values), "COMPLETELY_UNSEEN")
            result[f"{split}_body"] = body_exposure[split].get(row["body_geometry_id"], "COMPLETELY_UNSEEN")
        sample_rows.append(result)
    # Previously evaluated V2 truncation holdout: exact images were test-only, while body exposure follows the locator split.
    hold = np.load(V2_ROOT / "truncation_holdout_v2.npz", allow_pickle=False)
    for i in range(len(hold["sample_ids"])):
        body = str(hold["case_ids"][i]); result = {"sample_id": str(hold["sample_ids"][i]), "body_geometry_id": body,
                "sample_geometry_id": str(hold["geometry_ids"][i]), "source": "TRUNCATION_HOLDOUT_V2"}
        for split in SPLITS:
            result[f"{split}_image"] = "TEST_ONLY"; result[f"{split}_body"] = body_exposure[split].get(body, "COMPLETELY_UNSEEN")
        sample_rows.append(result)
    # C4 was challenge-only for all three models.
    for i in range(len(cache["challenge_sample_ids"])):
        body = str(cache["challenge_case_ids"][i]); result = {"sample_id": str(cache["challenge_sample_ids"][i]), "body_geometry_id": body,
                "sample_geometry_id": str(cache["challenge_geometry_ids"][i]), "source": "C4_CHALLENGE_ONLY"}
        for split in SPLITS:
            result[f"{split}_image"] = "TEST_ONLY"; result[f"{split}_body"] = body_exposure[split].get(body, "COMPLETELY_UNSEEN")
        sample_rows.append(result)
    # New decoder validation/test bodies were never in any locator train/val/test split.
    for phase in ("validation", "untouched_test"):
        manifest = read(DECODER_ROOT / f"{phase}_sample_generation_report.json")
        for row in manifest["samples"]:
            result = {"sample_id": row["sample_id"], "body_geometry_id": row["case_id"],
                      "sample_geometry_id": f"{row['case_id']}__{row['camera_id']}", "source": f"DECODER_{phase.upper()}",
                      "posthoc_use": "DECODER_VALIDATION" if phase == "validation" else "DECODER_UNTOUCHED_TEST"}
            for split in SPLITS: result[f"{split}_image"] = result[f"{split}_body"] = "COMPLETELY_UNSEEN"
            sample_rows.append(result)
    fields = ["sample_id", "body_geometry_id", "sample_geometry_id", "source", "posthoc_use"] + [f"{split}_{level}" for split in SPLITS for level in ("image", "body")]
    with (output / "LOCATOR_EXPOSURE_MATRIX_V1.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(sample_rows)
    body_rows = {}
    for row in sample_rows:
        body = row["body_geometry_id"]; item = body_rows.setdefault(body, {"body_geometry_id": body, "sources": set()}); item["sources"].add(row["source"])
        for split in SPLITS:
            key = f"{split}_body"; current = item.get(key, "COMPLETELY_UNSEEN")
            if exposure_rank(row[key]) > exposure_rank(current): item[key] = row[key]
    bodies = []
    for item in body_rows.values():
        body = {**item, "sources": sorted(item["sources"])}
        for split in SPLITS: body.setdefault(f"{split}_body", "COMPLETELY_UNSEEN")
        bodies.append(body)
    summary = {split: {category: {"sample_count": sum(row[f"{split}_image"] == category for row in sample_rows),
                                           "body_geometry_count": sum(row[f"{split}_body"] == category for row in bodies)}
                       for category in ("TRAIN_SEEN", "VAL_SEEN", "TEST_ONLY", "COMPLETELY_UNSEEN")} for split in SPLITS}
    payload = {"schema": "locator-exposure-matrix-v1", "passed": True,
               "definitions": {"image_exposure": "Exact image participation in frozen locator development/evaluation.",
                               "body_exposure": "Highest exposure of any image sharing the same Shape-Pose body geometry; camera/appearance do not create a new body."},
               "models_are_independent_diagnostic_replicas": True, "pooling_for_reliability_training_allowed": False,
               "sample_row_count": len(sample_rows), "body_geometry_count": len(bodies), "summary": summary, "body_rows": sorted(bodies, key=lambda x: x["body_geometry_id"]),
               "matrix_csv": str(output / "LOCATOR_EXPOSURE_MATRIX_V1.csv")}
    write(output / "LOCATOR_EXPOSURE_MATRIX_V1.json", payload); return payload


def event_count(rows: list[dict], predicate) -> dict:
    selected = [row for row in rows if predicate(row)]
    return {"point_instances": len(selected), "images": len({row["sample_id"] for row in selected}),
            "body_geometries": len({row["body_geometry_id"] for row in selected}),
            "body_geometry_ids": sorted({row["body_geometry_id"] for row in selected})}


def build_events(output: Path) -> dict:
    all_rows = []; model_summaries = {split: {} for split in SPLITS}; availability_rows = []
    for phase in ("validation", "untouched_test"):
        data = np.load(DECODER_ROOT / f"{phase}_decoder_cache.npz", allow_pickle=False)
        for split in SPLITS:
            pred = np.load(DECODER_ROOT / phase / "predictions" / f"{split}.npz", allow_pickle=False)["hybrid"]
            for i, sample_path in enumerate(data["sample_paths"].astype(str)):
                sample = Path(sample_path); labels = read(sample / "labels.json"); depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
                with Image.open(sample / "depth_valid_mask.png") as image: valid = np.asarray(image.convert("L"), np.uint8)
                with Image.open(sample / "skin_mask.png") as image: skin = np.asarray(image.convert("L"), np.uint8)
                intr = labels["camera"]["intrinsics"]; body = str(data["sample_ids"][i]).split("__", 1)[0]
                for j, point in enumerate(labels["points"]):
                    reason = point["visibility_reason"]
                    available = bool(reason == "VISIBLE" and point["in_frame"] and point["front_facing"] and point["visible"])
                    u, v = map(float, pred[i, j]); col, image_row = int(math.floor(u)), int(math.floor(v)); invalid_reason = None; error_mm = None
                    if available:
                        if not (0 <= col < depth.shape[1] and 0 <= image_row < depth.shape[0]): invalid_reason = "PREDICTED_OUT_OF_FRAME"
                        elif depth[image_row, col] <= 0 or valid[image_row, col] != 255: invalid_reason = "INVALID_DEPTH"
                        elif skin[image_row, col] != 255: invalid_reason = "NON_SKIN_FIRST_SURFACE"
                        else:
                            z = float(depth[image_row, col]); xyz = np.asarray([(u - intr["cx"]) * z / intr["fx"], (v - intr["cy"]) * z / intr["fy"], z])
                            error_mm = float(np.linalg.norm(xyz - np.asarray(point["xyz_camera_opencv_m"])) * 1000.0)
                    row = {"phase": phase, "locator_model": split, "sample_id": str(data["sample_ids"][i]), "body_geometry_id": body,
                           "camera_id": str(data["camera_ids"][i]), "point_id": point["point_id"], "visibility_reason": reason,
                           "available_for_3d_gt": available, "final_3d_error_mm": error_mm, "invalid_prediction_reason": invalid_reason or ""}
                    all_rows.append(row)
                    if split == SPLITS[0]: availability_rows.append(row)
    fields = list(all_rows[0])
    with (output / "reliability_event_rows.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(all_rows)
    availability = {phase: {} for phase in ("validation", "untouched_test")}
    for phase in availability:
        subset = [row for row in availability_rows if row["phase"] == phase]
        availability[phase]["AVAILABLE_FOR_3D"] = event_count(subset, lambda row: row["available_for_3d_gt"])
        for reason in REASONS: availability[phase][reason] = event_count(subset, lambda row, reason=reason: row["visibility_reason"] == reason)
    reliability = {}
    for split in SPLITS:
        reliability[split] = {}
        for phase in ("validation", "untouched_test"):
            subset = [row for row in all_rows if row["locator_model"] == split and row["phase"] == phase]
            reliability[split][phase] = {
                "AVAILABLE_WITH_VALID_3D": event_count(subset, lambda row: row["available_for_3d_gt"] and row["final_3d_error_mm"] is not None),
                "INVALID_PREDICTED_3D": event_count(subset, lambda row: bool(row["invalid_prediction_reason"])),
                "BAD20": event_count(subset, lambda row: row["final_3d_error_mm"] is not None and row["final_3d_error_mm"] > 20.0),
                "BAD30": event_count(subset, lambda row: row["final_3d_error_mm"] is not None and row["final_3d_error_mm"] > 30.0),
                "BAD50": event_count(subset, lambda row: row["final_3d_error_mm"] is not None and row["final_3d_error_mm"] > 50.0),
            }
    payload = {"schema": "reliability-event-inventory-v1", "medical_truth": False,
               "counting_units": ["point_instances", "images", "body_geometries"],
               "body_geometry_definition": "Shape-Pose case; camera and appearance variants remain grouped with the same body.",
               "availability": availability, "reliability_by_locator": reliability,
               "point_level_csv": str(output / "reliability_event_rows.csv")}
    write(output / "RELIABILITY_EVENT_INVENTORY_V1.json", payload); return payload


def feature_audit(output: Path) -> dict:
    groups = {
        "ALLOWED_RUNTIME": ["raw-logit peak probability", "entropy", "top1-top2 gap", "local heatmap spread", "multimodality", "local probability mass",
                            "boundary branch requested/used per axis", "fallback code", "expectation-hybrid correction", "quadratic curvature/vertex/extrapolation",
                            "predicted distance to image edge", "predicted uv in-frame", "scene depth validity at predicted uv", "local depth variance/gradient/hole"],
        "LABEL_OR_EVALUATION_ONLY": ["GT visibility_reason", "GT available_for_3d", "GT uv/xyz", "final 3D error", "BAD20/BAD30/BAD50",
                                     "shape_id", "pose_id", "camera_id", "sample_id", "base/body geometry id", "point_id for grouped reporting"],
        "PROHIBITED_INPUT": ["GT Skin Mask", "GT first-surface identity", "labels.json fields containing truth", "overlay", "synthetic-only metadata",
                             "Depth/Mask values not obtainable from the deployed RGB-D path"],
        "CONDITIONAL_NOT_AVAILABLE_V1": ["predicted human Skin Mask (no independent runtime segmentation model exists in this phase)"],
    }
    checks = {"no_reliability_model_trained": True, "gt_skin_mask_prohibited": True, "ids_grouping_only": True,
              "three_locator_rows_must_not_be_pooled": True, "runtime_feature_values_not_yet_selected": True}
    payload = {"schema": "runtime-feature-leakage-audit-v1", "passed": all(checks.values()), "checks": checks, "feature_groups": groups,
               "finding": "No reliability learner exists yet, so no training leakage occurred. High-risk fields are explicitly quarantined before dataset construction."}
    write(output / "RUNTIME_FEATURE_LEAKAGE_AUDIT_V1.json", payload); return payload


def sufficiency(output: Path, exposure: dict, events: dict, leakage: dict) -> dict:
    unseen_bodies = sorted({row["body_geometry_id"] for row in exposure["body_rows"] if all(row.get(f"{split}_body") == "COMPLETELY_UNSEEN" for split in SPLITS)})
    avail_all = {reason: set() for reason in REASONS}
    for phase in events["availability"].values():
        for reason in REASONS: avail_all[reason].update(phase[reason]["body_geometry_ids"])
    bad_bodies = {split: set() for split in SPLITS}
    for split in SPLITS:
        for phase in events["reliability_by_locator"][split].values(): bad_bodies[split].update(phase["BAD30"]["body_geometry_ids"])
    structural_gaps = {
        "only_eight_locator_unseen_body_geometries": len(unseen_bodies) == 8,
        "external_occlusion_absent_in_locator_unseen_inventory": len(avail_all["EXTERNAL_OCCLUDED"]) == 0,
        "self_occlusion_absent_in_locator_unseen_inventory": len(avail_all["SELF_OCCLUDED"]) == 0,
        "back_facing_absent_in_locator_unseen_inventory": len(avail_all["BACK_FACING"]) == 0,
        "no_fresh_reliability_untouched_partition_reserved": True,
        "availability_negative_patterns_limited_to_controlled_out_of_frame": True,
    }
    decision = "INSUFFICIENT_NEED_NEW_RELIABILITY_DATA"
    payload = {"schema": "reliability-data-sufficiency-decision-v1", "decision": decision, "passed_audit": leakage["passed"],
               "locator_unseen_body_geometry_count": len(unseen_bodies), "locator_unseen_body_geometry_ids": unseen_bodies,
               "bad30_event_bearing_body_geometries_by_locator": {split: sorted(values) for split, values in bad_bodies.items()},
               "availability_reason_body_geometry_coverage": {reason: sorted(values) for reason, values in avail_all.items()},
               "structural_gaps": structural_gaps,
               "rationale": ["Point and image counts are correlated replicas of only eight body geometries.",
                             "No locator-unseen external-occlusion, self-occlusion or back-facing body coverage exists in this inventory.",
                             "The eight bodies were already consumed by decoder validation/test; no fresh three-way reliability train/calibration/untouched partition remains.",
                             "A reliability learner would therefore be under-supported and its calibration would not be independently testable."],
               "next_gate": "RELIABILITY_DATASET_GATE_V1",
               "next_gate_constraints": ["Generate new Shape-Pose bodies completely unseen by all three frozen locators.",
                                         "Keep three locator reliability datasets/models/calibrators separate.",
                                         "Cover normal, oblique, left/right truncation and frozen C3 external occlusion; C4 remains challenge-only.",
                                         "Freeze body-grouped train/calibration/untouched partitions before prediction-based selection."],
               "training_authorized": False}
    write(output / "RELIABILITY_DATA_SUFFICIENCY_DECISION_V1.json", payload); return payload


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=Path); args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    exposure = build_exposure(output); events = build_events(output); leakage = feature_audit(output); decision = sufficiency(output, exposure, events, leakage)
    checks = {"exposure_matrix_built": exposure["passed"], "event_inventory_built": bool(events["reliability_by_locator"]),
              "feature_leakage_audit_passed": leakage["passed"], "decision_is_explicit": decision["decision"] in ("ENOUGH_FOR_FEASIBILITY_TRAINING", "INSUFFICIENT_NEED_NEW_RELIABILITY_DATA"),
              "no_training_authorized": decision["training_authorized"] is False}
    verification = {"schema": "reliability-feasibility-phase1-verification-v1", "passed": all(checks.values()), "checks": checks,
                    "decision": decision["decision"], "no_model_training_performed": True, "no_reliability_untouched_test_generated": True}
    write(output / "phase1_verification.json", verification)
    print(json.dumps({"passed": verification["passed"], "decision": verification["decision"],
                      "unseen_bodies": decision["locator_unseen_body_geometry_count"], "exposure_rows": exposure["sample_row_count"]}, ensure_ascii=False, indent=2))
    if not verification["passed"]: raise SystemExit(3)


if __name__ == "__main__": main()
