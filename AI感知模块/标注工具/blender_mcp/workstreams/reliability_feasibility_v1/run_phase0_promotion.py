from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
AI_ROOT = Path(__file__).resolve().parents[4]
DECODER_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-09-02_13-10-44_DECODER_CONTRACT_VALIDATION_UNTOUCHED_V1"
V2_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2"
EVAL_V2 = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_21-07-08_EVALUATION_CONTRACT_V2"


def read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path: Path, value: dict) -> None: path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path: Path) -> dict: return {"path": str(path), "sha256": sha(path)}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=Path); args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    contract_path = DECODER_ROOT / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json"
    freeze_path = DECODER_ROOT / "decoder_contract_freeze_receipt.json"
    verification_path = DECODER_ROOT / "verification.json"
    contract, freeze, verification = read(contract_path), read(freeze_path), read(verification_path)
    checks = {
        "freeze_receipt_passed": freeze["passed"],
        "contract_hash_matches_freeze_receipt": sha(contract_path) == freeze["contract_sha256"],
        "untouched_test_verification_passed": verification["passed"],
        "untouched_test_status_pass": verification["status"] == "PASS_FROZEN_BOUNDARY_HYBRID_V1",
        "protected_inputs_unchanged": all(sha(Path(item["path"])) == item["sha256"] for item in freeze["protected_inputs"].values()),
    }
    weights = {split: ref(V2_ROOT / "training" / split / "model_state.pt") for split in SPLITS}
    predictions = {phase: {split: ref(DECODER_ROOT / phase / "predictions" / f"{split}.npz") for split in SPLITS} for phase in ("validation", "untouched_test")}
    promotion = {
        "schema": "boundary-hybrid-v1-promotion-receipt-v1",
        "status": "RELEASED_FOR_SYNTHETIC_ENGINEERING_EVALUATION" if all(checks.values()) else "PROMOTION_FAILED",
        "passed": all(checks.values()), "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "medical_truth": False, "real_human_validated": False, "robot_safe": False,
        "frozen_decoder_contract": ref(contract_path), "freeze_receipt": ref(freeze_path),
        "final_untouched_verification": ref(verification_path),
        "decoder_code": ref(Path(freeze["protected_inputs"]["boundary_hybrid_decoder.py"]["path"])),
        "frozen_model_weights": weights, "validation_predictions": predictions["validation"],
        "untouched_test_predictions": predictions["untouched_test"], "checks": checks,
        "scope": "Three independent frozen TinyHeatmapNet diagnostic baselines on synthetic canonical SKEL E01-E20 engineering points.",
        "prohibited_claims": ["medical validity", "real RGB-D generalization", "production locator", "robot execution safety"],
    }
    promotion_path = out / "BOUNDARY_HYBRID_V1_PROMOTION_RECEIPT.json"; write(promotion_path, promotion)
    coordinate_path = EVAL_V2 / "evaluation_coordinate_contract_v2.json"
    eval_v3 = {
        "schema": "evaluation-contract-v3", "status": "FROZEN_FOR_RELIABILITY_FEASIBILITY",
        "medical_truth": False, "robot_safe": False,
        "references": {"decoder_contract": ref(contract_path), "freeze_receipt": ref(freeze_path),
                       "promotion_receipt": ref(promotion_path), "coordinate_contract_v2": ref(coordinate_path)},
        "default_decoder": {"id": "BOUNDARY_HYBRID_V1", "authority": "Referenced frozen decoder contract; rules are not duplicated here."},
        "diagnostic_decoder": {"id": "GLOBAL_SPATIAL_EXPECTATION", "use": "baseline comparison only"},
        "coordinates": {"space": "original 1280x1024 continuous image coordinates", "authority": str(coordinate_path)},
        "depth_and_backprojection": {"status": "UNCHANGED_FROM_EVALUATION_CONTRACT_V2_AND_CENTER_RAY_DEPTH_V2",
                                     "depth": "first visible scene surface OpenCV camera Zc in float32 meters; background 0"},
        "reliability_rule": "All future reliability labels and runtime features must be computed from frozen BOUNDARY_HYBRID_V1 outputs; the three locator baselines remain separate diagnostic replicas.",
        "model_roles": {split: {"role": "INDEPENDENT_DIAGNOSTIC_REPLICA", "may_pool_risk_training_rows": False,
                                "weight": weights[split]} for split in SPLITS},
        "not_authorized": ["retraining locator", "pooling three locators into one reliability model", "robot execution", "medical claims"],
    }
    eval_path = out / "EVALUATION_CONTRACT_V3.json"; write(eval_path, eval_v3)
    phase = {"schema": "reliability-feasibility-phase0-verification-v1", "passed": promotion["passed"],
             "checks": checks, "promotion_receipt": ref(promotion_path), "evaluation_contract_v3": ref(eval_path)}
    write(out / "phase0_verification.json", phase)
    print(json.dumps({"passed": phase["passed"], "promotion": str(promotion_path), "evaluation_v3": str(eval_path)}, ensure_ascii=False, indent=2))
    if not phase["passed"]: raise SystemExit(2)


if __name__ == "__main__": main()
