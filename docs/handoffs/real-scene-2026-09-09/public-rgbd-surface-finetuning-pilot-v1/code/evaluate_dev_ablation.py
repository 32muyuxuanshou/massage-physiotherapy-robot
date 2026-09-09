"""Evaluate V1 + CameraPose DEV meshes with legacy, triangle and rendered-depth metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from surface_metrics import (camera_to_world, legacy_point_to_vertex,
                             point_to_triangle, rendered_depth, world_to_camera)


def sample(points: np.ndarray, maximum: int, seed: int) -> np.ndarray:
    if len(points) <= maximum:
        return points
    ids = np.random.default_rng(seed).choice(len(points), maximum, replace=False)
    return points[ids]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faces-npy", type=Path, required=True,
                    help="MHR topology_faces.npy exported by generate_mhr_native_synthetic.py")
    ap.add_argument("--prepared-dir", type=Path, required=True)
    ap.add_argument("--predictions-dir", type=Path, required=True)
    ap.add_argument("--v1-results-dir", type=Path, required=True)
    ap.add_argument("--camera-pose-results-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--maximum-points", type=int, default=25000)
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()
    faces = np.load(args.faces_npy).astype(np.int64)
    if faces.shape != (36874, 3):
        raise ValueError(f"unexpected MHR topology: {faces.shape}")

    observations = sorted(args.prepared_dir.glob("*.npz"))
    if len(observations) != 5:
        raise RuntimeError(f"DEV contract requires exactly 5 observations, found {len(observations)}")
    rows = []
    for obs_index, observation_path in enumerate(observations):
        obs = np.load(observation_path)
        observed_b = sample(obs["points_b"].astype(np.float64), args.maximum_points,
                            args.seed + obs_index)
        for model_tag in ("official", "v2_e5"):
            pred_path = args.predictions_dir / f"{observation_path.stem}__{model_tag}.npz"
            pred = np.load(pred_path)
            initial_a = pred["pred_vertices"].reshape(-1, 3) + pred["pred_cam_t"].reshape(1, 3)
            initial_b = world_to_camera(camera_to_world(initial_a, obs["R_a"], obs["T_a"]),
                                        obs["R_b"], obs["T_b"])
            initial_metrics = {
                "legacy": legacy_point_to_vertex(observed_b, initial_b),
                "point_to_triangle": point_to_triangle(observed_b, initial_b, faces),
                "rendered_depth": rendered_depth(observed_b, initial_b, faces, obs["K_b"],
                                                  obs["rgb_b"].shape[0], obs["rgb_b"].shape[1]),
            }
            for group in ("camera", "pose", "camera_pose", "shape_scale", "combined"):
                directory = args.camera_pose_results_dir if group == "camera_pose" else args.v1_results_dir
                stem = f"{observation_path.stem}__{model_tag}__{group}"
                result_path, mesh_path = directory / f"{stem}.json", directory / f"{stem}.npz"
                if not result_path.is_file() or not mesh_path.is_file():
                    raise FileNotFoundError(f"missing DEV result pair: {stem}")
                prior = json.loads(result_path.read_text(encoding="utf-8"))
                mesh = np.load(mesh_path)
                refined_b = mesh["vertices_camera_b"].astype(np.float64)
                refined_metrics = {
                    "legacy": legacy_point_to_vertex(observed_b, refined_b),
                    "point_to_triangle": point_to_triangle(observed_b, refined_b, faces),
                    "rendered_depth": rendered_depth(observed_b, refined_b, faces, obs["K_b"],
                                                      obs["rgb_b"].shape[0], obs["rgb_b"].shape[1]),
                }
                rows.append({
                    "split": "DEV5_ONLY", "observation_id": observation_path.stem,
                    "subject_id": observation_path.stem.split("_a", 1)[0],
                    "model_tag": model_tag, "parameter_group": group,
                    "initial": initial_metrics, "refined": refined_metrics,
                    "parameter_sanity": prior["parameter_sanity"],
                    "source": {"observation": str(observation_path),
                               "prediction": str(pred_path), "fit_result": str(result_path)},
                })
                print("DONE", stem, flush=True)
    output = {
        "status": "COMPLETED_DEV5_METRIC_ABLATION", "sealed_test_accessed": False,
        "unit_contract": "geometry metres; reported distances millimetres; OpenCV camera +Z",
        "sampling": {"maximum_observed_points_per_subject": args.maximum_points,
                     "seed": args.seed, "aggregation_unit": "subject"},
        "metric_contract": {
            "legacy": "one-sided observed point to nearest MHR vertex; V1 comparability only",
            "point_to_triangle": "exact one-sided observed point to continuous MHR triangle surface",
            "rendered_depth": "absolute Z residual at held-out observed pixels where MHR rasterization overlaps",
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
