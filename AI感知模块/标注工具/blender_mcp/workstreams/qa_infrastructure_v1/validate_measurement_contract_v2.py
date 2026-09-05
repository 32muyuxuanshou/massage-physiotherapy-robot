from __future__ import annotations

import argparse
import json
from pathlib import Path


SLICE_METRICS = {
    "shoulder_width",
    "upper_torso_width",
    "lower_torso_width",
    "torso_thickness",
    "pelvis_width",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()
    data = json.loads(args.contract.read_text(encoding="utf-8"))

    checks = {
        "schema_v2": data.get("schema") == "skel-body-measurement-contract-v2",
        "medical_truth_false": data.get("medical_truth") is False,
        "runtime_medical_dependency_false": data.get("runtime_medical_point_dependency") is False,
        "topology_matches": data.get("topology_signature_sha256") == "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
        "slice_metrics_present": SLICE_METRICS.issubset(data.get("measurements", {})),
    }
    for name in sorted(SLICE_METRICS):
        metric = data["measurements"].get(name, {})
        checks[f"{name}_neutral_level_id"] = str(metric.get("reference_level_id", "")).startswith("MEASURE_")
        checks[f"{name}_no_runtime_reference_points"] = "reference_points" not in metric
        checks[f"{name}_frozen_vertices"] = bool(metric.get("frozen_vertex_indices"))
        checks[f"{name}_runtime_dependency_false"] = (
            metric.get("reference_level_origin", {}).get("runtime_dependency") is False
        )

    bridge = data.get("measurements", {}).get("shoulder_to_pelvis_length", {})
    checks["shoulder_to_pelvis_uses_frozen_vertex_sets"] = set(
        bridge.get("reference_vertex_sets", {})
    ) == {"MEASURE_SHOULDER_LEVEL_V1", "MEASURE_PELVIS_LEVEL_V1"}
    checks["shoulder_to_pelvis_marks_definition_change"] = bridge.get(
        "metric_definition_changed_from_v1"
    ) is True
    checks["shoulder_to_pelvis_no_reference_points"] = "reference_points" not in bridge

    report = {
        "schema": "measurement-contract-v2-validation-v1",
        "passed": all(checks.values()),
        "contract": str(args.contract),
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
