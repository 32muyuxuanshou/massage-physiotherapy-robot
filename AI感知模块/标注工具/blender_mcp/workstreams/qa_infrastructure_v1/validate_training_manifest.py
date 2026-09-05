from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = read_json(args.manifest)
    findings = []
    ids = []
    expected_order = data.get("point_order", [])
    for item in data.get("samples", []):
        sample_id = item.get("sample_id")
        ids.append(sample_id)
        model_record = item.get("model_input", {})
        model_path = Path(model_record.get("path", ""))
        lower = str(model_path).lower()
        if model_path.name.lower() != "rgb.png":
            findings.append({"sample": sample_id, "reason": "model input is not rgb.png"})
        if any(token in lower for token in ("overlay", "depth", "mask", "label")):
            findings.append({"sample": sample_id, "reason": "forbidden token in model input path"})
        if not model_path.is_file() or sha256(model_path) != model_record.get("sha256"):
            findings.append({"sample": sample_id, "reason": "model input missing or hash mismatch"})
        for role, record in item.get("geometry_inputs", {}).items():
            path = Path(record.get("path", ""))
            if not path.is_file() or sha256(path) != record.get("sha256"):
                findings.append({"sample": sample_id, "role": role, "reason": "geometry input missing or hash mismatch"})
        labels_path = Path(item.get("geometry_inputs", {}).get("labels", {}).get("path", ""))
        if labels_path.is_file():
            labels = read_json(labels_path)
            points = labels.get("points", [])
            order = [point.get("point_id") for point in points]
            if labels.get("medical_truth") is not False:
                findings.append({"sample": sample_id, "reason": "labels medical_truth is not false"})
            if order != expected_order:
                findings.append({"sample": sample_id, "reason": "point order mismatch"})

    checks = {
        "schema": data.get("schema") == "training-dataset-manifest-v1",
        "immutable": data.get("immutable") is True,
        "medical_truth_false": data.get("medical_truth") is False,
        "medical_validated_false": data.get("medical_validated") is False,
        "sample_count_30": len(ids) == data.get("sample_count") == 30,
        "sample_ids_unique": len(set(ids)) == len(ids),
        "point_count_20": len(expected_order) == data.get("point_count_per_sample") == 20,
        "point_ids_unique": len(set(expected_order)) == len(expected_order),
        "overlay_explicitly_forbidden": "overlay.png" in data.get("model_input_contract", {}).get("forbidden", []),
        "all_files_and_labels_verified": not findings,
    }
    report = {
        "schema": "independent-training-manifest-validation-v1",
        "passed": all(checks.values()),
        "manifest": str(args.manifest),
        "checks": checks,
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
