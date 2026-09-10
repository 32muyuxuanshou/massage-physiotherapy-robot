"""Audit bounded Camera-A depth translation of the frozen Official MHR mesh.

The correction estimator sees Camera A only. Camera B is used after correction
solely as a held-out engineering label. Bounds are derived from DEVELOPMENT raw
corrections before SELECTOR_VAL is scored. No system-sealed manifest is accepted.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

import numpy as np
import torch
from scipy.spatial import cKDTree

def load(path):
    return json.loads(Path(path).read_text())


def fixed_indices(n, key, cap=5000):
    if n <= cap:
        return np.arange(n)
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    return np.sort(np.random.default_rng(seed).choice(n, cap, replace=False))


def surface_anchors(vertices, faces, face_index, barycentric):
    tri = vertices[faces[face_index]]
    return (tri * barycentric[:, :, None]).sum(axis=1)


def robust_translation(points, anchors, mode, iterations=6):
    translation = np.zeros(3, np.float64)
    for _ in range(iterations):
        moved = anchors + translation
        distance, nearest = cKDTree(moved).query(points, workers=-1)
        keep = distance <= np.quantile(distance, 0.80)
        residual = points[keep] - moved[nearest[keep]]
        step = np.median(residual, axis=0)
        if mode == "tz":
            step[:2] = 0.0
        step = np.clip(step, -0.05, 0.05)
        translation += step
        if np.linalg.norm(step) < 1e-5:
            break
    return translation


def subject_equal(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["subject_id"], []).append(row[key])
    subject = {s: float(np.median(v)) for s, v in grouped.items()}
    return {"subject_count": len(subject),
            "mean_of_subject_frame_medians": float(np.mean(list(subject.values()))),
            "subjects": subject}


def score_split(rows, official_meshes, faces, anchors_spec, bounds, constant_bias):
    out = []
    for row in rows:
        start = time.perf_counter()
        with np.load(row["path"]) as z:
            points_a = z["points_a"].astype(np.float64)
            idx_b = np.asarray(row.get("b_indices", fixed_indices(len(z["points_b"]), row["id"] + ":B")), np.int64)
            idx_b = idx_b[fixed_indices(len(idx_b), row["id"] + ":B5000")]
            points_b = z["points_b"][idx_b].astype(np.float64)
            vertices_a = official_meshes[row["id"]]
            anchors = surface_anchors(vertices_a, faces, *anchors_spec)
            raw_tz = robust_translation(points_a, anchors, "tz")
            raw_xyz = robust_translation(points_a, anchors, "txyz")
            oor_tz = abs(raw_tz[2]) > bounds["tz_abs_m"]
            oor_xyz = np.linalg.norm(raw_xyz) > bounds["txyz_norm_m"]
            tz = np.zeros(3) if oor_tz else raw_tz
            xyz = np.zeros(3) if oor_xyz else raw_xyz
            def to_b(delta):
                return world_to_camera(camera_to_world(vertices_a + delta, z["R_a"], z["T_a"]), z["R_b"], z["T_b"])
            metrics = {}
            for name, delta in (("official", np.zeros(3)), ("tz", tz), ("txyz", xyz), ("constant_txyz", constant_bias)):
                metrics[name] = point_to_triangle(points_b, to_b(delta), faces)
        out.append({"id": row["id"], "subject_id": row["subject_id"],
                    "raw_tz_m": raw_tz.tolist(), "raw_txyz_m": raw_xyz.tolist(),
                    "applied_tz_m": tz.tolist(), "applied_txyz_m": xyz.tolist(),
                    "tz_norm_m": float(np.linalg.norm(raw_tz)), "txyz_norm_m": float(np.linalg.norm(raw_xyz)),
                    "tz_out_of_range": bool(oor_tz), "txyz_out_of_range": bool(oor_xyz),
                    "official_mm": metrics["official"]["median_mm"],
                    "tz_mm": metrics["tz"]["median_mm"],
                    "txyz_mm": metrics["txyz"]["median_mm"],
                    "constant_txyz_mm": metrics["constant_txyz"]["median_mm"],
                    "latency_s": time.perf_counter() - start})
    summary = {k: subject_equal(out, k) for k in ("official_mm", "tz_mm", "txyz_mm", "constant_txyz_mm")}
    summary["frame_counts"] = {
        "tz_better_than_official": sum(r["tz_mm"] < r["official_mm"] for r in out),
        "txyz_better_than_official": sum(r["txyz_mm"] < r["official_mm"] for r in out),
        "tz_out_of_range": sum(r["tz_out_of_range"] for r in out),
        "txyz_out_of_range": sum(r["txyz_out_of_range"] for r in out)}
    summary["median_total_correction_and_exact_eval_s"] = float(np.median([r["latency_s"] for r in out]))
    low = [r for r in out if r["official_mm"] < 30.0]
    summary["low_official_error_under_30mm"] = {
        "frame_count": len(low),
        "tz_regressed": sum(r["tz_mm"] > r["official_mm"] for r in low),
        "txyz_regressed": sum(r["txyz_mm"] > r["official_mm"] for r in low)}
    return out, summary


def main():
    ap = argparse.ArgumentParser()
    for name in ("sam-repo", "official", "mhr", "development-rows", "selector-val-rows", "anchors", "constant-baseline", "surface-metrics", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    if "sealed" in str(args.development_rows).lower() and "v2_sealed" not in str(args.development_rows).lower():
        raise ValueError("DEVELOPMENT rows unexpectedly name a new system sealed set")
    sys.path[:0] = [str(args.sam_repo), str(args.surface_metrics.parent)]
    global camera_to_world, point_to_triangle, world_to_camera
    from surface_metrics import camera_to_world, point_to_triangle, world_to_camera
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    development = load(args.development_rows)["rows"]
    selector_val = load(args.selector_val_rows)["rows"]
    model, cfg = load_sam_3d_body(str(args.official), device="cuda", mhr_path=str(args.mhr))
    model.eval(); estimator = SAM3DBodyEstimator(model, cfg)
    faces = model.head_pose.faces.cpu().numpy().astype(np.int64)
    meshes = {}
    inference_s = []
    with torch.no_grad():
        for row in development + selector_val:
            with np.load(row["path"]) as z:
                rgb, bbox, K = z["rgb_a"].copy(), z["bbox_a"].copy(), z["K_a"].copy()
            torch.cuda.synchronize(); start = time.perf_counter()
            batch = recursive_to(prepare_batch(rgb, estimator.transform, bbox[None].astype(np.float32), None, None), "cuda")
            batch["cam_int"] = torch.as_tensor(K[None], device="cuda").to(batch["img"])
            model._initialize_batch(batch)
            pred = model.forward_step(batch, decoder_type="body")["mhr"]
            meshes[row["id"]] = (pred["pred_vertices"] + pred["pred_cam_t"][:, None])[0].cpu().numpy()
            torch.cuda.synchronize(); inference_s.append(time.perf_counter() - start)
    anchor_npz = np.load(args.anchors)
    anchor_spec = (anchor_npz["face_index"], anchor_npz["barycentric"].astype(np.float64))
    # Bounds use DEVELOPMENT only. Raw estimates are computed before any B score is read.
    raw_dev_tz, raw_dev_xyz = [], []
    for row in development:
        with np.load(row["path"]) as z:
            anchors = surface_anchors(meshes[row["id"]], faces, *anchor_spec)
            raw_dev_tz.append(robust_translation(z["points_a"].astype(np.float64), anchors, "tz"))
            raw_dev_xyz.append(robust_translation(z["points_a"].astype(np.float64), anchors, "txyz"))
    bounds = {
        "rule": "clip DEVELOPMENT 95th percentile to [0.03,0.20] m; out-of-range falls back to Official",
        "tz_abs_m": float(np.clip(np.quantile(np.abs(np.asarray(raw_dev_tz)[:, 2]), .95), .03, .20)),
        "txyz_norm_m": float(np.clip(np.quantile(np.linalg.norm(raw_dev_xyz, axis=1), .95), .03, .20))}
    constant_bias = np.asarray(load(args.constant_baseline)["constant_bias_camera_a_m"], np.float64)
    dev_rows, dev_summary = score_split(development, meshes, faces, anchor_spec, bounds, constant_bias)
    val_rows, val_summary = score_split(selector_val, meshes, faces, anchor_spec, bounds, constant_bias)
    result = {"status": "CHEAP_CORRECTION_DEVELOPMENT_AND_SELECTOR_VAL_COMPLETE",
              "data_contract": {"development_rows": str(args.development_rows), "selector_val_rows": str(args.selector_val_rows),
                                "new_system_sealed_read": False, "camera_a_estimation_only": True, "camera_b_labels_only": True,
                                "evaluation_points_per_frame": 5000},
              "algorithm": {"anchors": 16384, "iterations": 6, "trim_fraction": 0.20,
                            "step_bound_m": 0.05, "out_of_range_action": "fallback_official", "bounds": bounds},
              "constant_bias_camera_a_m": constant_bias.tolist(),
              "official_inference_median_s": float(np.median(inference_s)),
              "development": {"summary": dev_summary, "rows": dev_rows},
              "selector_val": {"summary": val_summary, "rows": val_rows},
              "system_sealed_opened": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"bounds": bounds, "development": dev_summary, "selector_val": val_summary}, indent=2))


if __name__ == "__main__":
    main()
