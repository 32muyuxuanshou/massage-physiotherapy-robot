#!/usr/bin/env python3
"""Make a compact RGB/depth/mask sheet for the mandatory smoke visual gate."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=10)
    parser.add_argument("--panel-size", type=int, default=96)
    args = parser.parse_args()
    manifest = json.loads((args.dataset / "dataset_manifest.json").read_text(encoding="utf-8"))
    width, header = args.panel_size * 3, 18
    rows = math.ceil(len(manifest["records"]) / args.columns)
    sheet = Image.new("RGB", (args.columns * width, rows * (args.panel_size + header)), "white")
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
    for index, record in enumerate(manifest["records"]):
        sample = args.dataset / "samples" / record["sample_id"]
        rgb = Image.open(sample / "rgb.png").convert("RGB").resize((args.panel_size, args.panel_size))
        mask = Image.open(sample / "mask.png").convert("RGB").resize((args.panel_size, args.panel_size))
        depth = np.load(sample / "depth_z_m.npy")
        valid = depth > 0
        depth_u8 = np.zeros(depth.shape, dtype=np.uint8)
        if np.any(valid):
            lo, hi = np.percentile(depth[valid], [2, 98])
            depth_u8[valid] = np.clip((hi - depth[valid]) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
        depth_image = Image.fromarray(depth_u8, mode="L").convert("RGB").resize((args.panel_size, args.panel_size))
        x, y = (index % args.columns) * width, (index // args.columns) * (args.panel_size + header)
        draw.text((x + 3, y + 3), f"{record['sample_id']} I{record['identity_index']} V{record['view_index']}", fill="black", font=font)
        sheet.paste(rgb, (x, y + header))
        sheet.paste(depth_image, (x + args.panel_size, y + header))
        sheet.paste(mask, (x + 2 * args.panel_size, y + header))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=90)
    print(json.dumps({"output": str(args.output), "sample_count": len(manifest["records"]), "layout": "RGB|inverse-depth|mask"}))


if __name__ == "__main__":
    main()
