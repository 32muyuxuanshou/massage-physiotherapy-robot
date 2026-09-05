from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AI_ROOT = HERE.parents[3]
CAMERA_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_18-38-27_CAMERA_VISIBILITY_DIVERSITY_V1"
SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    failures = []
    rows = [line for line in target.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    for line in rows:
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected.lower():
            failures.append(relative)
    return {"passed": not failures, "entries": len(rows), "failures": failures, "manifest_sha256": sha256(target)}


def build_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    rows = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != target
    ]
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(target)}


def protected_sources_unchanged() -> dict:
    frozen = read_json(CAMERA_ROOT / "source_hashes_before.json")
    rows = []
    for name, item in frozen.items():
        path = Path(item["path"])
        actual = sha256(path) if path.is_file() else None
        rows.append({"name": name, "path": str(path), "expected": item["sha256"], "actual": actual, "passed": actual == item["sha256"]})
    return {"passed": all(row["passed"] for row in rows), "files": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    args = parser.parse_args()
    freeze = args.freeze.resolve()
    dataset = args.dataset.resolve()
    training = args.training.resolve()
    freeze_manifest = verify_manifest(freeze)
    dataset_manifest = verify_manifest(dataset)
    freeze_verification = read_json(freeze / "verification.json")
    dataset_verification = read_json(dataset / "qc_verification.json")
    dataset_visual = read_json(dataset / "visual_review.json")
    prediction_visual = read_json(training / "prediction_visual_review.json")
    determinism = read_json(training / "determinism_report.json")
    protected = protected_sources_unchanged()
    split_rows = []
    split_checks = []
    for split_id in SPLITS:
        root = training / split_id
        training_verification = read_json(root / "verification.json")
        independent_verification = read_json(root / "independent_verification.json")
        evaluation = read_json(root / "independent_evaluation.json")
        split_checks.extend([training_verification["passed"], independent_verification["passed"]])
        split_rows.append({
            "split_id": split_id,
            "training_passed": training_verification["passed"],
            "independent_evaluation_passed": independent_verification["passed"],
            "test_visible_2d": evaluation["test"]["visible_2d"],
            "test_depth_to_3d": evaluation["test"]["depth_to_3d"],
            "challenge_visible_2d": evaluation["challenge"]["visible_2d"],
            "challenge_depth_to_3d": evaluation["challenge"]["depth_to_3d"],
        })
    primary = read_json(training / "COMBINATION_HOLDOUT" / "independent_evaluation.json")
    write_json(training / "pilot_baseline_summary.json", {
        "schema": "engineering-pilot-baseline-summary-v1",
        "medical_truth": False,
        "dataset": {
            "main_samples": 360,
            "challenge_samples": 12,
            "camera_quotas": {"NORMAL_MAIN": 144, "C1_MILD_OBLIQUE": 108, "C2_EDGE_CROP": 54, "C3_EXTERNAL_OCCLUDER": 54},
            "appearance": "Frozen deterministic RGB-only photometric variants; geometry unchanged.",
        },
        "split_results": split_rows,
        "primary_combination_holdout_by_camera": primary["test"]["by_camera"],
        "headline_findings": [
            "Grouped holdouts prevent Shape×Pose case leakage across train/val/test.",
            "C2 single-direction edge crop is the hardest qualified main camera in the primary split.",
            "C4 challenge error is very large and confirms challenge-only handling; it is not solved by this baseline.",
            "Visible-point 3D recovery runs for every test-visible instance, but maximum errors remain far above robot-safe precision.",
        ],
        "allowed_conclusion": "A frozen synthetic engineering Pilot can train an RGB-only visible-point heatmap baseline and expose failure by unseen combination, shape, pose and camera.",
        "prohibited_conclusions": ["medical accuracy", "real-human generalization", "clinical deployment", "robot execution safety"],
    })
    write_json(training / "failure_driven_next_gate.json", {
        "schema": "engineering-pilot-failure-driven-next-gate-v1",
        "medical_truth": False,
        "observed": {
            "hardest_qualified_main_camera": "C2_EDGE_CROP",
            "c2_limit": "single-direction truncation only",
            "c3_limit": "fixed upper-back occluder only",
            "c4_status": "challenge-only and currently fails badly",
            "appearance_limit": "image-space photometric variation, not physical relighting/material rerendering",
        },
        "next_candidate_stage": "CONTROLLED_TRUNCATION_OCCLUSION_EXPANSION_V2",
        "candidate_changes": [
            "Validate a symmetric right-side crop as a separate camera gate.",
            "Validate middle- and lower-back occluder positions one at a time.",
            "Keep C4 out of training until a dedicated extreme-view strategy is designed.",
            "If real RGB-D hardware becomes available, prefer measured camera/noise work over invented depth noise.",
        ],
        "not_authorized_by_this_file": "Do not automatically generate V2 data until the new camera/occluder gates are reviewed.",
    })
    implementations = []
    for path in sorted(HERE.glob("*.py")):
        implementations.append({"path": str(path), "sha256": sha256(path)})
    write_json(training / "phase_implementation_hashes.json", {
        "schema": "engineering-pilot-implementation-hashes-v1",
        "files": implementations,
    })
    checks = {
        "freeze_manifest_passed": freeze_manifest["passed"],
        "freeze_verification_passed": freeze_verification["passed"],
        "dataset_manifest_passed": dataset_manifest["passed"],
        "dataset_qc_passed": dataset_verification["passed"],
        "dataset_visual_review_passed": dataset_visual["passed"],
        "all_three_training_and_independent_evaluations_passed": all(split_checks),
        "combination_training_deterministic": determinism["passed"],
        "prediction_visual_review_passed": prediction_visual["passed"],
        "protected_sources_unchanged": protected["passed"],
    }
    write_json(training / "protected_sources_verification.json", protected)
    write_json(training / "final_verification.json", {
        "schema": "engineering-pilot-final-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "freeze_root": str(freeze),
        "dataset_root": str(dataset),
        "training_root": str(training),
        "truth_status": {"kind": "ENGINEERING_MODEL_EVALUATION", "medical_truth": False, "medical_validated": False},
        "next_gate": "Review the failure map before any controlled truncation/occlusion expansion V2.",
    })
    result = build_manifest(training)
    print(json.dumps({"PILOT_FINAL": "PASS" if all(checks.values()) else "FAIL", **result}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
