#!/usr/bin/env python3
"""Independent audit of the isolated RGB-D prototype output bundle."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from PIL import Image

from verify_sample import (
    DEPTH_RAY_ABS_TOL_M,
    DEPTH_RAY_REL_TOL,
    DEFAULT_PROTECTED_MANIFEST,
    Recorder,
    _image_luma_bytes,
    _load_json,
    _mat_vec,
    _protected_checks,
    _read_npy_2d,
    _sha256,
    _utc_now,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PIXEL_PROBE = SCRIPT_DIR / "blender_pixel_probe.py"


def _sample_indices(indices: list[int], limit: int) -> list[int]:
    if len(indices) <= limit:
        return indices
    return [indices[round(i * (len(indices) - 1) / (limit - 1))] for i in range(limit)]


def _sha_manifest(recorder: Recorder, root: Path) -> dict[str, Any]:
    path = root / "SHA256SUMS.txt"
    evidence: dict[str, Any] = {"path": str(path), "entries": []}
    if not path.is_file():
        recorder.add("prototype_sha256_manifest", "FAIL", "SHA256SUMS.txt is missing.", severity="P0")
        return evidence
    listed: set[str] = set()
    all_match = True
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        digest, relative = raw.strip().split(None, 1)
        relative = relative.strip().replace("\\", "/")
        listed.add(relative)
        candidate = root / Path(relative)
        actual = _sha256(candidate) if candidate.is_file() else None
        matches = actual == digest.lower()
        all_match &= matches
        evidence["entries"].append({"path": relative, "expected": digest.lower(), "actual": actual, "matches": matches})
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.txt"
    }
    coverage_missing = sorted(actual_files - listed)
    stale_entries = sorted(listed - actual_files)
    complete = not coverage_missing and not stale_entries
    recorder.add(
        "prototype_sha256_manifest",
        "PASS" if all_match and complete else "FAIL",
        "All prototype files match SHA256SUMS and manifest coverage is complete.",
        severity="P0",
        metrics={"entry_count": len(listed), "hashes_match": all_match, "missing_from_manifest": coverage_missing, "stale_entries": stale_entries},
    )
    return evidence


def _load_case(recorder: Recorder, case_dir: Path) -> dict[str, Any]:
    metadata = _load_json(case_dir / "metadata.json")
    intrinsics = metadata["camera"]["intrinsics"]
    expected_hw = (int(intrinsics["height"]), int(intrinsics["width"]))
    depth_hw, scene_depth = _read_npy_2d(case_dir / "scene_depth_z.npy")
    body_hw, body_depth = _read_npy_2d(case_dir / "body_only_depth_z.npy")
    skin_hw, skin = _image_luma_bytes(case_dir / "visible_skin_mask.png")
    valid_hw, valid = _image_luma_bytes(case_dir / "depth_valid_mask.png")
    with Image.open(case_dir / "rgb.png") as rgb:
        rgb_hw = (rgb.height, rgb.width)
    aligned = expected_hw == depth_hw == body_hw == skin_hw == valid_hw == rgb_hw
    recorder.add(
        f"{case_dir.name}_pixel_alignment",
        "PASS" if aligned else "FAIL",
        f"{case_dir.name}: RGB/depth/body-depth/masks match declared camera resolution.",
        severity="P0",
        metrics={"expected_hw": expected_hw, "rgb_hw": rgb_hw, "depth_hw": depth_hw, "body_hw": body_hw, "skin_hw": skin_hw, "valid_hw": valid_hw},
    )
    skin_binary = set(skin).issubset({0, 255})
    valid_binary = set(valid).issubset({0, 255})
    depth_encoding = True
    for index, z_value in enumerate(scene_depth):
        z = float(z_value)
        if not math.isfinite(z) or z < 0.0:
            depth_encoding = False
            break
        if valid[index] == 0 and abs(z) > 1.0e-7:
            depth_encoding = False
            break
        if valid[index] == 255 and z <= 0.0:
            depth_encoding = False
            break
        if skin[index] == 255 and valid[index] != 255:
            depth_encoding = False
            break
    recorder.add(
        f"{case_dir.name}_encoding",
        "PASS" if skin_binary and valid_binary and depth_encoding else "FAIL",
        f"{case_dir.name}: binary masks and zero-background positive-Z depth encoding are valid.",
        metrics={"skin_binary": skin_binary, "valid_binary": valid_binary, "depth_encoding": depth_encoding},
    )
    tolerance = float(metadata["mask_contract"]["depth_match_tolerance_m"])
    derived_skin = bytearray(len(skin))
    mismatch = 0
    for index in range(len(skin)):
        expected = (
            float(scene_depth[index]) > 0.0
            and float(body_depth[index]) > 0.0
            and abs(float(scene_depth[index]) - float(body_depth[index])) <= tolerance
        )
        derived_skin[index] = 255 if expected else 0
        if derived_skin[index] != skin[index]:
            mismatch += 1
    recorder.add(
        f"{case_dir.name}_mask_derivation",
        "PASS" if mismatch == 0 else "FAIL",
        f"{case_dir.name}: visible skin mask exactly follows its declared scene/body depth rule.",
        severity="P1",
        metrics={"mismatch_pixels": mismatch, "tolerance_m": tolerance},
    )
    return {
        "dir": case_dir,
        "metadata": metadata,
        "height": expected_hw[0],
        "width": expected_hw[1],
        "scene_depth": scene_depth,
        "body_depth": body_depth,
        "skin": skin,
        "valid": valid,
    }


def _known_plane(recorder: Recorder, case: dict[str, Any]) -> None:
    values = [float(value) for value in case["scene_depth"]]
    errors = [abs(value - 2.0) for value in values]
    all_valid = all(value == 255 for value in case["valid"])
    all_skin = all(value == 255 for value in case["skin"])
    z_ok = max(errors, default=math.inf) <= 2.0e-5
    intrinsics = case["metadata"]["camera"]["intrinsics"]
    fx, fy, cx, cy = (float(intrinsics[key]) for key in ("fx", "fy", "cx", "cy"))
    corner_u, corner_v = 16.5, 16.5
    ray_distance = 2.0 * math.sqrt(1.0 + ((corner_u - cx) / fx) ** 2 + ((corner_v - cy) / fy) ** 2)
    distinguishes_z = ray_distance - values[16 * case["width"] + 16] > 0.1
    recorder.add(
        "known_plane_camera_z",
        "PASS" if z_ok and all_valid and all_skin and distinguishes_z else "FAIL",
        "Known fronto-parallel 2 m plane proves the stored pass is camera Zc rather than Euclidean ray distance.",
        severity="P0",
        metrics={"max_abs_z_error_m": max(errors, default=None), "all_valid": all_valid, "all_skin": all_skin, "corner_ray_distance_m": ray_distance, "corner_stored_z_m": values[16 * case["width"] + 16]},
    )


def _compare_skel_cases(recorder: Recorder, baseline: dict[str, Any], occluded: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    same_camera = baseline["metadata"]["camera"] == occluded["metadata"]["camera"]
    same_shape = baseline["height"] == occluded["height"] and baseline["width"] == occluded["width"]
    body_errors = [abs(float(a) - float(b)) for a, b in zip(baseline["body_depth"], occluded["body_depth"])]
    body_same = max(body_errors, default=math.inf) <= 1.0e-7
    recorder.add(
        "baseline_occluded_control_state",
        "PASS" if same_camera and same_shape and body_same else "FAIL",
        "Baseline and occluded cases share camera/resolution, and body-only depth is unchanged.",
        severity="P0",
        metrics={"same_camera_metadata": same_camera, "same_shape": same_shape, "body_only_depth_max_abs_error_m": max(body_errors, default=None)},
    )
    newly_occluded = []
    for index in range(len(baseline["skin"])):
        if (
            baseline["skin"][index] == 255
            and occluded["skin"][index] == 0
            and float(occluded["scene_depth"][index]) > 0.0
            and float(occluded["scene_depth"][index]) + 1.0e-4 < float(baseline["body_depth"][index])
        ):
            newly_occluded.append(index)
    declared_count = int(summary["skel"]["external_occlusion"]["newly_occluded_skin_pixel_count"])
    recorder.add(
        "external_occlusion_buffer_semantics",
        "PASS" if newly_occluded and len(newly_occluded) == declared_count else "FAIL",
        "Foreground depth replaces baseline skin depth and visible-skin mask becomes zero on the same pixels.",
        severity="P0",
        metrics={"independent_newly_occluded_pixels": len(newly_occluded), "declared_newly_occluded_pixels": declared_count},
    )

    point = summary["skel"]["engineering_point"]
    camera = baseline["metadata"]["camera"]
    camera_xyz = _mat_vec(camera["world_to_opencv_camera"], [float(v) for v in point["xyz_world_m"]] + [1.0])[:3]
    k = camera["intrinsics"]["K"]
    projected = [float(k[0][0]) * camera_xyz[0] / camera_xyz[2] + float(k[0][2]), float(k[1][1]) * camera_xyz[1] / camera_xyz[2] + float(k[1][2])]
    uv_error = max(abs(projected[i] - float(point["uv_top_left_px"][i])) for i in range(2))
    px, py = (int(v) for v in point["sample_pixel_xy"])
    index = py * baseline["width"] + px
    point_semantics = (
        uv_error <= 1.0e-3
        and baseline["skin"][index] == 255
        and abs(float(baseline["scene_depth"][index]) - camera_xyz[2]) <= 0.01
        and occluded["skin"][index] == 0
        and 0.0 < float(occluded["scene_depth"][index]) < camera_xyz[2]
    )
    recorder.add(
        "engineering_point_occlusion_pixel",
        "PASS" if point_semantics else "FAIL",
        "Engineering point projects consistently; baseline sees skin while occluded case records nearer non-skin depth.",
        severity="P0",
        metrics={"uv_error_px": uv_error, "point_zc_m": camera_xyz[2], "baseline_pixel_depth_m": float(baseline["scene_depth"][index]), "occluded_pixel_depth_m": float(occluded["scene_depth"][index]), "baseline_skin": baseline["skin"][index], "occluded_skin": occluded["skin"][index]},
    )
    return {"newly_occluded_indices": newly_occluded, "engineering_point_projected_uv": projected}


def _independent_baseline_rays(
    recorder: Recorder,
    baseline: dict[str, Any],
    canonical_blend: Path,
    blender_exe: Path,
    output_dir: Path,
    ignored_objects: list[str],
) -> dict[str, Any]:
    skin_indices = [index for index, value in enumerate(baseline["skin"]) if value == 255]
    background_indices = [index for index, value in enumerate(baseline["valid"]) if value == 0]
    chosen = [("skin", index) for index in _sample_indices(skin_indices, 32)] + [("background", index) for index in _sample_indices(background_indices, 16)]
    pixels = []
    for group, index in chosen:
        row, column = divmod(index, baseline["width"])
        pixels.append({"group": group, "row": row, "column": column, "stored_zc_m": float(baseline["scene_depth"][index]), "skin_mask": baseline["skin"][index] == 255, "depth_valid": baseline["valid"][index] == 255})
    request = {"ignored_render_objects": ignored_objects, "pixels": pixels}
    output_dir.mkdir(parents=True, exist_ok=True)
    request_path = output_dir / "prototype_baseline_ray_request.json"
    probe_path = output_dir / "prototype_baseline_ray_probe.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [str(blender_exe), "--background", str(canonical_blend), "--python", str(PIXEL_PROBE), "--", "--metadata", str(baseline["dir"] / "metadata.json"), "--requests", str(request_path), "--output", str(probe_path)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if completed.returncode != 0 or not probe_path.is_file():
        recorder.add("prototype_independent_baseline_rays", "FAIL", "Independent Blender pixel probe failed to run.", severity="P0", metrics={"returncode": completed.returncode, "stderr_tail": completed.stderr[-2000:]})
        return {"command": command, "returncode": completed.returncode}
    probe = _load_json(probe_path)
    target = str(baseline["metadata"]["mask_contract"]["skin_object"])
    mismatch = 0
    errors = []
    for result in probe["results"]:
        source = result["request"]
        if source["group"] == "skin":
            if not result.get("hit") or result.get("hit_object") != target:
                mismatch += 1
            else:
                error = abs(float(result["hit_zc_m"]) - float(source["stored_zc_m"]))
                errors.append(error)
                tolerance = max(DEPTH_RAY_ABS_TOL_M, DEPTH_RAY_REL_TOL * abs(float(result["hit_zc_m"])))
                if error > tolerance:
                    mismatch += 1
        elif result.get("hit") or source["depth_valid"] or source["skin_mask"] or abs(float(source["stored_zc_m"])) > 1.0e-7:
            mismatch += 1
    recorder.add(
        "prototype_independent_baseline_rays",
        "PASS" if probe["results"] and mismatch == 0 else "FAIL",
        "Independent fresh-Blender pixel-center rays agree with baseline Zc, skin object, background and top-left Y orientation.",
        severity="P0",
        metrics={"sample_count": len(probe["results"]), "mismatch_count": mismatch, "max_depth_error_m": max(errors, default=0.0)},
    )
    return {"command": command, "returncode": completed.returncode, "probe_path": str(probe_path), "probe_sha256": _sha256(probe_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prototype-root", required=True, type=Path)
    parser.add_argument("--canonical-blend", required=True, type=Path)
    parser.add_argument("--blender-exe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.prototype_root.resolve()
    recorder = Recorder()
    report: dict[str, Any] = {"schema": "independent-isolated-rgbd-prototype-audit-v1", "created_at": _utc_now(), "prototype_root": str(root), "independence_statement": "Reads only frozen output buffers/metadata and uses a separately authored Blender pixel-ray probe; imports no generator code."}
    report["protected_assets"] = _protected_checks(recorder, DEFAULT_PROTECTED_MANIFEST)
    report["sha256_manifest"] = _sha_manifest(recorder, root)
    summary = _load_json(root / "run_summary.json")
    recorder.add("prototype_self_report", "PASS" if summary.get("passed") else "FAIL", "Prototype run_summary declares PASS.", severity="P1")
    known = _load_case(recorder, root / "known_plane")
    baseline = _load_case(recorder, root / "skel_baseline")
    occluded = _load_case(recorder, root / "skel_occluded")
    _known_plane(recorder, known)
    report["skel_case_comparison"] = _compare_skel_cases(recorder, baseline, occluded, summary)
    report["baseline_ray_probe"] = _independent_baseline_rays(recorder, baseline, args.canonical_blend.resolve(), args.blender_exe.resolve(), args.output.resolve().parent, summary["skel"].get("hidden_non_skin_renderables", []))
    recorder.add("external_occluder_object_replay", "SKIP", "Prototype did not preserve an exact occluded scene snapshot; buffer semantics pass, but independent replay of the named occluder object is not possible.", severity="P1")
    report["checks"] = recorder.checks
    report["passed"] = recorder.passed()
    report["summary"] = {"pass": sum(c["status"] == "PASS" for c in recorder.checks), "fail": sum(c["status"] == "FAIL" for c in recorder.checks), "skip": sum(c["status"] == "SKIP" for c in recorder.checks)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "summary": report["summary"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
