from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
CAMERA_WS = HERE.parent / "camera_visibility_diversity_v1"
sys.path.insert(0, str(CAMERA_WS))
import run_camera_visibility_diversity as camera_gate  # noqa: E402

cross = camera_gate.cross
APPLY = CAMERA_WS / "apply_camera_scenario.py"
SEVERITY = HERE.parent / "truncation_gate_v2" / "measure_truncation_severity.py"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def appearance(seed: int, sample_id: str) -> dict:
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode()).digest()
    values = [value / 255.0 for value in digest]
    return {
        "global_exposure": 0.90 + 0.20 * values[0],
        "gamma": 0.92 + 0.16 * values[1],
        "skin_rgb_gain": [0.91 + 0.16 * values[i] for i in (2, 3, 4)],
        "non_skin_rgb_gain": [0.94 + 0.12 * values[i] for i in (5, 6, 7)],
        "image_space_gradient_angle_degrees": 360.0 * values[8],
        "image_space_gradient_amplitude": 0.02 + 0.06 * values[9],
    }


def apply_appearance(rgb_path: Path, skin_path: Path, params: dict, output: Path) -> None:
    with Image.open(rgb_path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    with Image.open(skin_path) as image:
        skin = np.asarray(image.convert("L"), dtype=np.float32)[..., None] / 255.0
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx + 0.5) / w * 2.0 - 1.0
    ny = (yy + 0.5) / h * 2.0 - 1.0
    angle = math.radians(float(params["image_space_gradient_angle_degrees"]))
    gradient = 1.0 + float(params["image_space_gradient_amplitude"]) * (
        nx * math.cos(angle) + ny * math.sin(angle)
    )
    gain = skin * np.asarray(params["skin_rgb_gain"], np.float32) + (
        1.0 - skin
    ) * np.asarray(params["non_skin_rgb_gain"], np.float32)
    adjusted = np.clip(
        rgb * gain * np.clip(gradient, 0.75, 1.25)[..., None]
        * float(params["global_exposure"]), 0.0, 1.0
    )
    adjusted = np.power(adjusted, 1.0 / float(params["gamma"]))
    Image.fromarray(np.rint(adjusted * 255.0).astype(np.uint8), "RGB").save(output)


def phase_config(root: Path, phase: str) -> tuple[Path, list[dict], int]:
    design = read(root / "camera_design_v1.json")
    key = "validation" if phase == "validation" else "untouched_test"
    scenarios = design[key]
    config_path = root / f"{phase}_camera_scenarios.json"
    write(config_path, {"schema": f"decoder-{phase}-camera-scenarios-v1", "scenarios": scenarios})
    seed = int(design["appearance"][f"{key}_seed"])
    return config_path, scenarios, seed


def reason_counts(labels: dict) -> dict:
    values = [point["visibility_reason"] for point in labels["points"]]
    return {key: values.count(key) for key in sorted(set(values))}


