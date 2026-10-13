"""CPU evaluation of MHR predictions on the official SMPL vertex layout.

The mapping is fixed before evaluation and never reads the reference body.
Inputs to the mapper are already in one camera coordinate system, in meters.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def camera_vertices(pred_vertices_m, pred_cam_t_m):
    """SAM3D local vertices already have its camera-axis convention. Add t once."""
    return np.asarray(pred_vertices_m, dtype=np.float64) + np.asarray(
        pred_cam_t_m, dtype=np.float64
    ).reshape(1, 3)


def behave_world_to_camera(vertices_world_m, local_to_world_rotation, local_to_world_translation_m):
    """Invert the official date/sequence camera extrinsic, without fitting to GT."""
    rotation = np.asarray(local_to_world_rotation).reshape(3, 3)
    translation = np.asarray(local_to_world_translation_m).reshape(3)
    return (np.asarray(vertices_world_m) - translation) @ rotation


def map_mhr_to_smpl(vertices_camera_m, mhr_faces, mapping_path):
    """Fixed official barycentric sampling, without body fitting or GT alignment."""
    vertices = np.asarray(vertices_camera_m, dtype=np.float64)
    faces = np.asarray(mhr_faces, dtype=np.int64)
    if vertices.shape != (18439, 3) or faces.shape != (36874, 3):
        raise ValueError("The official mapping requires MHR LOD1 topology.")
    with np.load(mapping_path, allow_pickle=False) as mapping:
        triangle_ids = mapping["triangle_ids"]
        weights = mapping["baryc_coords"]
    if triangle_ids.shape != (6890,) or weights.shape != (6890, 3):
        raise ValueError("Expected the MHR-to-SMPL map, not the SMPL-X map.")
    if not np.allclose(weights.sum(axis=1), 1.0, atol=1e-12, rtol=0):
        raise ValueError("Invalid barycentric weights.")
    return np.einsum("nj,njk->nk", weights, vertices[faces[triangle_ids]])


def pve_mm(predicted_m, reference_m):
    """Mean Euclidean distance between corresponding vertices; NOT a median."""
    return float(1000.0 * np.linalg.norm(predicted_m - reference_m, axis=1).mean())


def similarity_align(predicted_m, reference_m):
    """Diagnostic proper similarity alignment: translation + rotation + scale."""
    p = predicted_m - predicted_m.mean(axis=0)
    q = reference_m - reference_m.mean(axis=0)
    u, singular_values, vt = np.linalg.svd(p.T @ q)
    signs = np.ones(3)
    signs[-1] = np.linalg.det(u @ vt)
    rotation = (u * signs) @ vt
    scale = float(np.dot(singular_values, signs) / np.square(p).sum())
    return scale * p @ rotation + reference_m.mean(axis=0), scale


def evaluate_vertices(predicted_m, reference_m, joint_regressor=None):
    predicted = np.asarray(predicted_m, dtype=np.float64)
    reference = np.asarray(reference_m, dtype=np.float64)
    if predicted.shape != reference.shape or predicted.ndim != 2 or predicted.shape[1] != 3:
        raise ValueError("Reference and prediction must have identical vertex identities.")
    if not (np.isfinite(predicted).all() and np.isfinite(reference).all()):
        raise ValueError("Non-finite vertex coordinates.")
    centered_p = predicted - predicted.mean(axis=0)
    centered_q = reference - reference.mean(axis=0)
    aligned, scale = similarity_align(predicted, reference)
    result = {
        "vertex_count": len(reference),
        "pve_absolute_mm": pve_mm(predicted, reference),
        "pve_centroid_centered_mm": pve_mm(centered_p, centered_q),
        "pa_pve_similarity_mm": pve_mm(aligned, reference),
        "diagnostic_pa_scale": scale,
        "centroid_delta_xyz_mm": (1000 * (predicted.mean(0) - reference.mean(0))).tolist(),
        "reference_kind": "fitted_body_reference_not_direct_skin_ground_truth",
        "m3_exact_protocol_equivalence": "UNCONFIRMED",
    }
    if joint_regressor is not None:
        regressor = np.asarray(joint_regressor, dtype=np.float64)
        if regressor.shape[1] != len(reference):
            raise ValueError("Joint regressor topology differs from the evaluated vertices.")
        pred_joints, ref_joints = regressor @ predicted, regressor @ reference
        result.update(
            joint_count=len(regressor),
            mpjpe_regressor_joints_absolute_mm=pve_mm(pred_joints, ref_joints),
            pve_pelvis_centered_mm=pve_mm(predicted - pred_joints[0], reference - ref_joints[0]),
            mpjpe_regressor_joints_pelvis_centered_mm=pve_mm(
                pred_joints - pred_joints[0], ref_joints - ref_joints[0]
            ),
        )
    return result


def load_vertices(path, key):
    path = Path(path)
    if path.suffix.lower() == ".ply":
        import trimesh

        return np.asarray(trimesh.load(path, process=False).vertices, dtype=np.float64)
    if path.suffix.lower() == ".npy":
        return np.load(path, allow_pickle=False)
    with np.load(path, allow_pickle=False) as data:
        return data[key]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--prediction-key", default="vertices_camera_m")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-key", default="vertices_camera_m")
    parser.add_argument("--reference-space", choices=["camera", "behave-world"], required=True)
    parser.add_argument("--local-to-world-config", type=Path,
                        help="BEHAVE calibs/DateXX/config/<camera_id>/config.json")
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--mhr-faces", type=Path, required=True)
    parser.add_argument("--joint-regressor", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    predicted = load_vertices(args.prediction, args.prediction_key)
    reference = load_vertices(args.reference, args.reference_key)
    if reference.shape != (6890, 3):
        raise ValueError("Expected a 6890-vertex SMPL/SMPL-H fitted reference in camera meters.")
    if args.reference_space == "behave-world":
        if args.local_to_world_config is None:
            parser.error("A BEHAVE world-space reference requires the sequence's camera config.")
        calibration = json.loads(args.local_to_world_config.read_text(encoding="utf-8"))
        reference = behave_world_to_camera(reference, calibration["rotation"], calibration["translation"])
    mapped = map_mhr_to_smpl(predicted, np.load(args.mhr_faces), args.mapping)
    regressor = np.load(args.joint_regressor) if args.joint_regressor else None
    result = evaluate_vertices(mapped, reference, regressor)
    result["conversion"] = "fixed_official_barycentric_map_no_parameter_fitting"
    result["reference_source_space"] = args.reference_space
    result["inputs"] = {
        name: {"path": str(path.resolve()), "sha256": sha256(path)}
        for name, path in {
            "prediction": args.prediction,
            "reference": args.reference,
            "mapping": args.mapping,
            "mhr_faces": args.mhr_faces,
            **({"reference_camera_config": args.local_to_world_config} if args.local_to_world_config else {}),
            **({"joint_regressor": args.joint_regressor} if args.joint_regressor else {}),
        }.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    np.save(args.output.with_suffix(".mapped_smpl_vertices_m.npy"), mapped)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
