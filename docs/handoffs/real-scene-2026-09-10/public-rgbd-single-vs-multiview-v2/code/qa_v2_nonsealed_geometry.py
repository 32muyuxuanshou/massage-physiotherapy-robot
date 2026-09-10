"""QA/cache the planned non-SEALED HuMMan workset using the prior geometry module."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ALLOWED_SPLITS = {"TRAIN_NEW", "VAL_NEW"}
CAMERAS = ("kinect_008", "kinect_009")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_geometry_module(code_root: Path):
    sys.path.insert(0, str(code_root.resolve()))
    try:
        import humman_geometry
    finally:
        sys.path.pop(0)
    return humman_geometry


def assert_nonsealed_contract(plan: dict, workset_root: Path) -> None:
    if plan.get("sealed_or_reserve_pixels_selected") is not False:
        raise RuntimeError("plan does not explicitly exclude SEALED pixels")
    sealed = set(set(plan["v2_sealed_subjects_excluded"]) | set(plan["final_reserve_subjects_excluded"]))
    rows = plan["observations"]
    subjects = {row["subject"] for row in rows}
    if any(row["split"] not in ALLOWED_SPLITS for row in rows) or subjects & sealed:
        raise RuntimeError("plan contains SEALED or non-DEV/TRAIN/VAL subjects")
    sequences = {row["sequence"] for row in rows}
    if any(Path(sequence).name != sequence for sequence in sequences):
        raise RuntimeError("sequence must be one relative directory name")
    present = {p.name for p in workset_root.iterdir() if p.is_dir()}
    sealed_present = {name for name in present if name.split("_", 1)[0] in sealed}
    if sealed_present:
        raise RuntimeError(f"SEALED directory present; refusing all pixel reads: {sorted(sealed_present)}")
    if present - sequences:
        raise RuntimeError(f"unplanned sequence directories: {sorted(present - sequences)}")


def load_selected_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def camera_quality(camera: dict[str, np.ndarray]) -> dict:
    R = camera["R"]
    return {"rotation_orthonormal_max_abs": float(np.max(np.abs(R @ R.T - np.eye(3)))),
            "rotation_determinant": float(np.linalg.det(R)),
            "fx": float(camera["K"][0, 0]), "fy": float(camera["K"][1, 1])}


def torso_proxy(points: np.ndarray, K: np.ndarray, mask_color: np.ndarray) -> tuple[np.ndarray, dict]:
    """Return a body-core support proxy; this is not an anatomical torso label."""
    binary = (mask_color > 0).astype(np.uint8)
    interior = cv2.erode(binary, np.ones((7, 7), np.uint8), iterations=1)
    ys, xs = np.nonzero(interior)
    definition = "GEOMETRIC_BODY_CORE_PROXY_NOT_ANATOMY"
    if not len(xs):
        return points[:0], {"definition": definition, "points": 0}
    x0, x1 = np.quantile(xs, [0.20, 0.80])
    y0, y1 = np.quantile(ys, [0.20, 0.80])
    z = points[:, 2]
    u = K[0, 0] * points[:, 0] / z + K[0, 2]
    v = K[1, 1] * points[:, 1] / z + K[1, 2]
    ui, vi = np.rint(u).astype(np.int64), np.rint(v).astype(np.int64)
    inside = (ui >= 0) & (ui < binary.shape[1]) & (vi >= 0) & (vi < binary.shape[0])
    interior_hit = np.zeros(len(points), dtype=bool)
    interior_hit[inside] = interior[vi[inside], ui[inside]] > 0
    chosen = inside & interior_hit & (u >= x0) & (u <= x1) & (v >= y0) & (v <= y1)
    selected = points[chosen]
    return selected, {"definition": definition, "silhouette_erosion_kernel_px": 7,
                      "interior_quantile_box_xy": [0.20, 0.80], "points": int(len(selected)),
                      "fraction_of_registered_person_points": float(len(selected) / max(len(points), 1)),
                      "depth_median_m": float(np.median(selected[:, 2])) if len(selected) else None,
                      "depth_p05_m": float(np.quantile(selected[:, 2], 0.05)) if len(selected) else None,
                      "depth_p95_m": float(np.quantile(selected[:, 2], 0.95)) if len(selected) else None}


def nearest_metrics(a: np.ndarray, b: np.ndarray, max_points: int = 3000) -> dict:
    """Descriptive symmetric surface distances; cameras see different surfaces."""
    from scipy.spatial import cKDTree

    def sample(points: np.ndarray) -> np.ndarray:
        if len(points) <= max_points:
            return points.astype(np.float64)
        return points[np.linspace(0, len(points) - 1, max_points, dtype=np.int64)].astype(np.float64)

    a, b = sample(a), sample(b)
    if not len(a) or not len(b):
        return {"available": False}
    da = cKDTree(b).query(a, k=1, workers=1)[0]
    db = cKDTree(a).query(b, k=1, workers=1)[0]
    d = np.concatenate((da, db))
    return {"available": True, "role": "DESCRIPTIVE_ONLY_DIFFERENT_VISIBLE_SURFACES",
            "sample_points_each_max": max_points, "symmetric_nn_median_m": float(np.median(d)),
            "symmetric_nn_p95_m": float(np.quantile(d, 0.95))}


def make_panel(rgb: np.ndarray, mask: np.ndarray, depth: np.ndarray, title: str,
               width: int = 320) -> tuple[np.ndarray, np.ndarray]:
    overlay = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    green = np.zeros_like(overlay); green[:, :, 1] = 255
    hit = mask > 0
    overlay[hit] = (0.55 * overlay[hit] + 0.45 * green[hit]).astype(np.uint8)
    valid = depth > 0
    depth8 = np.zeros(depth.shape, np.uint8)
    if valid.any():
        lo, hi = np.quantile(depth[valid], [0.02, 0.98])
        depth8[valid] = np.clip((depth[valid] - lo) * 255.0 / max(float(hi - lo), 1.0), 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(255 - depth8, cv2.COLORMAP_TURBO); colored[~valid] = 0
    target_h = round(overlay.shape[0] * width / overlay.shape[1])
    overlay = cv2.resize(overlay, (width, target_h), interpolation=cv2.INTER_AREA)
    colored = cv2.resize(colored, (width, target_h), interpolation=cv2.INTER_NEAREST)
    cv2.putText(overlay, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
    return overlay, colored


def save_contact_sheets(rows: list[dict], output_dir: Path, rows_per_page: int = 13) -> list[dict]:
    sheets = []
    for page, start in enumerate(range(0, len(rows), rows_per_page), 1):
        images = []
        for row in rows[start:start + rows_per_page]:
            a = row["views"]["kinect_008"]; b = row["views"]["kinect_009"]
            pa = make_panel(a["rgb"], a["mask"], a["depth"], f"{row['id']} cam008")
            pb = make_panel(b["rgb"], b["mask"], b["depth"], f"{row['split']} cam009")
            images.append(np.concatenate((pa[0], pa[1], pb[0], pb[1]), axis=1))
        sheet = np.concatenate(images, axis=0)
        path = output_dir / f"registration_contact_sheet_{page:02d}.jpg"
        if not cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88]):
            raise RuntimeError(f"cannot write {path}")
        sheets.append({"path": str(path.resolve()), "sha256": sha256(path), "rows": len(images)})
    return sheets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "extraction-report", "workset-root", "geometry-code-root", "output-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--min-person-points", type=int, default=5000)
    parser.add_argument("--min-torso-proxy-points", type=int, default=750)
    parser.add_argument("--min-projection-retention", type=float, default=0.80)
    args = parser.parse_args()
    plan, extraction = read_json(args.plan), read_json(args.extraction_report)
    if extraction.get("status") != "DECODE_AND_FRAME_ID_QA_PASS_GEOMETRY_PENDING":
        raise RuntimeError(f"selective extraction is not complete: {extraction.get('status')}")
    if extraction.get("sealed_or_reserve_pixels_materialized") is not False:
        raise RuntimeError("extraction report does not explicitly exclude SEALED pixels")
    assert_nonsealed_contract(plan, args.workset_root)
    geometry = load_geometry_module(args.geometry_code_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    cache_root = args.output_root / "sample_cache"; cache_root.mkdir(exist_ok=True)
    results, visual_rows = [], []
    for observation in plan["observations"]:
        seq = observation["sequence"]
        cameras = geometry.load_cameras(args.workset_root / seq / "cameras.json")
        for frame_id in observation["frame_ids"]:
            item_id = f"{seq}_f{frame_id:06d}"
            views, metrics = {}, {}
            payload = {"subject": np.asarray(observation["subject"]), "sequence": np.asarray(seq),
                       "split": np.asarray(observation["split"]), "frame_id": np.asarray(frame_id, np.int32),
                       "geometry_contract": np.asarray("HuMMan OpenCV world2cam; uint16 millimetre Z-depth"),
                       "torso_proxy_contract": np.asarray("GEOMETRIC_BODY_CORE_PROXY_NOT_ANATOMY")}
            usable, reasons = True, []
            for device in CAMERAS:
                suffix = device.removeprefix("kinect_")
                color_camera = cameras[f"kinect_color_{suffix}"]; depth_camera = cameras[f"kinect_depth_{suffix}"]
                rgb = load_selected_rgb(args.workset_root / seq / "selected_rgb" / device / f"{frame_id:06d}.png")
                depth = geometry.read_image(args.workset_root / seq / "kinect_depth" / device / f"{frame_id:06d}.png", cv2.IMREAD_UNCHANGED)
                mask_depth = geometry.read_image(args.workset_root / seq / "kinect_mask" / device / f"{frame_id:06d}.png", cv2.IMREAD_GRAYSCALE)
                if depth is None or mask_depth is None:
                    raise FileNotFoundError(f"missing selected depth/mask: {item_id}/{device}")
                points, mask_color, registration = geometry.registered_person_points(depth, mask_depth, depth_camera, color_camera, rgb.shape[:2])
                torso_points, torso_report = torso_proxy(points, color_camera["K"], mask_color)
                retention = registration["person_points_retained_after_projection"] / max(registration["raw_valid_person_depth_points"], 1)
                camera_report = camera_quality(color_camera); view_reasons = []
                if len(points) < args.min_person_points: view_reasons.append("TOO_FEW_REGISTERED_PERSON_POINTS")
                if len(torso_points) < args.min_torso_proxy_points: view_reasons.append("TOO_FEW_TORSO_PROXY_POINTS")
                if retention < args.min_projection_retention: view_reasons.append("LOW_DEPTH_TO_COLOR_PROJECTION_RETENTION")
                if camera_report["rotation_orthonormal_max_abs"] > 1e-5 or abs(camera_report["rotation_determinant"] - 1.0) > 1e-5:
                    view_reasons.append("INVALID_COLOR_CAMERA_ROTATION")
                if view_reasons:
                    usable = False; reasons.extend(f"{device}:{reason}" for reason in view_reasons)
                metrics[device] = {"rgb_shape": list(rgb.shape), "rgb_dtype": str(rgb.dtype),
                                   "depth_shape": list(depth.shape), "depth_dtype": str(depth.dtype),
                                   "depth_nonzero_pixels": int(np.count_nonzero(depth)),
                                   "depth_mask_pixels": int(np.count_nonzero(mask_depth)),
                                   "registration": registration, "projection_retention": float(retention),
                                   "projected_mask_pixels": int(np.count_nonzero(mask_color)),
                                   "torso_proxy": torso_report, "camera": camera_report,
                                   "auto_gate_reasons": view_reasons}
                views[device] = {"rgb": rgb, "depth": depth, "mask": mask_color, "points": points,
                                 "torso_points": torso_points, "color_camera": color_camera,
                                 "depth_camera": depth_camera, "mask_depth": mask_depth}
                # Preserve the exact prepare_observations.py / trainer A-B cache
                # interface: cam008 is Camera A and cam009 is held-out Camera B.
                tag = "a" if device == "kinect_008" else "b"
                payload.update({f"rgb_{tag}": rgb, f"depth_{tag}": depth, f"mask_depth_{tag}": mask_depth,
                                f"mask_color_{tag}": mask_color, f"points_{tag}": points,
                                f"torso_proxy_points_{tag}": torso_points,
                                f"bbox_{tag}": geometry.mask_bbox(mask_color),
                                f"K_{tag}": color_camera["K"], f"R_{tag}": color_camera["R"], f"T_{tag}": color_camera["T"],
                                f"K_depth_{tag}": depth_camera["K"], f"R_depth_{tag}": depth_camera["R"], f"T_depth_{tag}": depth_camera["T"]})
            p008_world = geometry.camera_to_world(views["kinect_008"]["points"], views["kinect_008"]["color_camera"])
            p008_in_009 = geometry.world_to_camera(p008_world, views["kinect_009"]["color_camera"])
            cross_camera = nearest_metrics(p008_in_009, views["kinect_009"]["points"])
            cache_path = cache_root / observation["split"].lower() / f"{item_id}.npz"; cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_path, **payload)
            result = {"id": item_id, "subject": observation["subject"], "sequence": seq, "action": observation["action"],
                      "split": observation["split"], "frame_id": frame_id, "usable": usable,
                      "auto_gate_reasons": sorted(set(reasons)), "visual_registration_review": "PENDING_CONTACT_SHEET_REVIEW",
                      "views": metrics, "cross_camera_surface_consistency": cross_camera,
                      "cache_npz": str(cache_path.resolve()), "cache_sha256": sha256(cache_path)}
            results.append(result); visual_rows.append({"id": item_id, "split": observation["split"], "views": views})
            print("CACHED", item_id, "usable", usable, flush=True)
    sheets = save_contact_sheets(visual_rows, args.output_root)
    split_counts = {name: sum(row["split"] == name for row in results) for name in sorted(ALLOWED_SPLITS)}
    usable_counts = {name: sum(row["split"] == name and row["usable"] for row in results) for name in sorted(ALLOWED_SPLITS)}
    report = {"status": "AUTO_QA_COMPLETE_VISUAL_REVIEW_PENDING", "task": "PUBLIC_RGBD_SINGLE_VS_MULTIVIEW_V2",
              "scope": "NONSEALED_WORKSET_ONLY", "sealed_pixels_read": False,
              "source_plan": str(args.plan.resolve()), "source_plan_sha256": sha256(args.plan),
              "source_split_seed_from_plan": plan["subject_split_seed"],
              "source_extraction_report": str(args.extraction_report.resolve()),
              "geometry_implementation": str((args.geometry_code_root / "humman_geometry.py").resolve()),
              "geometry_implementation_sha256": sha256(args.geometry_code_root / "humman_geometry.py"),
              "torso_validity_scope": "GEOMETRIC_BODY_CORE_PROXY_NOT_ANATOMY",
              "auto_gate": {"min_person_points_each_view": args.min_person_points,
                            "min_torso_proxy_points_each_view": args.min_torso_proxy_points,
                            "min_projection_retention_each_view": args.min_projection_retention,
                            "camera_rotation_tolerance": 1e-5, "cross_camera_surface_consistency_is_gate": False},
              "observations": len(results), "counts_by_split": split_counts,
              "auto_usable": sum(row["usable"] for row in results), "auto_usable_by_split": usable_counts,
              "contact_sheets": sheets, "results": results}
    write_json(args.output_root / "HUMMAN_V2_NEW_NONSEALED_GEOMETRY_QA_V1.json", report)
    print("QA_COMPLETE", report["auto_usable"], "/", len(results), flush=True)


if __name__ == "__main__":
    main()

