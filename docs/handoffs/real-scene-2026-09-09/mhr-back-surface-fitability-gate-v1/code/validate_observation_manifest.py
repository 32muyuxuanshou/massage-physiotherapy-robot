"""Validate a future real RGB-D observation manifest before fitting."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


CLASSES = {"FIT", "HELD_OUT_VIEW", "REPEATABILITY"}


def finite_positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def validate(data, allow_template=False):
    errors = []
    if data.get("status") == "TEMPLATE" and allow_template:
        return []
    if not data.get("subject_id") or not data.get("session_id"):
        errors.append("subject_id and session_id are required")
    if not data.get("consent_and_use_scope_recorded"):
        errors.append("consent/use scope must be recorded")
    captures = data.get("captures") or []
    if len(captures) < 2:
        errors.append("at least FIT and held-out capture are required")
    ids = [row.get("frame_id") for row in captures]
    if len(ids) != len(set(ids)):
        errors.append("frame_id values must be unique")
    roles = {row.get("role") for row in captures}
    if "FIT" not in roles or "HELD_OUT_VIEW" not in roles:
        errors.append("FIT and HELD_OUT_VIEW roles are required")
    for i, row in enumerate(captures):
        prefix = f"captures[{i}]"
        if row.get("role") not in CLASSES:
            errors.append(f"{prefix}.role invalid")
        if row.get("mesh_overlay_seen_during_annotation") is not False:
            errors.append(f"{prefix} annotation must be mesh-blind")
        if not finite_positive(row.get("depth_raw_unit_scale_to_m")):
            errors.append(f"{prefix}.depth_raw_unit_scale_to_m invalid")
        for key in ("rgb_intrinsics", "depth_intrinsics"):
            intr = row.get(key) or {}
            for field in ("width", "height", "fx", "fy"):
                if not finite_positive(intr.get(field)):
                    errors.append(f"{prefix}.{key}.{field} invalid")
            for field in ("cx", "cy"):
                if not isinstance(intr.get(field), (int, float)) or not math.isfinite(intr[field]):
                    errors.append(f"{prefix}.{key}.{field} invalid")
        matrix = row.get("depth_to_rgb_extrinsics_4x4")
        if not (isinstance(matrix, list) and len(matrix) == 4 and all(isinstance(r, list) and len(r) == 4 for r in matrix)):
            errors.append(f"{prefix}.depth_to_rgb_extrinsics_4x4 invalid")
        for key in ("rgb_path", "depth_raw_path", "depth_registered_path", "visible_bare_back_mask_path", "semantic_mask_path", "calibration_report_path"):
            if not row.get(key):
                errors.append(f"{prefix}.{key} required")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--allow-template", action="store_true")
    args = parser.parse_args()
    errors = validate(json.loads(args.manifest.read_text(encoding="utf-8")), args.allow_template)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
