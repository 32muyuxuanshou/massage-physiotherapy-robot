#!/usr/bin/env python3
"""Build a compact visual review montage for TRUNCATION_GATE_V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROFILES = (
    "TRUNC_LEFT_MILD",
    "TRUNC_LEFT_MODERATE",
    "TRUNC_RIGHT_MILD",
    "TRUNC_RIGHT_MODERATE",
)

CASES = (
    "C02_SHORT_NARROW_THIN__D01_SCAPULA_ABDUCTION_PAIR_P6",
    "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    visual_dir = root / "visuals"
    visual_dir.mkdir(parents=True, exist_ok=True)
    matrix = json.loads((root / "truncation_matrix_report.json").read_text(encoding="utf-8"))
    sample_meta = {item["sample_id"]: item for item in matrix["samples"]}

    tile_w, tile_h, header_h = 480, 384, 52
    canvas = Image.new("RGB", (tile_w * 4, (tile_h + header_h) * 2), "#202124")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    entries = []

    for row, case_id in enumerate(CASES):
        for col, profile_id in enumerate(PROFILES):
            sample_id = f"{case_id}__{profile_id}"
            image_path = root / "matrix" / "samples" / sample_id / "overlay.png"
            if not image_path.exists() or sample_id not in sample_meta:
                raise FileNotFoundError(sample_id)

            source = Image.open(image_path).convert("RGB")
            source.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
            x0 = col * tile_w
            y0 = row * (tile_h + header_h)
            paste_x = x0 + (tile_w - source.width) // 2
            paste_y = y0 + header_h + (tile_h - source.height) // 2
            canvas.paste(source, (paste_x, paste_y))

            truncation = sample_meta[sample_id]["truncation_qc"]
            severity = truncation["severity"]
            visible_count = truncation["reason_counts"].get("VISIBLE", 0)
            out_of_frame_count = truncation["reason_counts"].get("OUT_OF_FRAME", 0)
            title = f"{profile_id.replace('TRUNC_', '')} | visible {visible_count} | OOF {out_of_frame_count}"
            subtitle = f"bbox trunc {severity['bbox_area_truncation_fraction']:.3f} | skin ratio {truncation['skin_mask_area_ratio_to_baseline']:.3f}"
            draw.text((x0 + 8, y0 + 8), title, fill="#ffffff", font=font)
            draw.text((x0 + 8, y0 + 28), subtitle, fill="#c6dafc", font=font)

            entries.append(
                {
                    "sample_id": sample_id,
                    "overlay": str(image_path),
                    "visible_count": visible_count,
                    "out_of_frame_count": out_of_frame_count,
                    "body_bbox_truncation_fraction": severity["bbox_area_truncation_fraction"],
                    "skin_mask_ratio_to_baseline": truncation["skin_mask_area_ratio_to_baseline"],
                    "out_of_frame_point_ids": truncation["out_of_frame_point_ids"],
                }
            )

    montage = visual_dir / "truncation_profile_montage.png"
    canvas.save(montage)
    index = {
        "schema": "truncation-gate-visual-index-v2",
        "purpose": "Representative manual review only; not a substitute for the 68-cell numeric gate.",
        "montage": str(montage),
        "entries": entries,
    }
    (visual_dir / "visual_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(montage)


if __name__ == "__main__":
    main()
