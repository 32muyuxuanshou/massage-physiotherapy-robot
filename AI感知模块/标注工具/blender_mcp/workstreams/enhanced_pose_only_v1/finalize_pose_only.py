#!/usr/bin/env python3
"""Create B-line sensitivity reports and a provisional profile set."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import run_enhanced_pose_only as b


def angle_degrees(first, second) -> float:
    dot = sum(float(a) * float(c) for a, c in zip(first, second))
    left = math.sqrt(sum(float(value) ** 2 for value in first))
    right = math.sqrt(sum(float(value) ** 2 for value in second))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (left * right))))) if left and right else 0.0


def overlay(preview: Path, probe: dict, output: Path) -> None:
    with Image.open(preview) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    scale_x = image.width / 1280.0
    scale_y = image.height / 1024.0
    font = ImageFont.load_default()
    for point in probe["points"]:
        u, v = point["uv_pixel_opencv"]
        x, y = u * scale_x, v * scale_y
        color = (25, 230, 90) if point["visible"] else (240, 60, 60)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color, outline=(0, 0, 0))
        draw.text((x + 5, y - 6), str(point.get("code") or point["point_id"]), fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def montage(items, output: Path, columns=4) -> None:
    width, height, header = 320, 256, 26
    rows = math.ceil(len(items) / columns)
    canvas = Image.new("RGB", (width * columns, (height + header) * rows), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, path) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        x, y = index % columns * width, index // columns * (height + header)
        canvas.paste(image, (x, y + header))
        draw.text((x + 5, y + 7), label, fill="black", font=font)
    canvas.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=b.OUT)
    args = parser.parse_args()
    root = args.output.resolve()
    primary, deterministic = b.read(root / "pose_only_report.json"), b.read(root / "determinism_report.json")
    definitions = {item["pose_id"]: item for item in b.read(b.CONFIG)["profiles"]}
    baseline = b.read(b.RUN_ROOT / "probes" / "P0_BASE.json")
    baseline_points = {item["point_id"]: item for item in baseline["points"]}
    baseline_si = b.read(b.RUN_ROOT / "self_intersections" / "P0_BASE.json")
    baseline_pairs = {tuple(pair) for pair in baseline_si["nonadjacent_intersection_pairs_truncated"]}
    rows, csv_rows, montage_items = [], [], []
    for pose_id in definitions:
        probe = b.read(b.RUN_ROOT / "probes" / f"{pose_id}.json")
        si = b.read(b.RUN_ROOT / "self_intersections" / f"{pose_id}.json")
        current_pairs = {tuple(pair) for pair in si["nonadjacent_intersection_pairs_truncated"]}
        details = []
        for point in probe["points"]:
            original = baseline_points[point["point_id"]]
            detail = {
                "point_id": point["point_id"], "code": point.get("code"),
                "xyz_delta_mm": math.dist(point["xyz_world_m"], original["xyz_world_m"]) * 1000,
                "uv_delta_px": math.dist(point["uv_pixel_opencv"], original["uv_pixel_opencv"]),
                "normal_delta_deg": angle_degrees(point["normal_world"], original["normal_world"]),
                "triangle_area_ratio": float(point["triangle_area_m2"]) / float(original["triangle_area_m2"]),
                "max_triangle_edge_delta_mm": max(abs((float(a) - float(c)) * 1000) for a, c in zip(point["triangle_edge_lengths_m"], original["triangle_edge_lengths_m"])),
                "visible": point["visible"], "visibility_reason": point["visibility_reason"],
            }
            details.append(detail)
            csv_rows.append({"pose_id": pose_id, **detail})
        case = next(item for item in primary["cases"] if item["pose_id"] == pose_id)
        row = {
            "pose_id": pose_id, "kind": definitions[pose_id]["kind"],
            "parameter_source": definitions[pose_id]["source"],
            "overrides_degrees": definitions[pose_id]["overrides_degrees"],
            "diagnostic_intent": definitions[pose_id]["diagnostic_intent"],
            "automatic_gates_passed": case["passed_automatic_gates"],
            "bed_clearance_m": probe["bed"]["minimum_body_clearance_m"],
            "visibility_count": probe["visibility_count"],
            "anchor_2ring_overlap_pair_count": si["anchor_scope"]["overlap_pair_count"],
            "global_overlap_pair_count": si["nonadjacent_intersection_pair_count"],
            "global_added_pair_count_vs_p0": len(current_pairs - baseline_pairs),
            "global_removed_pair_count_vs_p0": len(baseline_pairs - current_pairs),
            "max_anchor_xyz_delta_mm": max(item["xyz_delta_mm"] for item in details),
            "max_anchor_uv_delta_px": max(item["uv_delta_px"] for item in details),
            "max_anchor_normal_delta_deg": max(item["normal_delta_deg"] for item in details),
            "points": details,
        }
        rows.append(row)
        target = root / "preview_overlays" / f"{pose_id}.png"
        overlay(b.RUN_ROOT / "previews" / f"{pose_id}.png", probe, target)
        montage_items.append((pose_id, target))
    montage(montage_items, root / "pose_montage.png")
    report = {
        "schema": "enhanced-skel-pose-sensitivity-v1", "medical_truth": False, "medical_validated": False,
        "shape_scope": "beta=0 only", "baseline": "P0_BASE", "case_count": len(rows), "cases": rows,
        "existing_evidence_notice": "P0-P4 are pre-existing delivered evidence and are not described as first-time experiments.",
        "self_intersection_notice": "Anchor 2-ring zero is the hard gate. Global overlap counts are baseline-relative diagnostics and do not support a complete-body self-intersection-free claim.",
        "terminology": "engineering surface-reference geometric sensitivity; never medical drift or acupoint error",
    }
    b.write(root / "pose_sensitivity_report.json", report)
    with (root / "pose_sensitivity.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["pose_id", "point_id", "code", "xyz_delta_mm", "uv_delta_px", "normal_delta_deg", "triangle_area_ratio", "max_triangle_edge_delta_mm", "visible", "visibility_reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    eligible = [row["pose_id"] for row in rows if row["automatic_gates_passed"] and row["anchor_2ring_overlap_pair_count"] == 0]
    provisional = {
        "schema": "candidate-pose-profiles-base-shape-v1",
        "reserved_final_name": "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1",
        "status": "CANDIDATE_PENDING_VISUAL_REVIEW",
        "medical_truth": False, "medical_validated": False, "betas": [0.0] * 10,
        "profiles": eligible,
        "determinism_passed": deterministic["passed"],
        "baseline_restore_passed": deterministic["baseline_restore"]["passed"],
        "cannot_generalize_to_other_shapes": True,
        "not_authorized": ["Shape x Pose", "training", "medical validation"],
    }
    b.write(root / "candidate_pose_profiles_base_shape_v1.json", provisional)
    b.write(root / "verification.json", {
        "schema": "enhanced-pose-only-verification-v1",
        "passed": False,
        "automatic_gates_passed": primary["qualification_batch_passed"],
        "eligible_profile_count": len(eligible),
        "rejected_profile_count": len(rows) - len(eligible),
        "determinism_passed": deterministic["passed"],
        "baseline_restore_passed": deterministic["baseline_restore"]["passed"],
        "visual_review": "PENDING",
        "status": "PENDING_VISUAL_REVIEW_DO_NOT_CALL_QUALIFIED",
        "source_inputs_unchanged": b.read(root / "source_hashes_before.json") == b.read(root / "source_hashes_after.json"),
    })
    print(json.dumps({"finalized_reports": True, "visual_review": "PENDING", "eligible_count": len(eligible)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
