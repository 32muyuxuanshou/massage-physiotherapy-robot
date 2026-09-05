from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CASES = (
    "C02_SHORT_NARROW_THIN__D01_SCAPULA_ABDUCTION_PAIR_P6",
    "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4",
)
PROFILES = (
    "TRUNC_LEFT_MILD",
    "TRUNC_LEFT_MODERATE",
    "TRUNC_RIGHT_MILD",
    "TRUNC_RIGHT_MODERATE",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "dataset_manifest.json").read_text(encoding="utf-8-sig"))
    by_id = {row["sample_id"]: row for row in manifest["truncation_train_pool"]}
    tile_w, tile_h, head_h = 400, 320, 36
    canvas = Image.new("RGB", (tile_w * 4, (tile_h + head_h) * 2), (25, 25, 27))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    selected = []
    for row_index, case_id in enumerate(CASES):
        for col_index, profile in enumerate(PROFILES):
            sample_id = f"TRUNCV2__{case_id}__{profile}__A00"
            row = by_id[sample_id]
            path = root / row["rgb_relative_path"]
            image = Image.open(path).convert("RGB")
            image.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
            x = col_index * tile_w
            y = row_index * (tile_h + head_h)
            canvas.paste(image, (x + (tile_w - image.width) // 2, y + head_h + (tile_h - image.height) // 2))
            draw.text((x + 6, y + 10), profile.replace("TRUNC_", ""), fill=(255, 255, 255), font=font)
            selected.append({"sample_id": sample_id, "rgb": row["rgb_relative_path"], "sha256": row["rgb_sha256"]})
    visual_dir = root / "visuals"
    visual_dir.mkdir(parents=True, exist_ok=True)
    montage = visual_dir / "v2_truncation_training_montage.png"
    canvas.save(montage)
    (visual_dir / "visual_index.json").write_text(
        json.dumps({"schema": "failure-driven-pilot-visual-index-v2", "montage": str(montage), "items": selected}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(montage)


if __name__ == "__main__":
    main()