def generate(root: Path, phase: str) -> None:
    if phase == "untouched_test":
        receipt = root / "decoder_contract_freeze_receipt.json"
        if not receipt.is_file() or not read(receipt).get("passed"):
            raise RuntimeError("Untouched test is locked until a passed freeze receipt exists")
    selection = read(root / "qualified_new_geometry.json")
    cells = selection["validation" if phase == "validation" else "untouched_test"]
    config_path, scenarios, seed = phase_config(root, phase)
    phase_root = root / phase
    rows = []
    with tempfile.TemporaryDirectory(prefix=f"acu_decoder_{phase}_") as temp_name:
        temporary = Path(temp_name)
        for cell_index, cell in enumerate(cells, 1):
            base = camera_gate.build_snapshot(root, cell, temporary / cell["case_id"])
            local_mesh_hash = None
            for scenario in scenarios:
                sample_id = f"{cell['case_id']}__{scenario['camera_id']}"
                sample = phase_root / "samples" / sample_id
                snapshot = temporary / sample_id / f"{sample_id}.blend"
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(base, snapshot)
                cross.shared.bj(snapshot, APPLY, [
                    "--config", config_path, "--camera-id", scenario["camera_id"],
                    "--result", temporary / sample_id / "camera.json", "--save", snapshot,
                ], "ACU_APPLY_CAMERA_SCENARIO=PASS")
                severity_path = phase_root / "severity" / f"{sample_id}.json"
                cross.shared.bj(snapshot, SEVERITY, [
                    "--mesh-name", "SKEL-skin-female", "--width", 1280, "--height", 1024,
                    "--output", severity_path,
                ], "ACU_TRUNCATION_SEVERITY=PASS")
                profile_path = root / "profiles" / f"{cell['case_id']}.json"
                native = temporary / cell["case_id"] / "native" / "parameters.json"
                probe_path = phase_root / "probes" / f"{sample_id}.json"
                cross.shared.bj(snapshot, cross.SHAPE_PROBE, [
                    "--atlas", camera_gate.RECON_ROOT / "source_atlas_v5.json",
                    "--contract", root / "body_measurement_contract_v2.json",
                    "--profile", profile_path, "--native-parameters", native,
                    "--core-parent", cross.shared.CORE_PARENT, "--output", probe_path,
                    "--width", 1280, "--height", 1024,
                ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
                required = ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png", "labels.json")
                if not all((sample / name).is_file() for name in required):
                    if sample.exists():
                        archived = sample.with_name(sample.name + "_incomplete_" + datetime.now().strftime("%H%M%S"))
                        sample.rename(archived)
                    cross.shared.bj(snapshot, cross.shared.EXPORT, [
                        "--fixture", root / "engineering_fixture_manual20.json",
                        "--output", sample, "--result", phase_root / "export" / f"{sample_id}.json",
                        "--width", 1280, "--height", 1024,
                    ], "ACU_EXPORT_PRONE_SAMPLE=PASS")
                probe = read(probe_path)
                cross.shared.overlay_from_probe(sample / "rgb.png", probe, sample / "overlay.png")
                params = appearance(seed, sample_id)
                apply_appearance(sample / "rgb.png", sample / "skin_mask.png", params, sample / "rgb_model.png")
                profile = read(profile_path)
                qc = cross.shared.strict_sample_qc(
                    sample, read(root / "engineering_fixture_manual20.json"),
                    [float(value) for value in profile["betas"]]
                )
                labels = read(sample / "labels.json")
                pose_ok = labels["scene"]["native_pose_parameters_degrees"] == profile["pose_degrees"]
                mesh_hash = probe["model"]["evaluated_local_vertices_float32_sha256"]
                local_mesh_hash = local_mesh_hash or mesh_hash
                same_geometry = mesh_hash == local_mesh_hash
                checks = {"sample_qc": qc["passed"], "pose_recorded": pose_ok,
                          "same_geometry_across_cameras": same_geometry,
                          "model_rgb_distinct_from_raw": sha(sample / "rgb_model.png") != sha(sample / "rgb.png")}
                row = {
                    "sample_id": sample_id, "phase": phase, "case_id": cell["case_id"],
                    "camera_id": scenario["camera_id"], "camera_kind": scenario["kind"],
                    "direction": scenario.get("direction"), "passed": all(checks.values()),
                    "checks": checks, "reason_counts": reason_counts(labels),
                    "severity": read(severity_path), "appearance": params,
                    "sample": str(sample),
                    "hashes": {name: sha(sample / name) for name in (
                        "rgb.png", "rgb_model.png", "scene_depth_z.npy",
                        "depth_valid_mask.png", "skin_mask.png", "labels.json")},
                }
                rows.append(row)
                print(phase, len(rows), "/", len(cells) * len(scenarios), sample_id,
                      "PASS" if row["passed"] else "FAIL", flush=True)
    payload = {
        "schema": f"decoder-{phase}-sample-generation-v1", "medical_truth": False,
        "passed": len(rows) == len(cells) * len(scenarios) and all(r["passed"] for r in rows),
        "geometry_count": len(cells), "camera_count": len(scenarios), "sample_count": len(rows),
        "appearance_seed": seed, "samples": rows,
    }
    write(root / f"{phase}_sample_generation_report.json", payload)
    if not payload["passed"]:
        raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validation", "untouched_test"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    generate(args.root.resolve(), args.phase)


if __name__ == "__main__":
    main()
