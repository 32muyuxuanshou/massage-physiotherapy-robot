"""Prepare Camera-A fit and Camera-B held-out HuMMan observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from humman_geometry import load_humman_view


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True,
                    help="JSON with observations[{id,sequence,frame_id,camera_a,camera_b}]")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--min-person-points", type=int, default=5000)
    args = ap.parse_args()
    spec = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    for row in spec["observations"]:
        if row["camera_a"] == row["camera_b"]:
            raise ValueError(f"{row['id']}: Camera A and B must differ")
        views = {key: load_humman_view(args.data_root, row["sequence"], row[key], row["frame_id"])
                 for key in ("camera_a", "camera_b")}
        if min(len(v["points_color"]) for v in views.values()) < args.min_person_points:
            raise ValueError(f"{row['id']}: too few registered person-depth points")
        out = args.output_dir / f"{row['id']}.npz"
        payload = {}
        for label, key in (("a", "camera_a"), ("b", "camera_b")):
            view = views[key]
            payload.update({
                f"rgb_{label}": view["rgb"], f"mask_{label}": view["mask"],
                f"mask_depth_{label}": view["mask_depth"],
                f"depth_{label}": view["depth"],
                f"points_{label}": view["points_color"], f"bbox_{label}": view["bbox"],
                f"K_{label}": view["color_camera"]["K"],
                f"R_{label}": view["color_camera"]["R"],
                f"T_{label}": view["color_camera"]["T"],
                f"K_depth_{label}": view["depth_camera"]["K"],
                f"R_depth_{label}": view["depth_camera"]["R"],
                f"T_depth_{label}": view["depth_camera"]["T"],
            })
        np.savez_compressed(out, **payload)
        prepared.append({**row, "observation_npz": str(out.resolve()), "sha256": digest(out),
                         "camera_a_registration": views["camera_a"]["registration"],
                         "camera_b_registration": views["camera_b"]["registration"],
                         "camera_b_role": "held_out_never_used_by_optimizer"})
    result = {"status": "PREPARED", "source_manifest": str(args.manifest.resolve()),
              "geometry_contract": "HuMMan OpenCV world2cam; uint16 millimetre Z-depth",
              "observations": prepared}
    (args.output_dir / "prepared_manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
