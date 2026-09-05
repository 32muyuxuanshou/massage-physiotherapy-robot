from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_TRUE_KEYS = {"medical_truth", "medical_validated"}
FORBIDDEN_STATUS_VALUES = {"validated_safe", "MEDICAL_TRUTH", "DOCTOR_CONFIRMED"}


def walk(value, path: str, findings: list[dict], warnings: list[dict]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                findings.append({"path": child_path, "reason": "medical truth flag must remain false"})
            if (
                key in {"status", "truth_status", "review_status"}
                and isinstance(item, str)
                and item in FORBIDDEN_STATUS_VALUES
            ):
                findings.append({"path": child_path, "reason": f"forbidden status: {item}"})
            if isinstance(item, str) and "doctor_annotation" in item.lower():
                warnings.append({
                    "path": child_path,
                    "reason": "ambiguous legacy doctor_annotation string requires the frozen engineering truth envelope",
                })
            walk(item, child_path, findings, warnings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk(item, f"{path}[{index}]", findings, warnings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    findings: list[dict] = []
    warnings: list[dict] = []
    parsed = 0
    parse_errors = []
    for path in sorted(args.root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            parse_errors.append({"file": str(path), "error": str(exc)})
            continue
        parsed += 1
        file_findings: list[dict] = []
        file_warnings: list[dict] = []
        walk(data, "", file_findings, file_warnings)
        for item in file_findings:
            item["file"] = str(path)
        for item in file_warnings:
            item["file"] = str(path)
        findings.extend(file_findings)
        warnings.extend(file_warnings)

    report = {
        "schema": "engineering-truth-tree-validation-v1",
        "passed": not findings and not parse_errors,
        "root": str(args.root),
        "json_files_parsed": parsed,
        "findings": findings,
        "parse_errors": parse_errors,
        "warnings": warnings,
        "warning_policy": "Warnings do not fail the tree, but copied legacy Atlas files remain governed by engineering_reference_truth_envelope_v1.json.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
