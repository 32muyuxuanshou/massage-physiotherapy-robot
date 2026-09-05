from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validation", "untouched_test"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.phase == "untouched_test" and not (root / "decoder_contract_freeze_receipt.json").is_file():
        raise RuntimeError("Untouched test remains locked")
    manifest = read(root / f"{args.phase}_sample_generation_report.json")
    if not manifest["passed"]:
        raise RuntimeError("Sample generation gate did not pass")
    images, uv, visible, reasons, sample_ids, cameras, kinds, directions, paths = [], [], [], [], [], [], [], [], []
    point_ids = None
    for row in manifest["samples"]:
        sample = Path(row["sample"])
        labels = read(sample / "labels.json")
        ids = [point["point_id"] for point in labels["points"]]
        point_ids = point_ids or ids
        if ids != point_ids:
            raise RuntimeError("Point order changed")
        with Image.open(sample / "rgb_model.png") as image:
            images.append(np.asarray(image.convert("RGB").resize((160, 128), Image.Resampling.BILINEAR), dtype=np.uint8))
        uv.append([point["uv_pixel_opencv"] for point in labels["points"]])
        reason = [point["visibility_reason"] for point in labels["points"]]
        reasons.append(reason); visible.append([value == "VISIBLE" for value in reason])
        sample_ids.append(row["sample_id"]); cameras.append(row["camera_id"]); kinds.append(row["camera_kind"])
        directions.append(row.get("direction") or "NONE"); paths.append(str(sample))
    output = root / f"{args.phase}_decoder_cache.npz"
    np.savez_compressed(
        output, images_rgb=np.asarray(images), uv=np.asarray(uv, np.float32),
        visible=np.asarray(visible, np.uint8), reasons=np.asarray(reasons),
        sample_ids=np.asarray(sample_ids), camera_ids=np.asarray(cameras), camera_kinds=np.asarray(kinds),
        directions=np.asarray(directions), sample_paths=np.asarray(paths), point_ids=np.asarray(point_ids),
    )
    print(output)


if __name__ == "__main__":
    main()
