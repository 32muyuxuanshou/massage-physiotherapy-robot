from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
HERE = Path(__file__).resolve().parent


def read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path: Path, value: dict) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); parser.add_argument("--weights-root", required=True, type=Path); args = parser.parse_args()
    root = args.root.resolve(); weights = args.weights_root.resolve(); evaluation = read(root / "validation_decoder_evaluation.json")
    generation = read(root / "validation_sample_generation_report.json"); geometry = read(root / "selected_geometry_determinism.json")
    deterministic = read(root / "validation_decoder_determinism.json"); unit = read(root / "decoder_guard_unit_tests.json")
    thresholds = {"minimum_visible_2d_p95_relative_reduction": 0.25, "minimum_tail_gt30mm_relative_reduction": 0.50,
                  "maximum_hybrid_invalid_3d_count": 0, "maximum_gt_ge128_activation_rate": 0.01,
                  "maximum_regression_px": 0.5, "require_control_normal_exact": True, "require_control_oblique_exact": True}
    checks = {"geometry_deterministic": geometry["passed"], "validation_samples_passed": generation["passed"],
              "validation_inference_deterministic": deterministic["passed"], "guard_unit_tests_passed": unit["passed"],
              "untouched_test_samples_absent_at_freeze": not (root / "untouched_test").exists(),
              "untouched_test_cache_absent_at_freeze": not (root / "untouched_test_decoder_cache.npz").exists(),
              "untouched_test_report_absent_at_freeze": not (root / "untouched_test_decoder_evaluation.json").exists()}
    split_receipts = {}
    for split in SPLITS:
        data = evaluation["splits"][split]; base, candidate, audit = data["expectation"], data["hybrid"], data["branch_audit"]
        p95_reduction = 1.0 - candidate["visible_2d"]["p95"] / base["visible_2d"]["p95"]
        tail_reduction = 1.0 - candidate["tail_gt30mm_count"] / base["tail_gt30mm_count"]
        split_checks = {
            "visible_2d_p95_reduction": p95_reduction >= thresholds["minimum_visible_2d_p95_relative_reduction"],
            "tail_gt30mm_reduction": tail_reduction >= thresholds["minimum_tail_gt30mm_relative_reduction"],
            "invalid_3d_zero": candidate["invalid_3d_count"] <= thresholds["maximum_hybrid_invalid_3d_count"],
            "nonedge_activation_bounded": audit["nonedge_gt_ge128_activation_rate"] <= thresholds["maximum_gt_ge128_activation_rate"],
            "regression_bounded": audit["max_regression_px"] <= thresholds["maximum_regression_px"],
            "control_normal_exact": base["by_kind"]["CONTROL_NORMAL"] == candidate["by_kind"]["CONTROL_NORMAL"],
            "control_oblique_exact": base["by_kind"]["CONTROL_OBLIQUE"] == candidate["by_kind"]["CONTROL_OBLIQUE"],
        }
        checks[f"{split}_acceptance"] = all(split_checks.values())
        split_receipts[split] = {"checks": split_checks, "p95_relative_reduction": p95_reduction,
                                 "tail_gt30mm_relative_reduction": tail_reduction,
                                 "expectation": base, "hybrid": candidate, "branch_audit": audit}
    source_files = [HERE / name for name in ("boundary_hybrid_decoder.py", "infer_decoder_gate.py", "build_decoder_cache.py", "evaluate_decoder_gate.py", "generate_decoder_samples.py")]
    protected = {path.name: {"path": str(path), "sha256": sha(path)} for path in source_files}
    protected["camera_design_v1.json"] = {"path": str(root / "camera_design_v1.json"), "sha256": sha(root / "camera_design_v1.json")}
    protected["qualified_new_geometry.json"] = {"path": str(root / "qualified_new_geometry.json"), "sha256": sha(root / "qualified_new_geometry.json")}
    for split in SPLITS:
        path = weights / split / "model_state.pt"; protected[f"model_{split}"] = {"path": str(path), "sha256": sha(path)}
    passed = all(checks.values())
    contract = {"schema": "boundary-hybrid-decoder-contract-v1", "status": "FROZEN_VALIDATION_PASSED_UNTOUCHED_TEST_PENDING",
                "passed_validation": passed, "medical_truth": False,
                "decoder": {"input": "finite raw logits BxPx32x40 (no prior softmax)", "base_decoder": "global spatial softmax expectation",
                            "boundary_cells": 4, "fit": "axiswise 3-point quadratic on log-marginals",
                            "curvature_epsilon": 1e-8, "valid_vertex_domain": {"x": [-0.5, 39.5], "y": [-0.5, 31.5]},
                            "minimum_axiswise_correction_original_px": 12.0,
                            "fallback": "global spatial expectation when nonfinite/singular/nonconcave/out-of-domain/or correction<12px"},
                "acceptance_thresholds_frozen_before_untouched_test": thresholds, "checks": checks,
                "validation_split_receipts": split_receipts, "protected_inputs": protected,
                "limitations": ["Three frozen TinyHeatmapNet engineering baselines", "Synthetic SKEL and non-medical E01-E20 only",
                                "Validation passed does not imply clinical, real-camera or robot safety"]}
    contract_path = root / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json"; write(contract_path, contract)
    receipt = {"schema": "decoder-contract-freeze-receipt-v1", "passed": passed,
               "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "contract": str(contract_path),
               "contract_sha256": sha(contract_path), "untouched_test_not_generated_at_freeze": checks["untouched_test_samples_absent_at_freeze"],
               "protected_inputs": protected}
    write(root / "decoder_contract_freeze_receipt.json", receipt)
    print(json.dumps({"passed": passed, "contract_sha256": receipt["contract_sha256"], "checks": checks}, ensure_ascii=False, indent=2))
    if not passed: raise SystemExit(3)


if __name__ == "__main__": main()
