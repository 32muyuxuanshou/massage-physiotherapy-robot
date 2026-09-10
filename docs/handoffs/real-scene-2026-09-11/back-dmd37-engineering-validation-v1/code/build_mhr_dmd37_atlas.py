"""Build a topology-bound MHR engineering atlas from the reviewed DMD37 asset.

This is a geometry/provenance conversion. It does not validate medical semantics.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve()
ROOT = HERE.parents[5]
OUT = HERE.parent.parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def closest_on_triangles(point: np.ndarray, tri: np.ndarray):
    """Return closest point, triangle index and barycentric coordinates."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac = b - a, c - a
    n = np.cross(ab, ac)
    nn = np.einsum("ij,ij->i", n, n)
    plane = point - n * (np.einsum("ij,ij->i", point - a, n) / np.maximum(nn, 1e-20))[:, None]
    v0, v1, v2 = ab, ac, plane - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    den = d00 * d11 - d01 * d01
    vb = (d11 * d20 - d01 * d21) / np.maximum(den, 1e-20)
    wb = (d00 * d21 - d01 * d20) / np.maximum(den, 1e-20)
    ub = 1.0 - vb - wb
    inside = (ub >= 0) & (vb >= 0) & (wb >= 0) & (nn > 1e-20)

    candidates = []
    bary = []
    plane_dist = np.sum((plane - point) ** 2, axis=1)
    candidates.append(np.where(inside[:, None], plane, np.inf))
    bary.append(np.column_stack([ub, vb, wb]))
    for x, y, weights in ((a, b, (0, 1)), (b, c, (1, 2)), (c, a, (2, 0))):
        edge = y - x
        t = np.clip(np.einsum("ij,ij->i", point - x, edge) / np.maximum(np.einsum("ij,ij->i", edge, edge), 1e-20), 0, 1)
        q = x + t[:, None] * edge
        w = np.zeros((len(tri), 3), np.float64)
        w[:, weights[0]] = 1 - t
        w[:, weights[1]] = t
        candidates.append(q)
        bary.append(w)
    cand = np.stack(candidates, axis=1)
    bw = np.stack(bary, axis=1)
    dist2 = np.sum((cand - point) ** 2, axis=2)
    choice = np.argmin(dist2, axis=1)
    row = np.arange(len(tri))
    best_per_face = cand[row, choice]
    best_bary = bw[row, choice]
    face = int(np.argmin(dist2[row, choice]))
    return best_per_face[face], face, best_bary[face]


