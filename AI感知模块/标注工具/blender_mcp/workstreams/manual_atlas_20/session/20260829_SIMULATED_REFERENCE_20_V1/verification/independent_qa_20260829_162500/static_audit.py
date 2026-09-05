import hashlib
import json
import math
import os
import sys


EXPECTED = {
    "schema_version": "smpl-acupoint-annotation-v5",
    "plugin_version": "0.6.3",
    "family": "SKEL",
    "variant": "1.1.1",
    "gender": "female",
    "model_template_id": "skel-female-trunk-limb-v2.3",
    "session_template_id": "SKEL_FEMALE_TRUNK_LIMB_v2.3",
    "canonical_shape_id": "shape-zero",
    "canonical_pose_id": "template-default",
    "object_name": "SKEL-skin-female",
    "vertex_count": 6890,
    "polygon_count": 13776,
    "topology_signature_sha256": "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
    "annotation_count": 20,
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    atlas_path, canonical_path, work_path, output_path = sys.argv[1:]
    with open(atlas_path, "r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    model = payload.get("model") or {}
    session = payload.get("session") or {}
    annotations = payload.get("annotations") or []
    failures = []

    declared = {
        "schema_version": payload.get("schema_version"),
        "plugin_version": payload.get("plugin_version"),
        "family": model.get("family"),
        "variant": model.get("variant"),
        "gender": model.get("gender"),
        "model_template_id": model.get("template_id"),
        "session_template_id": session.get("template_id"),
        "canonical_shape_id": model.get("canonical_shape_id"),
        "canonical_pose_id": model.get("canonical_pose_id"),
        "object_name": model.get("object_name"),
        "vertex_count": model.get("vertex_count"),
        "polygon_count": model.get("polygon_count"),
        "topology_signature_sha256": model.get("topology_signature_sha256"),
        "annotation_count": len(annotations),
    }
    for field, expected in EXPECTED.items():
        if declared.get(field) != expected:
            failures.append(
                f"{field}: expected {expected!r}, got {declared.get(field)!r}"
            )

    ids = [str(item.get("id", "")) for item in annotations]
    point_ids = [str(item.get("point_id", "")) for item in annotations]
    code_sides = [
        (str(item.get("code", "")).strip().upper(), str(item.get("side", "")))
        for item in annotations
    ]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        failures.append("annotation ids are empty or not unique")
    if len(point_ids) != len(set(point_ids)) or any(not value for value in point_ids):
        failures.append("point_id values are empty or not unique")
    if len(code_sides) != len(set(code_sides)):
        failures.append("code+side pairs are not unique")
    for item, pair in zip(annotations, code_sides):
        expected_point_id = f"{pair[0]}_{pair[1]}"
        if item.get("point_id") != expected_point_id:
            failures.append(
                f"point_id mismatch: {item.get('point_id')} != {expected_point_id}"
            )

    max_sum_error = 0.0
    min_weight = math.inf
    max_weight = -math.inf
    one_third_count = 0
    malformed_bary = []
    malformed_indices = []
    notes_failures = []
    status_values = set()
    for item in annotations:
        label = str(item.get("point_id", item.get("id", "unknown")))
        bary = item.get("barycentric")
        if (
            not isinstance(bary, list)
            or len(bary) != 3
            or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in bary)
        ):
            malformed_bary.append(label)
        else:
            bary = [float(value) for value in bary]
            max_sum_error = max(max_sum_error, abs(sum(bary) - 1.0))
            min_weight = min(min_weight, *bary)
            max_weight = max(max_weight, *bary)
            if all(abs(value - 1.0 / 3.0) < 1e-7 for value in bary):
                one_third_count += 1
            if abs(sum(bary) - 1.0) >= 1e-7 or any(
                value < -1e-7 or value > 1.0 + 1e-7 for value in bary
            ):
                malformed_bary.append(label)
        face = item.get("face_index")
        vertices = item.get("vertex_indices")
        if (
            not isinstance(face, int)
            or not 0 <= face < EXPECTED["polygon_count"]
            or not isinstance(vertices, list)
            or len(vertices) != 3
            or not all(isinstance(value, int) and 0 <= value < EXPECTED["vertex_count"] for value in vertices)
        ):
            malformed_indices.append(label)
        notes = str(item.get("notes", ""))
        if "SIMULATED_FROM_REFERENCE" not in notes or "medical_validated=false" not in notes:
            notes_failures.append(label)
        status_values.add(str(item.get("review_status", "")))

    if malformed_bary:
        failures.append(f"invalid barycentric records: {malformed_bary}")
    if malformed_indices:
        failures.append(f"invalid face/vertex index records: {malformed_indices}")
    if notes_failures:
        failures.append(f"missing simulation/non-medical notes: {notes_failures}")

    canonical_hash = sha256_file(canonical_path)
    work_hash = sha256_file(work_path)
    atlas_hash = sha256_file(atlas_path)
    declared_template_hash = str(session.get("template_file_sha256", "")).upper()
    if canonical_hash != declared_template_hash:
        failures.append(
            f"canonical hash {canonical_hash} != session template hash {declared_template_hash}"
        )

    result = {
        "pass": not failures,
        "failures": failures,
        "atlas_path": atlas_path,
        "atlas_sha256": atlas_hash,
        "canonical_path": canonical_path,
        "canonical_sha256": canonical_hash,
        "work_blend_path": work_path,
        "work_blend_sha256": work_hash,
        "declared": declared,
        "session": {
            "session_id": session.get("session_id"),
            "doctor_id": session.get("doctor_id"),
            "task_id": session.get("task_id"),
            "workflow_mode": session.get("workflow_mode"),
            "template_file_sha256": declared_template_hash,
        },
        "unique_annotation_ids": len(set(ids)),
        "unique_point_ids": len(set(point_ids)),
        "unique_code_side_pairs": len(set(code_sides)),
        "barycentric": {
            "max_abs_sum_minus_one": max_sum_error,
            "minimum_weight": min_weight,
            "maximum_weight": max_weight,
            "all_in_range_and_sum_one_within_1e-7": not malformed_bary,
            "exact_one_third_within_1e-7_count": one_third_count,
            "all_are_one_third": one_third_count == len(annotations),
        },
        "face_vertex_index_shape_and_ranges_valid": not malformed_indices,
        "simulation_notes_present_count": len(annotations) - len(notes_failures),
        "review_status_values": sorted(status_values),
        "medical_status": payload.get("medical_status"),
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
