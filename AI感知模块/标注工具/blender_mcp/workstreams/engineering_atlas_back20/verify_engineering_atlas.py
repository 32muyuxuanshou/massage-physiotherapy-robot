"""Independently verify a frozen ENG_BACK_20 atlas against canonical SKEL."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TARGET_NAME = "SKEL-skin-female"
TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"


def topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 2:
        raise ValueError("expected atlas and report paths")
    atlas_path, report_path = map(Path, argv)
    atlas = json.loads(atlas_path.read_text(encoding="utf-8-sig"))
    target = bpy.data.objects.get(TARGET_NAME)
    if target is None:
        raise RuntimeError("canonical target missing")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    checks = []
    details = []
    try:
        anchors = atlas.get("anchors", [])
        codes = [item.get("code") for item in anchors]
        checks.append({"id": "identity_and_count", "passed": atlas.get("atlas_id") == "ENG_BACK_20_V1" and atlas.get("medical_truth") is False and atlas.get("medical_annotation") is False and codes == [f"E{i:02d}" for i in range(1, 21)]})
        checks.append({"id": "unique_codes_faces", "passed": len(set(codes)) == 20 and len({int(item["face_index"]) for item in anchors}) == 20})
        checks.append({"id": "topology", "passed": len(mesh.vertices) == 6890 and len(mesh.polygons) == 13776 and topology_signature(mesh) == TOPOLOGY and atlas["model"]["topology_signature_sha256"] == TOPOLOGY})
        all_binding = all_bary = all_position = all_dorsal = all_side = True
        max_sum_error = max_xyz_error = 0.0
        for item in anchors:
            polygon = mesh.polygons[int(item["face_index"])]
            vertices = [int(value) for value in polygon.vertices]
            weights = [float(value) for value in item["barycentric"]]
            point = sum((mesh.vertices[index].co * weight for index, weight in zip(vertices, weights)), Vector((0.0, 0.0, 0.0)))
            stored = Vector(item["xyz_local_m"])
            sum_error = abs(sum(weights) - 1.0)
            xyz_error = (point - stored).length
            max_sum_error = max(max_sum_error, sum_error)
            max_xyz_error = max(max_xyz_error, xyz_error)
            all_binding = all_binding and vertices == [int(value) for value in item["vertex_indices"]]
            all_bary = all_bary and sum_error <= 1e-12 and min(weights) >= 0.10
            all_position = all_position and xyz_error <= 1e-7
            all_dorsal = all_dorsal and float(polygon.normal.z) <= -0.45
            side = item["side"]
            all_side = all_side and ((side == "MIDLINE" and abs(float(point.x)) <= 0.035) or (side == "SUBJECT_LEFT" and float(point.x) > 0.0) or (side == "SUBJECT_RIGHT" and float(point.x) < 0.0))
            details.append({"code": item["code"], "face_index": int(item["face_index"]), "vertex_indices": vertices, "barycentric_sum_error": sum_error, "xyz_reconstruction_error_m": xyz_error, "normal_z": float(polygon.normal.z), "xyz_local_m": list(point), "side": side})
        checks.extend([
            {"id": "frozen_face_vertices", "passed": all_binding},
            {"id": "barycentric_interior", "passed": all_bary, "metrics": {"max_sum_error": max_sum_error}},
            {"id": "stored_xyz_reconstruction", "passed": all_position, "metrics": {"max_error_m": max_xyz_error}},
            {"id": "dorsal_surface", "passed": all_dorsal},
            {"id": "subject_laterality", "passed": all_side},
        ])
    finally:
        evaluated.to_mesh_clear()
    passed = all(item["passed"] for item in checks)
    report = {"schema": "skel-engineering-atlas-qc-v1", "passed": passed, "medical_truth": False, "checks": checks, "summary": {"pass": sum(item["passed"] for item in checks), "fail": sum(not item["passed"] for item in checks)}, "points": details}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_VERIFY_ENG_BACK20=" + ("PASS" if passed else "FAIL"))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
