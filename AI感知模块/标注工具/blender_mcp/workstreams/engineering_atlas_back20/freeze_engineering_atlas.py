"""Construct ENG_BACK_20_V1 once on canonical SKEL; never use this as an acceptance test."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


TARGET_NAME = "SKEL-skin-female"
TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
TARGETS = (
    ("E01", "neck_base_midline", "MIDLINE", 0.00, 0.34),
    ("E02", "upper_thoracic_midline", "MIDLINE", 0.00, 0.27),
    ("E03", "middle_thoracic_midline", "MIDLINE", 0.00, 0.15),
    ("E04", "lower_thoracic_midline", "MIDLINE", 0.00, 0.05),
    ("E05", "upper_lumbar_midline", "MIDLINE", 0.00, -0.07),
    ("E06", "lumbosacral_midline", "MIDLINE", 0.00, -0.18),
    ("E07", "posterior_shoulder", "SUBJECT_LEFT", 0.18, 0.27),
    ("E08", "posterior_shoulder", "SUBJECT_RIGHT", -0.18, 0.27),
    ("E09", "upper_scapular", "SUBJECT_LEFT", 0.14, 0.22),
    ("E10", "upper_scapular", "SUBJECT_RIGHT", -0.14, 0.22),
    ("E11", "medial_scapular", "SUBJECT_LEFT", 0.08, 0.16),
    ("E12", "medial_scapular", "SUBJECT_RIGHT", -0.08, 0.16),
    ("E13", "lower_scapular", "SUBJECT_LEFT", 0.12, 0.08),
    ("E14", "lower_scapular", "SUBJECT_RIGHT", -0.12, 0.08),
    ("E15", "lower_thoracic_paraspinal", "SUBJECT_LEFT", 0.13, 0.00),
    ("E16", "lower_thoracic_paraspinal", "SUBJECT_RIGHT", -0.13, 0.00),
    ("E17", "lumbar_paraspinal", "SUBJECT_LEFT", 0.11, -0.10),
    ("E18", "lumbar_paraspinal", "SUBJECT_RIGHT", -0.11, -0.10),
    ("E19", "lower_lumbar_lateral", "SUBJECT_LEFT", 0.16, -0.18),
    ("E20", "lower_lumbar_lateral", "SUBJECT_RIGHT", -0.16, -0.18),
)


def topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def select_face(mesh, x: float, y: float, used: set[int]):
    target = Vector((x, y, -0.08))
    best = None
    for polygon in mesh.polygons:
        if polygon.index in used or len(polygon.vertices) != 3 or float(polygon.normal.z) > -0.45:
            continue
        delta = polygon.center - target
        score = float(delta.x * delta.x + delta.y * delta.y + 0.20 * delta.z * delta.z)
        if best is None or score < best[0]:
            best = (score, polygon)
    if best is None:
        raise RuntimeError(f"no dorsal face for {(x, y)}")
    return best


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 1:
        raise ValueError("expected output atlas path")
    output = Path(argv[0])
    target = bpy.data.objects.get(TARGET_NAME)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing {TARGET_NAME}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        if topology_signature(mesh) != TOPOLOGY:
            raise RuntimeError("canonical topology mismatch")
        used = set()
        anchors = []
        for code, region, side, x, y in TARGETS:
            score, polygon = select_face(mesh, x, y, used)
            used.add(int(polygon.index))
            anchors.append({
                "point_id": code,
                "code": code,
                "name_zh": "工程试验点（非医学穴位）",
                "region": region,
                "side": side,
                "body_region": "BACK",
                "surface": "DORSAL",
                "medical_annotation": False,
                "face_index": int(polygon.index),
                "vertex_indices": [int(value) for value in polygon.vertices],
                "barycentric": [1.0 / 3.0] * 3,
                "xyz_local_m": [float(value) for value in polygon.center],
                "normal_local": [float(value) for value in polygon.normal],
                "construction_target_local_xy_m": [x, y],
                "construction_distance_m": math.sqrt(score),
            })
    finally:
        evaluated.to_mesh_clear()
    payload = {
        "schema": "skel-engineering-atlas-v1",
        "atlas_id": "ENG_BACK_20_V1",
        "atlas_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "medical_truth": False,
        "medical_annotation": False,
        "notice": "Engineering trial targets only; never interpret as acupoints.",
        "laterality_convention": "SUBJECT_LEFT/SUBJECT_RIGHT refer to the modeled subject, never image left/right. Canonical SKEL object-local +X is subject-left and -X is subject-right, confirmed from official kin_skel.py joint order/coordinates.",
        "unit": "m",
        "coordinate_system": "canonical SKEL object-local coordinates; Blender world uses the template object matrix",
        "model": {"family": "SKEL", "gender": "female", "template_id": "SKEL_FEMALE_TRUNK_LIMB_v2.3", "object_name": TARGET_NAME, "vertex_count": 6890, "polygon_count": 13776, "topology_signature_sha256": TOPOLOGY},
        "construction_method": "one-time nearest triangular face-center selection from 20 predeclared dorsal target regions; downstream acceptance must not reselect",
        "acceptance_must_not_reselect": True,
        "anchors": anchors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_FREEZE_ENG_BACK20=PASS")


if __name__ == "__main__":
    main()
