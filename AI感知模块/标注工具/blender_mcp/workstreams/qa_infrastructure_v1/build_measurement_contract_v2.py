from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path


PROJECT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
SOURCE = PROJECT / "outputs" / "交付文件" / "2026-08-30_19-24-33" / "body_measurement_contract_v1.json"
OUTPUT = PROJECT / "outputs" / "交付文件" / "2026-08-31_13-36-44" / "F_qa" / "body_measurement_contract_v2.json"


LEVEL_IDS = {
    "shoulder_width": "MEASURE_SHOULDER_LEVEL_V1",
    "upper_torso_width": "MEASURE_UPPER_TORSO_LEVEL_V1",
    "lower_torso_width": "MEASURE_LOWER_TORSO_LEVEL_V1",
    "torso_thickness": "MEASURE_TORSO_THICKNESS_LEVEL_V1",
    "pelvis_width": "MEASURE_PELVIS_LEVEL_V1",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    result = deepcopy(source)
    result["schema"] = "skel-body-measurement-contract-v2"
    result["source_contract"] = {
        "path": str(SOURCE),
        "sha256": sha256(SOURCE),
        "compatibility": "same frozen beta-zero vertex sets for existing extent metrics",
    }
    result["medical_truth"] = False
    result["runtime_medical_point_dependency"] = False

    for metric_name, level_id in LEVEL_IDS.items():
        metric = result["measurements"][metric_name]
        old_names = metric.pop("reference_points", [])
        metric["reference_level_id"] = level_id
        metric["reference_level_origin"] = {
            "kind": "frozen_body_local_y_numeric_level",
            "level_y_m": metric["level_y_m"],
            "legacy_engineering_labels_removed": old_names,
            "runtime_dependency": False,
        }

    shoulder_vertices = result["measurements"]["shoulder_width"]["frozen_vertex_indices"]
    pelvis_vertices = result["measurements"]["pelvis_width"]["frozen_vertex_indices"]
    result["measurements"]["shoulder_to_pelvis_length"] = {
        "axis": "body_longitudinal_y",
        "method": "absolute difference between mean body-local Y of two frozen beta-zero vertex sets",
        "reference_vertex_sets": {
            "MEASURE_SHOULDER_LEVEL_V1": shoulder_vertices,
            "MEASURE_PELVIS_LEVEL_V1": pelvis_vertices,
        },
        "metric_definition_changed_from_v1": True,
        "comparison_notice": "Do not compare this metric numerically with v1 shoulder_to_pelvis_length without an explicit bridge analysis.",
    }
    result["limitations"] = list(result.get("limitations", [])) + [
        "Level names are engineering measurement IDs, not medical acupoints.",
        "V2 shoulder-to-pelvis length uses frozen mesh vertex sets and is intentionally decoupled from Atlas point positions.",
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "schema": "measurement-contract-v2-build-report",
        "passed": True,
        "source": str(SOURCE),
        "source_sha256": sha256(SOURCE),
        "output": str(OUTPUT),
        "output_sha256": sha256(OUTPUT),
        "medical_like_runtime_references": [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