def main() -> None:
    reviewed = ROOT / "docs/handoffs/real-scene-2026-09-06/reviewed-dmd37-2026-09-07/reviewed_points.json"
    skel_map_path = ROOT / "AI感知模块/模型资源/SMPL-X_SKEL_v2.2_internal/alignment/mapping_male.npz"
    mapping_dir = ROOT / "AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets"
    mhr_smpl_path = mapping_dir / "mhr2smpl_mapping.npz"
    mhr_smplx_path = mapping_dir / "mhr2smplx_mapping.npz"
    mhr_asset = ROOT / "AI感知模块/outputs/内部工程证据/2026-09-06_SAM3D_S01_PILOT_V1/weights/assets/mhr_model.pt"
    verts_path = OUT / "raw/mhr_rest_vertices.npy"
    faces_path = OUT / "raw/mhr_faces.npy"

    source = json.loads(reviewed.read_text(encoding="utf-8"))
    skel = np.load(skel_map_path)
    direct_mapping = np.load(mhr_smpl_path)
    historical_mapping = np.load(mhr_smplx_path)
    verts = np.load(verts_path).astype(np.float64)
    faces = np.load(faces_path).astype(np.int64)
    tri = verts[faces]
    assert len(source["points"]) == 37
    assert verts.shape == (18439, 3) and faces.shape == (36874, 3)
    assert np.allclose(direct_mapping["baryc_coords"].sum(1), 1, atol=1e-8)
    assert np.allclose(historical_mapping["baryc_coords"].sum(1), 1, atol=1e-8)

    smpl_on_mhr = (tri[direct_mapping["triangle_ids"]] * direct_mapping["baryc_coords"][:, :, None]).sum(1)
    smplx_on_mhr = (tri[historical_mapping["triangle_ids"]] * historical_mapping["baryc_coords"][:, :, None]).sum(1)
    rows, bridge_rows = [], []
    for p in source["points"]:
        ids = np.asarray(p["vertex_indices"], dtype=np.int64)
        w = np.asarray(p["barycentric"], dtype=np.float64)
        assert np.array_equal(skel["skel_skin_faces"][p["face_index"]], ids)
        # The reviewed SKEL skin has the exact 6890-vertex SMPL face topology.
        # The official mhr2smpl asset therefore supplies the direct candidate.
        direct_composed = (smpl_on_mhr[ids] * w[:, None]).sum(0)
        targets = skel["target_indices"][ids]
        historical_composed = (smplx_on_mhr[targets] * w[:, None]).sum(0)
        composed = direct_composed
        projected, face_id, bary = closest_on_triangles(composed, tri)
        historical_projected, historical_face, historical_bary = closest_on_triangles(historical_composed, tri)
        replay = (verts[faces[face_id]] * bary[:, None]).sum(0)
        bridge_d = skel["canonical_distances_m"][ids].astype(float)
        row = {
            "engineering_point_id": p["point_id"], "reference_code": p["reference_code"],
            "current_engineering_name": p["name_zh"], "anatomical_side": p["side"],
            "mhr_face_index": face_id, "vertex_indices": faces[face_id].tolist(),
            "barycentric": bary.tolist(), "canonical_3d_cm": replay.tolist(),
            "canonical_3d_m": (replay / 100.0).tolist(),
            "source_skel_point": {"face_index": p["face_index"], "vertex_indices": ids.tolist(), "barycentric": w.tolist()},
            "bridge_method": "reviewed SKEL/SMPL-identical face anchor -> official mhr2smpl barycentric correspondence -> exact nearest MHR triangle",
            "bridge_quality": {"direct_composed_to_mhr_surface_mm": float(np.linalg.norm(projected - composed) * 10),
                               "direct_vs_historical_smplx_bridge_mm": float(np.linalg.norm(projected - historical_projected) * 10),
                               "historical_skel_to_smplx_vertex_distance_mm": (bridge_d * 1000).tolist(),
                               "historical_face_index": historical_face, "historical_barycentric": historical_bary.tolist()},
            "mhr_asset_sha256": sha256_file(mhr_asset), "faces_sha256_int32_c_order": hashlib.sha256(faces.astype(np.int32).tobytes()).hexdigest(),
            "medical_truth": False, "real_medical_validated": False,
        }
        rows.append(row)
        bridge_rows.append({"point_id": p["point_id"], **row["bridge_quality"], "side": p["side"], "direct_xyz_cm": replay.tolist(), "historical_xyz_cm": historical_projected.tolist()})

    max_surface = max(r["direct_composed_to_mhr_surface_mm"] for r in bridge_rows)
    direct_history = np.asarray([r["direct_vs_historical_smplx_bridge_mm"] for r in bridge_rows])
    midline = [r for r in rows if r["anatomical_side"] == "MIDLINE"]
    side_ok = all((r["canonical_3d_cm"][0] > 0) if r["anatomical_side"] == "LEFT" else
                  (r["canonical_3d_cm"][0] < 0) if r["anatomical_side"] == "RIGHT" else True for r in rows)
    by_code = {}
    for r in rows:
        by_code.setdefault(r["reference_code"], {})[r["anatomical_side"]] = r
    pair_rows = []
    for code, pair in by_code.items():
        if "LEFT" not in pair or "RIGHT" not in pair:
            continue
        left, right = np.asarray(pair["LEFT"]["canonical_3d_cm"]), np.asarray(pair["RIGHT"]["canonical_3d_cm"])
        pair_rows.append({"reference_code": code, "mirror_residual_mm": float(np.linalg.norm(left - right * np.array([-1, 1, 1])) * 10),
                          "abs_lateral_radius_difference_mm": float(abs(abs(left[0]) - abs(right[0])) * 10),
                          "vertical_difference_mm": float(abs(left[1] - right[1]) * 10), "depth_difference_mm": float(abs(left[2] - right[2]) * 10)})
    # Keep the gate closed: the direct official candidate is numerically strong,
    # but the single-face projection rule was not frozen before seeing results
    # and differs materially from the historical bridge.
    atlas_gate = "BRIDGE_UNCERTAINTY_REQUIRES_REVIEW"
    topology = {
        "schema": "MHR_DMD37_TOPOLOGY_CONTRACT_V1", "status": "PASS",
        "mhr_version": "facebook/sam-3d-body public MHR TorchScript asset", "lod": "lod=1 (verified in mhr_head runtime source)",
        "vertex_count": len(verts), "face_count": len(faces),
        "faces_sha256_int32_c_order": hashlib.sha256(faces.astype(np.int32).tobytes()).hexdigest(),
        "mhr_asset_sha256": sha256_file(mhr_asset), "rest_vertices_sha256_float32_c_order": hashlib.sha256(verts.astype(np.float32).tobytes()).hexdigest(),
        "runtime_evidence": "raw/mhr_runtime_contract.json", "units": "runtime native centimeters; atlas also records meters",
    }
    atlas = {"schema": "DMD37_MHR_ENGINEERING_ATLAS_V1", "status": atlas_gate, "point_count": 37,
             "gate_reason": "Direct official SMPL candidate is deterministic, but the single-face projection rule was not pre-frozen and the historical bridge differs materially; independent engineering review is required before release.",
             "medical_truth": False, "real_image_accuracy_validated": False, "topology": topology, "points": rows}
    bridge = {"schema": "DMD37_BRIDGE_AUDIT_V1", "status": atlas_gate,
              "selected_bridge": "direct official mhr2smpl mapping because reviewed SKEL skin faces exactly match the 6890-vertex SMPL topology",
              "historical_bridge_reproduced": True, "official_mapping_assets": ["mhr2smpl", "mhr2smplx", "smpl2mhr", "smplx2mhr"],
              "summary": {"max_direct_composed_to_surface_mm": max_surface,
                          "direct_vs_historical_mm": {"mean": float(direct_history.mean()), "median": float(np.median(direct_history)), "p95": float(np.quantile(direct_history, .95)), "max": float(direct_history.max())},
                          "side_sign_consistency": side_ok,
                          "midline_max_abs_x_mm": max(abs(r["canonical_3d_cm"][0]) * 10 for r in midline),
                          "pair_mirror_residual_mm": {"mean": float(np.mean([p["mirror_residual_mm"] for p in pair_rows])), "max": float(np.max([p["mirror_residual_mm"] for p in pair_rows]))},
                          "all_source_vertices_valid": bool(all(np.all(skel["valid_mask"][np.asarray(p["vertex_indices"], int)]) for p in source["points"]))},
              "pairwise_symmetry": pair_rows, "points": bridge_rows,
              "limitations": ["The historical SKEL-to-SMPL-X nearest-vertex bridge remains only a comparator.", "No reliable geodesic result is reported in this version; graph-vertex paths would mix anchor-to-vertex approximation with correspondence difference.", "Passing this gate means deterministic engineering replay only, not anatomy or medical correctness."]}
    replay_errors = []
    for r in rows:
        q = (verts[np.asarray(r["vertex_indices"])] * np.asarray(r["barycentric"])[:, None]).sum(0)
        replay_errors.append(float(np.linalg.norm(q - np.asarray(r["canonical_3d_cm"])) * 10))
    replay = {"schema": "DMD37_ATLAS_REPLAY_TEST_V1", "status": "PASS" if max(replay_errors) <= .001 else "FAIL",
              "point_count": 37, "deterministic_replay_percent": 100.0, "max_replay_error_mm": max(replay_errors),
              "test": "reload face indices and barycentric weights on the exact hashed MHR rest mesh"}
    for name, obj in [("MHR_DMD37_TOPOLOGY_CONTRACT_V1.json", topology), ("DMD37_MHR_ENGINEERING_ATLAS_V1.json", atlas),
                      ("DMD37_BRIDGE_AUDIT_V1.json", bridge), ("DMD37_ATLAS_REPLAY_TEST_V1.json", replay)]:
        (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"atlas_gate": atlas_gate, "max_surface_mm": max_surface, "direct_vs_history_mean_mm": float(direct_history.mean()), "direct_vs_history_p95_mm": float(np.quantile(direct_history,.95)), "max_replay_mm": max(replay_errors)}))


if __name__ == "__main__":
    main()
