import hashlib
import json
import math
import os
import sys
import traceback


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def max_abs_error(left, right):
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def load_payload(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def annotation_map(payload):
    return {item["id"]: item for item in payload["annotations"]}


def inspect_loaded_scene(bpy, annotator, blend_path, atlas_path):
    bpy.ops.wm.open_mainfile(filepath=blend_path, load_ui=False)
    scene = bpy.context.scene
    annotator._initialize_session(scene)
    target = scene.smpl_acupoint_settings.target_mesh
    payload = load_payload(atlas_path)
    expected = annotation_map(payload)
    actual = {item.annotation_id: item for item in scene.smpl_acupoint_annotations}
    details = []
    max_bary_error = 0.0
    mismatches = []
    for annotation_id, source in expected.items():
        item = actual.get(annotation_id)
        if item is None:
            mismatches.append(f"missing annotation id {annotation_id}")
            continue
        bary_error = max_abs_error(item.barycentric, source["barycentric"])
        max_bary_error = max(max_bary_error, bary_error)
        _, _, vertices = annotator._surface_sample(
            target, item.face_index, item.barycentric
        )
        entry = {
            "id": annotation_id,
            "point_id": f"{item.code}_{item.side}",
            "face_expected": int(source["face_index"]),
            "face_actual": int(item.face_index),
            "vertices_expected": [int(v) for v in source["vertex_indices"]],
            "vertices_actual": [int(v) for v in vertices],
            "bary_expected": [float(v) for v in source["barycentric"]],
            "bary_actual": [float(v) for v in item.barycentric],
            "bary_max_abs_error": bary_error,
        }
        details.append(entry)
        if entry["face_actual"] != entry["face_expected"]:
            mismatches.append(f"{entry['point_id']}: face mismatch")
        if entry["vertices_actual"] != entry["vertices_expected"]:
            mismatches.append(f"{entry['point_id']}: vertices mismatch")
        if bary_error >= 1e-7:
            mismatches.append(f"{entry['point_id']}: bary error {bary_error}")
    extra_ids = sorted(set(actual) - set(expected))
    if extra_ids:
        mismatches.append(f"extra annotation ids: {extra_ids}")
    return {
        "mode": "inspect_saved_work_copy",
        "blend_path": blend_path,
        "blend_sha256": sha256_file(blend_path),
        "target_object": target.name if target else None,
        "model_descriptor": annotator._model_descriptor(target) if target else None,
        "saved_annotation_count": len(scene.smpl_acupoint_annotations),
        "expected_annotation_count": len(payload["annotations"]),
        "max_bary_abs_error": max_bary_error,
        "mismatches": mismatches,
        "details": details,
        "pass": (
            target is not None
            and len(actual) == len(expected) == 20
            and not mismatches
        ),
    }


def import_into_canonical(bpy, annotator, blend_path, atlas_path, evidence_blend):
    bpy.ops.wm.open_mainfile(filepath=blend_path, load_ui=False)
    scene = bpy.context.scene
    annotator._initialize_session(scene)
    target = scene.smpl_acupoint_settings.target_mesh
    payload = load_payload(atlas_path)
    expected = annotation_map(payload)
    initial_count = len(scene.smpl_acupoint_annotations)
    imported, skipped = annotator.import_annotations(scene, target, atlas_path)
    actual = {item.annotation_id: item for item in scene.smpl_acupoint_annotations}
    details = []
    mismatches = []
    max_bary_error = 0.0
    max_canonical_position_error = 0.0
    for annotation_id, source in expected.items():
        item = actual.get(annotation_id)
        if item is None:
            mismatches.append(f"missing annotation id {annotation_id}")
            continue
        bary_error = max_abs_error(item.barycentric, source["barycentric"])
        max_bary_error = max(max_bary_error, bary_error)
        _, _, vertices = annotator._surface_sample(
            target, item.face_index, item.barycentric
        )
        canonical_point = annotator._canonical_local_sample(
            target, item.face_index, item.barycentric
        )
        canonical_error = max_abs_error(
            canonical_point, source["canonical_local_position_m"]
        )
        max_canonical_position_error = max(
            max_canonical_position_error, canonical_error
        )
        entry = {
            "id": annotation_id,
            "point_id": f"{item.code}_{item.side}",
            "face_expected": int(source["face_index"]),
            "face_actual": int(item.face_index),
            "vertices_expected": [int(v) for v in source["vertex_indices"]],
            "vertices_actual": [int(v) for v in vertices],
            "bary_expected": [float(v) for v in source["barycentric"]],
            "bary_actual": [float(v) for v in item.barycentric],
            "bary_max_abs_error": bary_error,
            "canonical_position_max_abs_error_m": canonical_error,
        }
        details.append(entry)
        if entry["face_actual"] != entry["face_expected"]:
            mismatches.append(f"{entry['point_id']}: face mismatch")
        if entry["vertices_actual"] != entry["vertices_expected"]:
            mismatches.append(f"{entry['point_id']}: vertices mismatch")
        if bary_error >= 1e-7:
            mismatches.append(f"{entry['point_id']}: bary error {bary_error}")
        if canonical_error >= 1e-7:
            mismatches.append(
                f"{entry['point_id']}: canonical position error {canonical_error}"
            )
    extra_ids = sorted(set(actual) - set(expected))
    if extra_ids:
        mismatches.append(f"extra annotation ids: {extra_ids}")
    bpy.ops.wm.save_as_mainfile(filepath=evidence_blend, check_existing=False)
    return {
        "mode": "formal_plugin_import_into_clean_canonical_copy",
        "canonical_copy_path": blend_path,
        "canonical_copy_sha256_before_import": sha256_file(blend_path),
        "evidence_blend_path": evidence_blend,
        "evidence_blend_sha256": sha256_file(evidence_blend),
        "plugin_file": annotator.__file__,
        "plugin_version": annotator.PLUGIN_VERSION,
        "plugin_schema": annotator.SCHEMA_VERSION,
        "target_object": target.name if target else None,
        "model_descriptor": annotator._model_descriptor(target) if target else None,
        "initial_annotation_count": initial_count,
        "imported": imported,
        "skipped": skipped,
        "final_annotation_count": len(scene.smpl_acupoint_annotations),
        "max_bary_abs_error": max_bary_error,
        "max_canonical_position_abs_error_m": max_canonical_position_error,
        "mismatches": mismatches,
        "details": details,
        "pass": (
            target is not None
            and initial_count == 0
            and imported == 20
            and skipped == 0
            and len(actual) == len(expected) == 20
            and not mismatches
        ),
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    if len(argv) != 6:
        raise RuntimeError(
            "expected: MODE BLEND ATLAS ADDON_PARENT OUTPUT_JSON EVIDENCE_BLEND"
        )
    mode, blend_path, atlas_path, addon_parent, output_path, evidence_blend = argv
    sys.path.insert(0, addon_parent)
    import bpy
    import smpl_acupoint_annotator as annotator

    if not hasattr(bpy.types.Scene, "smpl_acupoint_settings"):
        annotator.register()
    try:
        if mode == "work":
            result = inspect_loaded_scene(bpy, annotator, blend_path, atlas_path)
        elif mode == "canonical":
            result = import_into_canonical(
                bpy, annotator, blend_path, atlas_path, evidence_blend
            )
        else:
            raise ValueError(f"unknown mode: {mode}")
    except Exception as exc:
        result = {
            "mode": mode,
            "pass": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("INDEPENDENT_ATLAS_QA_RESULT=" + ("PASS" if result["pass"] else "FAIL"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
