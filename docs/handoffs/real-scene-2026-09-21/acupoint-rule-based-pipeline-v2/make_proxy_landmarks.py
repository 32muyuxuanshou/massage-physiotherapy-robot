"""Build an explicitly provisional landmark frame for geometry sanity only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


LEVEL_FRACTIONS = {"C7_T1": 0.08, "T3": 0.23, "T5": 0.38, "T9": 0.68, "L2": 0.90}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vertices", type=Path, required=True)
    ap.add_argument("--faces", type=Path, required=True)
    ap.add_argument("--posterior-mask", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--vertical-order", choices=["min_to_max", "max_to_min"], default="min_to_max")
    ap.add_argument("--lateral-sign", type=float, choices=[-1.0, 1.0], default=1.0)
    args = ap.parse_args()
    vertices = np.asarray(np.load(args.vertices), dtype=np.float64)
    faces = np.asarray(np.load(args.faces), dtype=np.int64)
    mask = json.loads(args.posterior_mask.read_text(encoding="utf-8"))
    ids = np.asarray(mask["face_ids"], dtype=np.int64)
    centroids = vertices[faces[ids]].mean(axis=1)
    y_min, y_max = float(centroids[:, 1].min()), float(centroids[:, 1].max())
    x_width = float(np.percentile(centroids[:, 0], 95) - np.percentile(centroids[:, 0], 5))
    # This span is only a deterministic proxy for the proportional body-measurement
    # scale. It is deliberately not called a medical B-cun measurement.
    proxy_span_cun = 8.0
    native_per_b_cun = x_width / proxy_span_cun
    levels = {}
    for name, fraction in LEVEL_FRACTIONS.items():
        if args.vertical_order == "min_to_max":
            y = y_min + fraction * (y_max - y_min)
        else:
            y = y_max - fraction * (y_max - y_min)
        band = max((y_max - y_min) * 0.035, np.finfo(float).eps)
        selected = centroids[np.abs(centroids[:, 1] - y) <= band]
        if selected.size == 0:
            selected = centroids[np.argsort(np.abs(centroids[:, 1] - y))[:8]]
        point = np.median(selected, axis=0)
        point[0] = float(np.median(selected[:, 0]))
        levels[name] = {
            "point": point.tolist(), "lateral_axis": [args.lateral_sign, 0.0, 0.0],
            "native_per_b_cun": native_per_b_cun,
            "proxy_vertical_fraction": fraction,
            "proxy_band_native": band
        }
    output = {
        "schema": "PROXY_LANDMARK_FRAME_V1", "status": "PROXY_GEOMETRY_SANITY_ONLY",
        "medical_truth": False, "coordinate_frame": "mesh_native",
        "source": "posterior_mask_face_centroid_interpolation",
        "proxy_span_cun": proxy_span_cun, "posterior_face_count": int(len(ids)),
        "coordinate_orientation_contract": {"vertical_order": args.vertical_order, "lateral_sign": args.lateral_sign},
        "posterior_centroid_bbox_native": {"min": centroids.min(axis=0).tolist(), "max": centroids.max(axis=0).tolist()},
        "levels": levels,
        "limitations": [
            "No vertebral or skeletal landmark is observed.",
            "Vertical fractions and lateral scale are synthetic engineering proxies.",
            "Not for clinical accuracy, ground truth, or treatment execution."
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
