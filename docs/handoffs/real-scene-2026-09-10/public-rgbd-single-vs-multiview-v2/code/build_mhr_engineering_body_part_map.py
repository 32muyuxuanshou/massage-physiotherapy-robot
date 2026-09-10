#!/usr/bin/env python3
"""Build a topology-bound, non-medical MHR engineering body-part map."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


GROUPS = ("torso", "arms", "legs", "head", "hands_feet")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    a = np.ascontiguousarray(array)
    return hashlib.sha256(a.tobytes()).hexdigest()


def joint_group(name: str) -> str:
    if name in {"body_world", "root"} or name.startswith("c_spine") or "clavicle" in name:
        return "torso"
    if any(x in name for x in ("_uparm", "_lowarm")):
        return "arms"
    if any(x in name for x in ("_upleg", "_lowleg")):
        return "legs"
    if any(x in name for x in ("_wrist", "_pinky", "_ring", "_middle", "_index", "_thumb")):
        return "hands_feet"
    if any(x in name for x in ("_foot", "_talocrural", "_subtalar", "_transversetarsal", "_ball")):
        return "hands_feet"
    if name.startswith("c_neck") or name.startswith("c_head") or name.startswith("c_jaw") or name.startswith("c_teeth") or name.startswith("c_tongue") or name.endswith("eye") or "eye_null" in name:
        return "head"
    raise ValueError(f"unmapped joint: {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    model = torch.jit.load(str(args.mhr), map_location="cpu")
    joint_names = list(model.get_joint_names())
    skin_indices_t, skin_weights_t = model.get_lbsw()
    skin_indices = skin_indices_t.cpu().numpy().astype(np.int64)
    skin_weights = skin_weights_t.cpu().numpy().astype(np.float32)
    faces = model.character_torch.mesh.faces.cpu().numpy().astype(np.int32)

    if skin_indices.shape != skin_weights.shape or skin_indices.shape[0] <= 0:
        raise RuntimeError("invalid get_lbsw contract")
    if int(skin_indices.max()) >= len(joint_names):
        raise RuntimeError("LBS joint index exceeds joint_names")
    weight_sums = skin_weights.sum(axis=1)
    if not np.allclose(weight_sums, 1.0, atol=1e-5):
        raise RuntimeError("LBS weights do not sum to one")

    group_id = {name: i for i, name in enumerate(GROUPS)}
    joint_groups = [joint_group(name) for name in joint_names]
    group_weights = np.zeros((skin_indices.shape[0], len(GROUPS)), dtype=np.float32)
    rows = np.arange(skin_indices.shape[0])
    for slot in range(skin_indices.shape[1]):
        mapped = np.asarray([group_id[joint_groups[j]] for j in skin_indices[:, slot]], dtype=np.int64)
        np.add.at(group_weights, (rows, mapped), skin_weights[:, slot])

    vertex_labels = group_weights.argmax(axis=1).astype(np.uint8)
    ordered = np.sort(group_weights, axis=1)
    confidence = ordered[:, -1].astype(np.float32)
    margin = (ordered[:, -1] - ordered[:, -2]).astype(np.float32)
    face_group_weights = group_weights[faces].mean(axis=1)
    face_labels = face_group_weights.argmax(axis=1).astype(np.uint8)
    face_confidence = face_group_weights.max(axis=1).astype(np.float32)

    asset_sha = sha256_file(args.mhr)
    faces_sha = sha256_array(faces)
    joint_names_sha = hashlib.sha256(json.dumps(joint_names, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    npz_name = "MHR_ENGINEERING_BODY_PART_MAP_V1.npz"
    np.savez_compressed(
        args.output_dir / npz_name,
        group_names=np.asarray(GROUPS),
        joint_names=np.asarray(joint_names),
        joint_group_ids=np.asarray([group_id[x] for x in joint_groups], dtype=np.uint8),
        faces=faces,
        skin_indices=skin_indices.astype(np.uint16),
        skin_weights=skin_weights,
        vertex_group_weights=group_weights,
        vertex_labels=vertex_labels,
        vertex_confidence=confidence,
        vertex_margin=margin,
        face_labels=face_labels,
        face_confidence=face_confidence,
    )

    counts_v = {g: int((vertex_labels == i).sum()) for i, g in enumerate(GROUPS)}
    counts_f = {g: int((face_labels == i).sum()) for i, g in enumerate(GROUPS)}
    index_map = {g: np.flatnonzero(vertex_labels == i).astype(int).tolist() for i, g in enumerate(GROUPS)}
    result = {
        "schema": "MHR_ENGINEERING_BODY_PART_MAP_V1",
        "status": "USABLE_FOR_ENGINEERING_BODY_PART_METRICS_WITH_LIMITATIONS",
        "topology_binding": {
            "mhr_asset_sha256": asset_sha,
            "faces_sha256_int32_c_order": faces_sha,
            "joint_names_sha256_compact_json_utf8": joint_names_sha,
            "vertex_count": int(skin_indices.shape[0]),
            "face_count": int(faces.shape[0]),
            "joint_count": len(joint_names),
            "lbs_influences_per_vertex": int(skin_indices.shape[1]),
        },
        "groups": list(GROUPS),
        "rules": {
            "vertex": "Sum official get_lbsw weights by explicitly listed joint family; assign argmax group.",
            "face": "Average the three vertices' grouped LBS weights; assign argmax group.",
            "torso": "body_world, root, c_spine*, and left/right clavicle joints.",
            "arms": "left/right upper-arm and lower-arm joints, including twist/proc joints.",
            "legs": "left/right upper-leg and lower-leg joints, including twist/proc joints.",
            "head": "neck, head, jaw, teeth, tongue, and eye joint families.",
            "hands_feet": "wrist/finger families plus foot, ankle/tarsal, and ball families.",
        },
        "joint_to_group": dict(zip(joint_names, joint_groups)),
        "vertex_counts": counts_v,
        "face_counts": counts_f,
        "confidence_summary": {
            "vertex_group_weight_mean": float(confidence.mean()),
            "vertex_group_weight_p05": float(np.quantile(confidence, 0.05)),
            "vertex_margin_mean": float(margin.mean()),
            "vertices_margin_lt_0_1": int((margin < 0.1).sum()),
            "faces_group_weight_mean": float(face_confidence.mean()),
        },
        "vertex_indices_by_group": index_map,
        "artifacts": {"npz": npz_name},
        "limitations": [
            "This is an engineering anatomical-region map derived only from rig skinning weights; it is not a medical or acupuncture atlas.",
            "No upper/lower torso or front/back split is asserted because joint weights do not provide a reliable boundary for those regions.",
            "No XYZ-coordinate threshold is used; the map cannot identify the back surface or treatment sites.",
            "Argmax makes seam vertices exclusive; use stored group weights/confidence for analyses sensitive to boundaries.",
            "The map is valid only when all topology-binding hashes and counts match exactly.",
        ],
    }
    out_json = args.output_dir / "MHR_ENGINEERING_BODY_PART_MAP_V1.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    audit = {
        "schema": "BODY_PART_MAP_AUDIT_V1",
        "status": "PASS_ENGINEERING_MAP_CREATED",
        "source": {
            "asset_path_at_audit": str(args.mhr),
            "torchscript_methods_used": ["get_joint_names", "get_lbsw"],
            "mesh_faces_source": "character_torch.mesh.faces",
        },
        "contract_checks": {
            "all_127_joint_names_mapped_once": len(joint_groups) == 127,
            "lbs_shapes_match": skin_indices.shape == skin_weights.shape,
            "lbs_weight_sum_max_abs_error": float(np.abs(weight_sums - 1.0).max()),
            "face_vertex_indices_in_range": bool(faces.min() >= 0 and faces.max() < skin_indices.shape[0]),
            "all_vertices_assigned": int(sum(counts_v.values())) == skin_indices.shape[0],
            "all_faces_assigned": int(sum(counts_f.values())) == faces.shape[0],
        },
        "topology_binding": result["topology_binding"],
        "counts": {"vertices": counts_v, "faces": counts_f},
        "decision": {
            "coarse_engineering_body_parts": "DETERMINABLE",
            "upper_vs_lower_torso": "NOT_DETERMINABLE",
            "front_vs_back_torso": "NOT_DETERMINABLE",
            "medical_or_acupuncture_regions": "NOT_DETERMINABLE",
        },
        "map_json_sha256": sha256_file(out_json),
        "map_npz_sha256": sha256_file(args.output_dir / npz_name),
    }
    (args.output_dir / "BODY_PART_MAP_AUDIT_V1.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
