"""Small analytic and existing-asset checks; no model inference or benchmark run."""

import argparse
import json
from pathlib import Path

import numpy as np

from metrics import behave_world_to_camera, camera_vertices, evaluate_vertices, map_mhr_to_smpl, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--faces", type=Path, required=True)
    parser.add_argument("--raw-rest-cm", type=Path, required=True)
    parser.add_argument("--cached-vertices-m", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    faces = np.load(args.faces)
    # Native MHR cm -> meters and SAM3D's Y/Z flip. No flip for cached SAM3D meshes.
    rest = np.load(args.raw_rest_cm).astype(np.float64) * 0.01 * [1, -1, -1]
    cached = np.load(args.cached_vertices_m).astype(np.float64)
    rest_smpl = map_mhr_to_smpl(rest, faces, args.mapping)
    cached_smpl = map_mhr_to_smpl(cached, faces, args.mapping)
    checks = {}
    same = evaluate_vertices(rest_smpl, rest_smpl)
    assert same["pve_absolute_mm"] < 1e-8
    checks["same_mesh_zero_error"] = same
    delta = np.array([0.0, 0.0, 0.1])
    shifted = evaluate_vertices(rest_smpl + delta, rest_smpl)
    assert abs(shifted["pve_absolute_mm"] - 100) < 1e-8
    assert shifted["pve_centroid_centered_mm"] < 1e-8
    checks["100mm_depth_translation"] = shifted
    mapped_shift = map_mhr_to_smpl(rest + delta, faces, args.mapping)
    error = float(np.abs(mapped_shift - rest_smpl - delta).max())
    assert error < 1e-12
    checks["mapping_preserves_translation_max_abs_m"] = error
    theta = 0.4
    rotation = np.array([[np.cos(theta), -np.sin(theta), 0],
                         [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
    transformed = 1.12 * rest_smpl @ rotation + [0.03, -0.02, 0.1]
    pa = evaluate_vertices(transformed, rest_smpl)
    assert pa["pve_absolute_mm"] > 50
    assert pa["pve_centroid_centered_mm"] > 10
    assert pa["pa_pve_similarity_mm"] < 1e-8
    checks["pa_removes_rotation_scale_translation_not_absolute_accuracy"] = pa
    # A known local error must remain detectable after centering and PA.
    perturbed = rest_smpl.copy()
    perturbed[:1000, 0] += 0.05
    shape = evaluate_vertices(perturbed, rest_smpl)
    assert shape["pve_centroid_centered_mm"] > 1
    assert shape["pa_pve_similarity_mm"] > 1
    checks["local_geometry_error_remains"] = shape
    translation = np.array([0.3, 0.2, -0.1])
    world = rest_smpl @ rotation.T + translation
    recovered = behave_world_to_camera(world, rotation, translation)
    error = float(np.abs(recovered - rest_smpl).max())
    assert error < 1e-12
    checks["calibration_inverse_max_abs_m"] = error
    checks["cached_real_prediction_mapping"] = {
        "source_vertices": list(cached.shape),
        "mapped_vertices": list(cached_smpl.shape),
        "finite": bool(np.isfinite(cached_smpl).all()),
        "source_bbox_extent_m": np.ptp(cached, axis=0).tolist(),
        "mapped_bbox_extent_m": np.ptp(cached_smpl, axis=0).tolist(),
    }
    assert cached_smpl.shape == (6890, 3) and np.isfinite(cached_smpl).all()
    assert np.array_equal(camera_vertices(cached, delta), cached + delta)
    inputs = {name: {"path": str(path.resolve()), "sha256": sha256(path)}
              for name, path in vars(args).items() if name != "output"}
    result = {"status": "PASS_CPU_METRIC_AND_MAPPING_QA", "checks": checks,
              "inputs": inputs, "scientific_benchmark_executed": False,
              "semantic_correspondence_accuracy_validated": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    np.save(args.output.parent / "canonical_camera_vertices_m.npy", rest)
    np.save(args.output.parent / "canonical_mapped_smpl_vertices_m.npy", rest_smpl)
    np.save(args.output.parent / "cached_prediction_mapped_smpl_vertices_m.npy", cached_smpl)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
