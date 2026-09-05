"""Select engineering-only dorsal/ventral anchors once, then freeze their topology bindings.

This is fixture construction, not an acceptance test and not medical annotation.
Downstream verification reads only the resulting fixed face/vertex/barycentric records.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TARGET_NAME = "SKEL-skin-female"
TOPOLOGY_SHA256 = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
TARGETS = (
    ("ENG_BACK_C7", "DORSAL", (0.00, 0.33, -0.09)),
    ("ENG_BACK_SCAPULA_L", "DORSAL", (-0.16, 0.22, -0.08)),
    ("ENG_BACK_SCAPULA_R", "DORSAL", (0.16, 0.22, -0.08)),
    ("ENG_BACK_THORACIC_L", "DORSAL", (-0.11, 0.08, -0.08)),
    ("ENG_BACK_THORACIC_R", "DORSAL", (0.11, 0.08, -0.08)),
    ("ENG_BACK_LUMBAR", "DORSAL", (0.00, -0.08, -0.07)),
    ("ENG_FRONT_CHEST", "VENTRAL", (0.00, 0.24, 0.12)),
    ("ENG_FRONT_ABDOMEN", "VENTRAL", (0.00, 0.00, 0.12)),
)


def _topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def _select(mesh, target_xyz: tuple[float, float, float], surface: str, used: set[int]):
    target = Vector(target_xyz)
    best = None
    for polygon in mesh.polygons:
        if polygon.index in used or len(polygon.vertices) != 3:
            continue
        normal_z = float(polygon.normal.z)
        if surface == "DORSAL" and normal_z > -0.45:
            continue
        if surface == "VENTRAL" and normal_z < 0.45:
            continue
        center = polygon.center
        # Torso vertical/left-right position dominates; depth only breaks close ties.
        delta = center - target
        score = float(delta.x * delta.x + delta.y * delta.y + 0.25 * delta.z * delta.z)
        if best is None or score < best[0]:
            best = (score, polygon)
    if best is None:
        raise RuntimeError(f"No face candidate for {surface} at {target_xyz}")
    return best


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 1:
        raise ValueError("expected output fixture path")
    output = Path(argv[0])
    target = bpy.data.objects.get(TARGET_NAME)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing {TARGET_NAME}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        topology = _topology_signature(mesh)
        if topology != TOPOLOGY_SHA256:
            raise RuntimeError(f"topology mismatch: {topology}")
        used: set[int] = set()
        anchors = []
        for point_id, surface, target_xyz in TARGETS:
            score, polygon = _select(mesh, target_xyz, surface, used)
            used.add(int(polygon.index))
            anchors.append(
                {
                    "point_id": point_id,
                    "code": point_id,
                    "name_zh": "工程锚点（非医学穴位）",
                    "side": "MIDLINE" if point_id.endswith(("C7", "LUMBAR", "CHEST", "ABDOMEN")) else ("LEFT" if point_id.endswith("_L") else "RIGHT"),
                    "body_region": "TORSO",
                    "surface": surface,
                    "face_index": int(polygon.index),
                    "vertex_indices": [int(value) for value in polygon.vertices],
                    "barycentric": [1.0 / 3.0] * 3,
                    "fixture_local_center_m": [float(value) for value in polygon.center],
                    "fixture_local_normal": [float(value) for value in polygon.normal],
                    "construction_target_local_m": list(target_xyz),
                    "construction_score": math.sqrt(score),
                }
            )
    finally:
        evaluated.to_mesh_clear()
    payload = {
        "schema": "skel-prone-engineering-fixture-v1",
        "medical_truth": False,
        "notice": "Engineering anchors only; never interpret as acupoints.",
        "model": {
            "family": "SKEL",
            "gender": "female",
            "object_name": TARGET_NAME,
            "vertex_count": 6890,
            "polygon_count": 13776,
            "topology_signature_sha256": TOPOLOGY_SHA256,
        },
        "construction_method": "one-time nearest triangular face-center search with explicit dorsal/ventral normal constraint",
        "acceptance_must_not_reselect": True,
        "anchors": anchors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_FREEZE_PRONE_FIXTURE=PASS")


if __name__ == "__main__":
    main()
