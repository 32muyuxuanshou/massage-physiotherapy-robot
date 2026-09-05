from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image


CONTRACT_FILES = (
    "pilot_sampling_contract_v1.json",
    "pilot_visibility_loss_contract_v1.json",
    "pilot_appearance_contract_v1.json",
    "pilot_dataset_schema_v1.json",
    "evaluation_splits_v1.json",
    "pilot_plan_v1.json",
    "source_artifacts_v1.json",
    "verification.json",
)
GEOMETRY_FILES = ("labels.json", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    failures = []
    rows = [line for line in target.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    for line in rows:
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected.lower():
            failures.append(relative)
    return {"passed": not failures, "entries": len(rows), "failures": failures, "manifest_sha256": sha256(target)}


def build_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    rows = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != target
    ]
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(target)}


def apply_appearance(rgb_path: Path, skin_mask_path: Path, params: dict, output: Path) -> None:
    with Image.open(rgb_path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    with Image.open(skin_mask_path) as image:
        skin = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    skin = np.clip(skin, 0.0, 1.0)[..., None]
    height, width = rgb.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    nx = (xx + 0.5) / width * 2.0 - 1.0
    ny = (yy + 0.5) / height * 2.0 - 1.0
    angle = math.radians(float(params["image_space_gradient_angle_degrees"]))
    gradient = 1.0 + float(params["image_space_gradient_amplitude"]) * (nx * math.cos(angle) + ny * math.sin(angle))
    gradient = np.clip(gradient, 0.75, 1.25)[..., None]
    skin_gain = np.asarray(params["skin_rgb_gain"], dtype=np.float32).reshape(1, 1, 3)
    non_skin_gain = np.asarray(params["non_skin_rgb_gain"], dtype=np.float32).reshape(1, 1, 3)
    gain = skin * skin_gain + (1.0 - skin) * non_skin_gain
    adjusted = np.clip(rgb * gain * gradient * float(params["global_exposure"]), 0.0, 1.0)
    adjusted = np.power(adjusted, 1.0 / float(params["gamma"]))
    encoded = np.asarray(np.clip(np.rint(adjusted * 255.0), 0, 255), dtype=np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(encoded, mode="RGB").save(output, format="PNG", compress_level=6)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze = args.freeze.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    freeze_manifest = verify_manifest(freeze)
    freeze_verification = read_json(freeze / "verification.json")
    if not freeze_manifest["passed"] or not freeze_verification["passed"]:
        raise RuntimeError("Pilot Freeze input is not valid")
    if (output / "dataset_manifest.json").exists():
        raise RuntimeError("Output already contains a dataset manifest; use a new immutable output directory")

    contracts = output / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    for name in CONTRACT_FILES:
        shutil.copy2(freeze / name, contracts / name)
    plan = read_json(freeze / "pilot_plan_v1.json")
    sources = read_json(freeze / "source_artifacts_v1.json")
    source_by_id = {item["base_geometry_id"]: item for item in sources["base_sources"]}

    all_rows = [("main", row) for row in plan["main_samples"]] + [("challenge", row) for row in plan["challenge_samples"]]
    unique_bases = sorted({row["base_geometry_id"] for _, row in all_rows})
    base_rows = []
    geometry_copy_checks = []
    for index, base_id in enumerate(unique_bases, start=1):
        source = source_by_id[base_id]
        target = output / "base_geometry" / base_id
        target.mkdir(parents=True, exist_ok=True)
        copied = {}
        for name in GEOMETRY_FILES:
            source_info = source["files"][name]
            source_path = Path(source_info["path"])
            if sha256(source_path) != source_info["sha256"]:
                raise RuntimeError(f"Frozen source changed: {source_path}")
            target_path = target / name
            shutil.copy2(source_path, target_path)
            copied_hash = sha256(target_path)
            geometry_copy_checks.append(copied_hash == source_info["sha256"])
            copied[name] = {
                "relative_path": target_path.relative_to(output).as_posix(),
                "sha256": copied_hash,
                "bytes": target_path.stat().st_size,
                "source_sha256": source_info["sha256"],
            }
        base_rows.append({
            "base_geometry_id": base_id,
            "case_id": source["case_id"],
            "camera_id": source["camera_id"],
            "files": copied,
            "visibility_counts": source["visibility_counts"],
        })
        print(f"BASE {index}/{len(unique_bases)} {base_id}", flush=True)

    built_rows = {"main": [], "challenge": []}
    rgb_hashes = []
    for index, (partition, row) in enumerate(all_rows, start=1):
        source = source_by_id[row["base_geometry_id"]]
        rgb_source = Path(source["files"]["rgb.png"]["path"])
        if sha256(rgb_source) != source["files"]["rgb.png"]["sha256"]:
            raise RuntimeError(f"Frozen RGB source changed: {rgb_source}")
        subdir = "rgb" if partition == "main" else "challenge_rgb"
        rgb_target = output / subdir / f"{row['sample_id']}.png"
        skin_target = output / "base_geometry" / row["base_geometry_id"] / "skin_mask.png"
        apply_appearance(rgb_source, skin_target, row["appearance"], rgb_target)
        rgb_hash = sha256(rgb_target)
        rgb_hashes.append(rgb_hash)
        built = dict(row)
        built.update({
            "partition": partition,
            "rgb": {
                "relative_path": rgb_target.relative_to(output).as_posix(),
                "sha256": rgb_hash,
                "bytes": rgb_target.stat().st_size,
                "frozen_parent_rgb_sha256": source["files"]["rgb.png"]["sha256"],
            },
            "geometry_relative_directory": (Path("base_geometry") / row["base_geometry_id"]).as_posix(),
        })
        built_rows[partition].append(built)
        if index % 25 == 0 or index == len(all_rows):
            print(f"RGB {index}/{len(all_rows)}", flush=True)

    counts = Counter(row["camera_id"] for row in built_rows["main"])
    checks = {
        "freeze_manifest_passed": freeze_manifest["passed"],
        "freeze_verification_passed": freeze_verification["passed"],
        "base_geometry_count_71": len(base_rows) == 71,
        "geometry_copies_match_sources": all(geometry_copy_checks),
        "main_count_360": len(built_rows["main"]) == 360,
        "challenge_count_12": len(built_rows["challenge"]) == 12,
        "main_camera_quotas_exact": counts == Counter({
            "NORMAL_MAIN": 144,
            "C1_MILD_OBLIQUE": 108,
            "C2_EDGE_CROP": 54,
            "C3_EXTERNAL_OCCLUDER": 54,
        }),
        "c4_not_in_main": all(row["camera_id"] != "C4_SELF_OCCLUSION_STRESS" for row in built_rows["main"]),
        "all_generated_rgb_unique": len(set(rgb_hashes)) == len(rgb_hashes),
    }
    write_json(output / "dataset_manifest.json", {
        "schema": "engineering-pilot-dataset-manifest-v1",
        "medical_truth": False,
        "dataset_version": output.name,
        "freeze_root": str(freeze),
        "freeze_manifest_sha256": freeze_manifest["manifest_sha256"],
        "main_sample_count": len(built_rows["main"]),
        "challenge_sample_count": len(built_rows["challenge"]),
        "point_count": 20,
        "base_geometry_count": len(base_rows),
        "main_samples": built_rows["main"],
        "challenge_samples": built_rows["challenge"],
        "base_geometry": base_rows,
        "training_input_contract": {
            "allowed": ["rgb/<sample_id>.png"],
            "forbidden": ["overlay", "Depth", "Mask", "labels", "case/shape/pose/camera identifiers"],
            "target": "visible-point 2D heatmaps",
        },
        "claims": {"engineering_dataset_built": all(checks.values()), "generalization": False, "medical_accuracy": False},
    })
    write_json(output / "build_verification.json", {
        "schema": "engineering-pilot-build-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "rgb_sha_count": len(rgb_hashes),
        "unique_rgb_sha_count": len(set(rgb_hashes)),
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
    })
    result = build_manifest(output)
    print(json.dumps({"PILOT_BUILD": "PASS" if all(checks.values()) else "FAIL", **result}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
