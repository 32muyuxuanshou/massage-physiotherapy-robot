#!/usr/bin/env python3
"""Two-stage, non-random 30-sample engineering generator with immutable preflight."""
from __future__ import annotations

import argparse
import array
import ast
import json
import math
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import build_engineering_atlas_back20 as b

WS = b.TOOL_ROOT / "workstreams" / "qc_dataset_30"
CONFIG = WS / "dataset_config_v1.json"
ATLAS = b.AI_ROOT / "outputs" / "交付文件" / "2026-08-28_17-05-07" / "engineering_atlas_back20_v1.json"
PROBE = b.NATURAL_WS / "probe_pose_snapshot.py"
PREVIEW = b.NATURAL_WS / "render_preview.py"
EDGES = WS / "probe_sampling_edges.py"
POSE_INDEX = {"head_twist": 25, "shoulder_r_x": 29, "shoulder_r_y": 30, "elbow_flexion_r": 32,
              "shoulder_l_x": 39, "shoulder_l_y": 40, "elbow_flexion_l": 42}


def bj(script, blend, arguments, sentinel):
    return b.run([str(b.BLENDER), "--background", str(blend), "--python", str(script), "--", *map(str, arguments)], env=b.environment(), sentinel=sentinel)


def source_hashes():
    paths = [CONFIG, ATLAS, b.PROFILE, b.CONTRACT, b.CANONICAL, b.FORMAL_ATLAS, b.OFFICIAL_ZIP,
             b.GENERATE, b.PREPARE, b.EXPORT, PROBE, b.VERIFY_SAMPLE, EDGES, Path(__file__), Path(b.__file__)]
    paths += sorted((b.TOOL_ROOT.parent / "blender_addons" / "modules" / "training_export_core").glob("*.py"))
    paths += sorted((b.WORKBENCH / "user_resources" / "scripts" / "addons" / "modules" / "training_export_core").glob("*.py"))
    paths += sorted(b.VERIFY_WS.glob("*.py"))
    return {str(p): b.sha256(p) for p in paths}


def profile(shape, pose):
    value = b.read_json(b.PROFILE)
    value["betas"] = shape["betas"]
    value["profile_id"] = shape["shape_id"] + "_" + pose["pose_id"]
    for key, degrees in pose["overrides_degrees"].items():
        value["pose_degrees"][key] = degrees
        value["pose_vector_degrees"][POSE_INDEX[key]] = degrees
    return value


