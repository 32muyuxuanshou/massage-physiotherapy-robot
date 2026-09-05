"""Design true multi-beta candidates from the frozen single-axis sensitivity data.

The optimizer enumerates bounded two/three-component combinations.  Targets
are geometry directions; beta values are selected by the measured Jacobian,
not handwritten profile parameters.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np


COMPATIBLE_METRICS = [
    "body_longitudinal_length",
    "shoulder_width",
    "upper_torso_width",
    "lower_torso_width",
    "torso_thickness",
    "pelvis_width",
]

# Dimensionless targets relative to the largest observed +/-0.5 response for
# each metric.  These are desired geometry directions, not beta parameters.
OBJECTIVES = [
    ("C01_LONG_UPPER_WIDE", [0.65, 0.15, 0.40, 0.30, 0.10, 0.20]),
    ("C02_SHORT_NARROW_THIN", [-0.65, -0.20, -0.40, -0.35, -0.35, -0.30]),
    ("C03_LONG_NARROW", [0.60, -0.25, -0.35, -0.25, -0.15, -0.15]),
    ("C04_COMPACT_WIDE", [-0.25, 0.30, 0.40, 0.35, 0.25, 0.25]),
    ("C05_THICK_UPPER_WIDE", [0.10, 0.25, 0.35, 0.30, 0.45, 0.25]),
    ("C06_THIN_NARROW", [0.00, -0.25, -0.45, -0.40, -0.50, -0.25]),
    ("C07_SHOULDER_UPPER_WIDE", [0.00, 0.50, 0.45, 0.15, 0.00, 0.05]),
    ("C08_LOWER_PELVIS_WIDE", [0.00, 0.10, 0.05, 0.45, 0.30, 0.45]),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_design(report_path: Path) -> dict:
    report = read_json(report_path)
    by_case = {item["case"]: item for item in report["cases"]}
    baseline_clearance_mm = float(by_case["A_BASE"]["bed_clearance_m"]) * 1000.0

    # Central differences: (+0.5 - -0.5) / 1.0 beta unit.
    jacobian = np.asarray([
        [
            (
                float(by_case[f"B{index + 1:02d}_POS"]["measurements_m"][metric])
                - float(by_case[f"B{index + 1:02d}_NEG"]["measurements_m"][metric])
            )
            * 1000.0
            for index in range(10)
        ]
        for metric in COMPATIBLE_METRICS
    ])
    clearance_jacobian = np.asarray([
        (
            float(by_case[f"B{index + 1:02d}_POS"]["bed_clearance_m"])
            - float(by_case[f"B{index + 1:02d}_NEG"]["bed_clearance_m"])
        )
        * 1000.0
        for index in range(10)
    ])
    scales = np.max(np.abs(jacobian * 0.5), axis=1)
    values = (-0.35, -0.30, -0.25, -0.20, 0.20, 0.25, 0.30, 0.35)
    pool: list[tuple[np.ndarray, np.ndarray, float]] = []
    for count in (2, 3):
        for indices in itertools.combinations(range(10), count):
            for coefficients in itertools.product(values, repeat=count):
                # beta_2 negative was already bed-incompatible.  beta_6 positive
                # introduced an anchor-neighborhood overlap in the F calibration.
                if 1 in indices and coefficients[indices.index(1)] < 0:
                    continue
                if 5 in indices and coefficients[indices.index(5)] > 0:
                    continue
                betas = np.zeros(10, dtype=float)
                betas[list(indices)] = coefficients
                predicted_clearance = baseline_clearance_mm + float(clearance_jacobian @ betas)
                if predicted_clearance < 3.0:
                    continue
                pool.append((betas, jacobian @ betas, predicted_clearance))

    selected: list[dict] = []
    for objective_id, direction_values in OBJECTIVES:
        direction = np.asarray(direction_values, dtype=float)
        target = direction * scales
        best = None
        for betas, predicted, predicted_clearance in pool:
            if any(np.array_equal(betas, np.asarray(item["betas"])) for item in selected):
                continue
            residual = (predicted - target) / scales
            sign_violations = sum(
                1
                for ordinal, desired in enumerate(direction)
                if abs(desired) >= 0.25 and predicted[ordinal] * desired < 0
            )
            overlap_penalty = max(
                (
                    len(set(np.flatnonzero(betas)) & set(np.flatnonzero(item["betas"]))) / 3.0
                    for item in selected
                ),
                default=0.0,
            )
            score = (
                float(residual @ residual)
                + 0.03 * float(betas @ betas)
                + 0.30 * sign_violations
                + 0.03 * overlap_penalty
            )
            if best is None or score < best[0]:
                best = (score, betas.copy(), predicted.copy(), predicted_clearance, sign_violations)
        if best is None:
            raise RuntimeError(f"no feasible combination for {objective_id}")
        score, betas, predicted, predicted_clearance, sign_violations = best
        selected.append({
            "profile_id": objective_id,
            "betas": [float(value) for value in betas],
            "nonzero_beta_indices_zero_based": [int(value) for value in np.flatnonzero(betas)],
            "objective_direction_normalized": dict(zip(COMPATIBLE_METRICS, direction_values)),
            "target_delta_mm": dict(zip(COMPATIBLE_METRICS, map(float, target))),
            "predicted_delta_mm": dict(zip(COMPATIBLE_METRICS, map(float, predicted))),
            "normalized_residual_l2": float(np.linalg.norm((predicted - target) / scales)),
            "objective_score": float(score),
            "sign_violation_count": int(sign_violations),
            "predicted_fixed_bed_clearance_mm": float(predicted_clearance),
            "status": "DESIGNED_NOT_YET_VALIDATED",
        })

    return {
        "schema": "candidate-shape-combination-design-v1",
        "medical_truth": False,
        "source_sensitivity_report": str(report_path.resolve()),
        "jacobian_method": "central difference from each frozen +/-0.5 single-beta pair",
        "compatible_metrics": COMPATIBLE_METRICS,
        "metric_scale_mm": dict(zip(COMPATIBLE_METRICS, map(float, scales))),
        "measurement_jacobian_mm_per_beta": {
            metric: [float(value) for value in jacobian[row]]
            for row, metric in enumerate(COMPATIBLE_METRICS)
        },
        "clearance_jacobian_mm_per_beta": [float(value) for value in clearance_jacobian],
        "baseline_clearance_mm": baseline_clearance_mm,
        "enumeration": {
            "allowed_nonzero_component_counts": [2, 3],
            "allowed_magnitudes": list(values),
            "feasible_pool_count": len(pool),
            "minimum_predicted_clearance_mm": 3.0,
            "beta_2_negative": "excluded: prior fixed-bed incompatibility",
            "beta_6_positive": "excluded: F-line single-axis anchor-neighborhood overlap",
        },
        "candidates": selected,
        "limitations": [
            "This is a local linear design model; every combination requires nonlinear Blender validation.",
            "V1 shoulder_to_pelvis_length was excluded because the V2 measurement contract intentionally changed that metric.",
            "Geometry objective names are engineering descriptions, not clinical body categories.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_design(args.report)
    write_json(args.output, payload)
    print(json.dumps({"designed": len(payload["candidates"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
