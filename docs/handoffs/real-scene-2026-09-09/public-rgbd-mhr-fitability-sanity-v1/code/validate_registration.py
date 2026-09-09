"""Create an auditable depth-to-color projection overlay for one prepared view."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from humman_geometry import project, transform_camera, unproject_z_depth


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--observation", type=Path, required=True)
    ap.add_argument("--view", choices=("a", "b"), required=True)
    ap.add_argument("--output-image", type=Path, required=True)
    ap.add_argument("--output-json", type=Path, required=True)
    ap.add_argument("--point-radius", type=int, default=2)
    args = ap.parse_args()
    data = np.load(args.observation)
    rgb = data[f"rgb_{args.view}"].copy()
    mask = data[f"mask_{args.view}"] > 0
    color_camera = {key: data[f"{key}_{args.view}"] for key in ("K", "R", "T")}
    depth_camera = {key: data[f"{key}_depth_{args.view}"] for key in ("K", "R", "T")}
    points_depth, _ = unproject_z_depth(data[f"depth_{args.view}"], depth_camera["K"])
    points_color = transform_camera(points_depth, depth_camera, color_camera)
    uv, positive = project(points_color, color_camera["K"])
    pix = np.rint(uv[positive]).astype(np.int32)
    z = points_color[positive, 2]
    valid = ((pix[:, 0] >= 0) & (pix[:, 0] < rgb.shape[1]) &
             (pix[:, 1] >= 0) & (pix[:, 1] < rgb.shape[0]))
    pix, z = pix[valid], z[valid]
    # Z-buffer all projected depth, before consulting the person mask.
    registered_depth = np.full(mask.shape, np.inf, np.float32)
    np.minimum.at(registered_depth, (pix[:, 1], pix[:, 0]), z.astype(np.float32))
    occupied = np.zeros(mask.shape, np.uint8)
    occupied[pix[:, 1], pix[:, 0]] = 1
    if args.point_radius:
        k = 2 * args.point_radius + 1
        occupied = cv2.dilate(occupied, np.ones((k, k), np.uint8))
    covered = occupied.astype(bool) & mask
    overlay = rgb.astype(np.float32)
    valid_z = np.isfinite(registered_depth)
    if valid_z.any():
        lo, hi = np.percentile(registered_depth[valid_z], [2, 98])
        scaled = np.zeros(mask.shape, np.float32)
        scaled[valid_z] = np.clip((registered_depth[valid_z] - lo) / max(hi - lo, 1e-6), 0, 1)
        colors = cv2.applyColorMap((255 * (1 - scaled)).astype(np.uint8), cv2.COLORMAP_TURBO)
        colors = cv2.cvtColor(colors, cv2.COLOR_BGR2RGB)
        overlay[valid_z] = 0.45 * overlay[valid_z] + 0.55 * colors[valid_z]
    boundary = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_GRADIENT,
                                np.ones((5, 5), np.uint8)).astype(bool)
    overlay[boundary] = np.asarray([255, 255, 0])
    args.output_image.parent.mkdir(parents=True, exist_ok=True)
    encoded_ok, encoded = cv2.imencode(
        args.output_image.suffix or ".png",
        cv2.cvtColor(overlay.astype(np.uint8), cv2.COLOR_RGB2BGR),
    )
    if not encoded_ok:
        raise RuntimeError(f"cannot encode registration overlay: {args.output_image}")
    args.output_image.write_bytes(encoded.tobytes())
    report = {
        "status": "PROJECTION_OVERLAY_GENERATED_REQUIRES_VISUAL_REVIEW",
        "observation": str(args.observation.resolve()), "view": args.view,
        "all_projected_depth_points_in_color_image": int(len(pix)),
        "person_mask_pixels": int(mask.sum()),
        "projected_person_support_coverage": float(covered.sum() / max(mask.sum(), 1)),
        "point_radius_pixels": args.point_radius,
        "overlay_legend": {"turbo_color": "z-buffered metric depth projected independently into color",
                           "yellow": "person-mask boundary"},
        "claim_limit": "the mask is defined in depth space and projected by the same calibration, so coverage is only an implementation check; RGB boundary alignment requires visual review and does not prove sub-centimetre registration",
    }
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