def montage(items, output, columns=5):
    size, header = (320, 256), 28
    canvas = Image.new("RGB", (columns * size[0], math.ceil(len(items) / columns) * (size[1] + header)), "white")
    draw = ImageDraw.Draw(canvas)
    for i, (label, path) in enumerate(items):
        x, y = (i % columns) * size[0], (i // columns) * (size[1] + header)
        with Image.open(path) as img:
            canvas.paste(img.convert("RGB").resize(size, Image.Resampling.LANCZOS), (x, y + header))
        draw.text((x + 5, y + 6), label, fill="black", font=ImageFont.load_default())
    canvas.save(output)


def preflight():
    cfg = b.read_json(CONFIG)
    if b.sha256(ATLAS) != cfg["atlas_sha256"]:
        raise ValueError("Frozen Atlas hash mismatch")
    root = b.AI_ROOT / "outputs" / "交付文件" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    root.mkdir(parents=True, exist_ok=False)
    for sub in ("profiles", "camera_contracts", "snapshots", "preflight", "samples", "qc_reports"):
        (root / sub).mkdir()
    shutil.copy2(CONFIG, root / "dataset_config_v1.json")
    shutil.copy2(ATLAS, root / ATLAS.name)
    hashes = source_hashes()
    b.write_json(root / "source_hashes.json", hashes)
    atlas = b.read_json(ATLAS)
    index, previews = [], []
    reference_transform = None
    for si, shape in enumerate(cfg["shapes"]):
        for pi, pose in enumerate(cfg["poses"]):
            tag = f"S{si}_P{pi}"
            prof = profile(shape, pose)
            prof_path = root / "profiles" / f"{tag}.json"
            b.write_json(prof_path, prof)
            native = root / "preflight" / f"native_{tag}"
            b.run([str(b.PYTHON), str(b.GENERATE), "--profile", str(prof_path), "--output", str(native)])
            for ci, camera in enumerate(cfg["cameras"]):
                case = f"{tag}_C{ci}"
                contract = b.read_json(b.CONTRACT)
                contract["camera_matrix_world"] = camera["matrix_world"]
                contract_path = root / "camera_contracts" / f"C{ci}.json"
                if not contract_path.exists():
                    b.write_json(contract_path, contract)
                snapshot = root / "snapshots" / f"{case}.blend"
                prep_path = root / "preflight" / f"{case}_prepare.json"
                bj(b.PREPARE, b.CANONICAL, ["--snapshot", snapshot, "--result", prep_path, "--native-pose-dir", native,
                    "--pose-profile", prof_path, "--fixed-scene-contract", contract_path, "--width", 1280, "--height", 1024], "ACU_PREPARE_PRONE_SCENE=PASS")
                probe_path = root / "preflight" / f"{case}_probe.json"
                bj(PROBE, snapshot, ["--fixture", ATLAS, "--output", probe_path, "--width", 1280, "--height", 1024], "ACU_POSE_SNAPSHOT_PROBE=PASS")
                prep, probe = b.read_json(prep_path), b.read_json(probe_path)
                if reference_transform is None:
                    reference_transform = prep["prone_transform"]
                clearance = prep["body_bounds_world_m"]["min"][2]
                points = probe["points"]
                binding_ok = len(points) == 20 and all(
                    p["point_id"] == a["point_id"] and p["face_index"] == a["face_index"] and
                    p["vertex_indices"] == a["vertex_indices"] and p["barycentric"] == a["barycentric"]
                    for p, a in zip(points, atlas["anchors"]))
                checks = {
                    "topology": probe["model"]["topology_signature_sha256"] == atlas["model"]["topology_signature_sha256"],
                    "frozen_bindings": binding_ok,
                    "same_rigid_transform": prep["prone_transform"] == reference_transform,
                    "bed_clearance": cfg["qc_thresholds"]["body_min_clearance_m"] <= clearance <= cfg["qc_thresholds"]["body_max_clearance_m"],
                    "all_20_visible_in_frame": len(points) == 20 and all(p["visible"] and 0 <= p["uv_pixel_opencv"][0] < 1280 and 0 <= p["uv_pixel_opencv"][1] < 1024 for p in points),
                    "profile_recorded": probe["betas"] == shape["betas"] and probe["pose_degrees"] == prof["pose_degrees"],
                }
                entry = {"case": case, "sample_id": f"sample_{len(index)+1:06d}", "shape_id": shape["shape_id"], "pose_id": pose["pose_id"], "camera_id": camera["camera_id"],
                         "profile": str(prof_path.relative_to(root)), "snapshot": str(snapshot.relative_to(root)), "prepare": str(prep_path.relative_to(root)),
                         "snapshot_sha256": b.sha256(snapshot), "profile_sha256": b.sha256(prof_path),
                         "checks": checks, "body_clearance_m": clearance, "passed": all(checks.values())}
                index.append(entry)
                if si == 0:
                    preview = root / "preflight" / f"{case}_preview.png"
                    bj(PREVIEW, snapshot, [preview], "ACU_NATURAL_PRONE_PREVIEW=PASS")
                    previews.append((case, preview))
                print(f"PREFLIGHT {case}: {'PASS' if entry['passed'] else 'FAIL'} clearance={clearance:.6f}", flush=True)
    b.write_json(root / "dataset_index.json", index)
    passed = len(index) == 30 and all(e["passed"] for e in index) and hashes == source_hashes()
    b.write_json(root / "preflight_report.json", {"passed": passed, "cases": index, "source_hashes_unchanged": hashes == source_hashes(), "visual_review_required": True})
    montage(previews, root / "preflight_pose_camera_montage.png")
    b.write_json(root / "NOT_RELEASED.json", {"reason": "Preflight only. Batch generation and final visual QC are not complete."})
    print(json.dumps({"preflight_passed": passed, "root": str(root)}, ensure_ascii=False), flush=True)


def depth_array(path):
    with path.open("rb") as f:
        if f.read(6) != b"\x93NUMPY":
            raise ValueError("Not NPY")
        major, _minor = f.read(2)
        n = struct.unpack("<H" if major == 1 else "<I", f.read(2 if major == 1 else 4))[0]
        header = ast.literal_eval(f.read(n).decode("latin1"))
        if header["descr"] != "<f4" or header["fortran_order"]:
            raise ValueError("Expected little-endian C-order float32")
        values = array.array("f")
        values.frombytes(f.read())
        if sys.byteorder != "little":
            values.byteswap()
        h, w = header["shape"]
        if len(values) != h*w:
            raise ValueError("Depth size mismatch")
        return h, w, values


def strict_qc(sample, atlas, profile_data, cfg):
    labels = b.read_json(sample / "labels.json")
    h, w, depths = depth_array(sample / "scene_depth_z.npy")
    k = labels["camera"]["intrinsics"]
    checks = {"resolution": [w, h] == cfg["resolution"], "point_count": len(labels["points"]) == 20,
              "shape_recorded": labels["scene"]["native_shape_betas"] == profile_data["betas"],
              "pose_recorded": labels["scene"]["native_pose_parameters_degrees"] == profile_data["pose_degrees"]}
    details = []
    with Image.open(sample / "skin_mask.png") as mask:
        for point, anchor in zip(labels["points"], atlas["anchors"]):
            u, v = point["uv_pixel_opencv"]
            in_frame = 0 <= u < w and 0 <= v < h
            observed = depths[int(v)*w+int(u)] if in_frame else 0.0
            gt = point["xyz_camera_opencv_m"]
            lifted = [(u-k["cx"])*observed/k["fx"], (v-k["cy"])*observed/k["fy"], observed]
            zerror, xyzerror = abs(observed-gt[2]), math.dist(lifted, gt)
            binding = all(point[key] == anchor[key] for key in ("point_id", "face_index", "vertex_indices", "barycentric", "side"))
            ok = binding and in_frame and point["visible"] and point["ray_hit_object"] == "SKEL-skin-female" and observed > 0 and mask.getpixel((int(u), int(v))) == 255
            ok = ok and zerror <= cfg["qc_thresholds"]["visible_point_depth_error_m"] and xyzerror <= cfg["qc_thresholds"]["visible_point_backprojection_error_m"]
            details.append({"point_id": point["point_id"], "passed": bool(ok), "depth_error_m": zerror, "backprojection_error_m": xyzerror})
    checks["all_points"] = len(details) == 20 and all(p["passed"] for p in details)
    return {"passed": all(checks.values()), "checks": checks, "points": details,
            "max_depth_error_m": max(p["depth_error_m"] for p in details), "max_backprojection_error_m": max(p["backprojection_error_m"] for p in details),
            "sampling_note": "Nearest containing raster pixel; lift using continuous annotation UV. This is not a per-pixel interpolated depth identity."}


def generate(root):
    root = root.resolve()
    if b.AI_ROOT.resolve() not in root.parents or not b.read_json(root / "preflight_report.json")["passed"]:
        raise ValueError("Need a passed, project-local preflight")
    if b.read_json(root / "source_hashes.json") != source_hashes():
        raise ValueError("Inputs changed since preflight")
    cfg = b.read_json(root / "dataset_config_v1.json")
    atlas = b.read_json(root / ATLAS.name)
    index = b.read_json(root / "dataset_index.json")
    if b.sha256(root / ATLAS.name) != cfg["atlas_sha256"] or cfg != b.read_json(CONFIG):
        raise ValueError("Preflight Atlas/config copy changed")
    for entry in index:
        if b.sha256(root / entry["snapshot"]) != entry["snapshot_sha256"] or b.sha256(root / entry["profile"]) != entry["profile_sha256"]:
            raise ValueError("Preflight snapshot/profile changed: " + entry["case"])
    results, previews = [], []
    try:
        for i, entry in enumerate(index):
            sid = entry["sample_id"]
            sample = root / "samples" / sid
            snapshot = root / entry["snapshot"]
            bj(b.EXPORT, snapshot, ["--fixture", root / ATLAS.name, "--output", sample, "--result", root / "qc_reports" / f"{sid}_export.json", "--width", 1280, "--height", 1024], "ACU_EXPORT_PRONE_SAMPLE=PASS")
            b.make_overlay(sample)
            independent = root / "qc_reports" / f"{sid}_independent.json"
            command = [str(b.PYTHON), str(b.VERIFY_SAMPLE), "--sample", str(sample), "--scene-blend", str(snapshot), "--blender-exe", str(b.BLENDER), "--protected-manifest", str(b.PROTECTED), "--require-rgbd", "--output", str(independent)]
            # One independently reopened/re-exported representative per Shape.
            if i in (0, 17, 28):
                replay = root / "preflight" / f"replay_{sid}"
                bj(b.EXPORT, snapshot, ["--fixture", root / ATLAS.name, "--output", replay, "--result", root / "qc_reports" / f"{sid}_replay.json", "--width", 1280, "--height", 1024], "ACU_EXPORT_PRONE_SAMPLE=PASS")
                command += ["--compare-sample", str(replay)]
            b.run(command, env=b.environment())
            edge_path = root / "qc_reports" / f"{sid}_silhouette_edges.json"
            bj(EDGES, snapshot, [sample, edge_path], None)
            edges = b.read_json(edge_path)
            strict = strict_qc(sample, atlas, b.read_json(root / entry["profile"]), cfg)
            strict["independent_passed"] = b.read_json(independent)["passed"]
            strict["silhouette_edges"] = {k:v for k,v in edges.items() if k != "mismatches"}
            strict["passed"] = strict["passed"] and strict["independent_passed"] and edges["pixel_count"] > 0 and edges["mismatch_count"] == 0
            b.write_json(root / "qc_reports" / f"{sid}_strict.json", strict)
            results.append({"sample_id": sid, "case": entry["case"], "passed": strict["passed"], "max_depth_error_m": strict["max_depth_error_m"], "max_backprojection_error_m": strict["max_backprojection_error_m"]})
            previews.append((f"{sid} {entry['case']}", sample / "overlay.png"))
            b.write_json(root / "batch_progress.json", results)
            print(f"SAMPLE {i+1}/30 {entry['case']}: {'PASS' if strict['passed'] else 'FAIL'} depth={strict['max_depth_error_m']*1000:.3f}mm xyz={strict['max_backprojection_error_m']*1000:.3f}mm", flush=True)
        passed = len(results) == 30 and all(r["passed"] for r in results) and b.read_json(root / "source_hashes.json") == source_hashes()
        report = {"schema": "skel-back20-qc30-v1", "automatic_passed": passed, "medical_truth": False,
                  "sample_count": len(results), "pass_count": sum(r["passed"] for r in results), "fail_count": sum(not r["passed"] for r in results),
                  "max_depth_error_m": max(r["max_depth_error_m"] for r in results), "max_backprojection_error_m": max(r["max_backprojection_error_m"] for r in results),
                  "representative_exact_replays": [index[i]["sample_id"] for i in (0,17,28)], "visual_review": "PENDING", "samples": results}
        b.write_json(root / "dataset_qc_report.json", report)
        montage(previews, root / "overlay_montage_30.png")
        for si in range(3):
            montage(previews[si*10:(si+1)*10], root / f"overlay_montage_S{si}.png")
        b.manifest(root)
        print(json.dumps({"automatic_passed": passed, "root": str(root), "visual_review": "PENDING"}, ensure_ascii=False), flush=True)
    except Exception as exc:
        b.write_json(root / "FAILED_DO_NOT_DELIVER.json", {"passed": False, "error": str(exc), "completed_samples": len(results)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-from", type=Path)
    args = parser.parse_args()
    generate(args.generate_from) if args.generate_from else preflight()
