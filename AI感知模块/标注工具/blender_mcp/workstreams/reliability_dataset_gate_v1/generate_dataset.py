from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
CAMERA_WS = HERE.parent / "camera_visibility_diversity_v1"
DECODER_WS = HERE.parent / "decoder_contract_v1"
sys.path.insert(0, str(CAMERA_WS))
import run_camera_visibility_diversity as camera_gate  # noqa: E402
sys.path.insert(0, str(DECODER_WS))
import generate_decoder_samples as decoder_gen  # noqa: E402

cross = camera_gate.cross
APPLY = CAMERA_WS / "apply_camera_scenario.py"
SEVERITY = HERE.parent / "truncation_gate_v2" / "measure_truncation_severity.py"
PARTITIONS = ("RELIABILITY_TRAIN", "CALIBRATION", "UNTOUCHED_TEST")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_freeze(root: Path) -> dict:
    receipt = read(root / "partition_freeze_receipt.json")
    changed = []
    for name, item in receipt["protected_inputs"].items():
        path = Path(item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            changed.append(name)
    checks = {
        "freeze_receipt_passed": receipt["passed"],
        "protected_inputs_unchanged": not changed,
        "training_still_not_authorized": receipt["training_authorized"] is False,
    }
    return {"passed": all(checks.values()), "checks": checks, "changed": changed}


def expected_scenario(scenario: dict) -> dict:
    scenario = dict(scenario)
    kind = scenario["kind"]
    if kind == "EXTERNAL_OCCLUSION":
        scenario["expect"] = {"minimum_visible": 8, "minimum_external_occluded": 2}
    elif kind == "TRUNCATION":
        minimum = 2 if "MODERATE" in scenario["camera_id"] else 1
        scenario["expect"] = {"minimum_visible": 2, "minimum_out_of_frame": minimum}
    else:
        scenario["expect"] = {"minimum_visible": 18}
    return scenario


def source_probe(root: Path, case_id: str) -> Path:
    for phase in ("geometry_primary", "geometry_reserve"):
        path = root / phase / "probes" / f"{case_id}.json"
        if path.is_file():
            return path
    raise FileNotFoundError(case_id)


def generate_partition(root: Path, partition: str) -> None:
    freeze = verify_freeze(root)
    if not freeze["passed"]:
        raise RuntimeError(f"Partition freeze verification failed: {freeze}")
    selection = read(root / "qualified_body_selection.json")
    cells = [row for row in selection["selected"] if row["partition"] == partition]
    design = read(root / "camera_design_v1.json")
    scenarios = [expected_scenario(item) for item in design["scenarios"]]
    config_path = root / "frozen_camera_scenarios.json"
    if not config_path.exists():
        write(config_path, {"schema": "reliability-dataset-camera-runtime-v1", "scenarios": design["scenarios"]})
    seed = int(design["partition_appearance_seeds"][partition])
    phase_root = root / "dataset" / partition
    rows = []
    with tempfile.TemporaryDirectory(prefix=f"acu_reliability_dataset_{partition.lower()}_") as temp_name:
        temporary = Path(temp_name)
        for body_index, cell in enumerate(cells, 1):
            base = camera_gate.build_snapshot(root, cell, temporary / cell["case_id"])
            local_mesh_hash = None
            for scenario in scenarios:
                sample_id = f"{cell['case_id']}__{scenario['camera_id']}"
                sample = phase_root / "samples" / sample_id
                snapshot = temporary / sample_id / f"{sample_id}.blend"
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(base, snapshot)
                cross.shared.bj(
                    snapshot,
                    APPLY,
                    [
                        "--config", config_path,
                        "--camera-id", scenario["camera_id"],
                        "--result", temporary / sample_id / "camera.json",
                        "--save", snapshot,
                    ],
                    "ACU_APPLY_CAMERA_SCENARIO=PASS",
                )
                severity_path = phase_root / "severity" / f"{sample_id}.json"
                cross.shared.bj(
                    snapshot,
                    SEVERITY,
                    [
                        "--mesh-name", "SKEL-skin-female",
                        "--width", 1280,
                        "--height", 1024,
                        "--output", severity_path,
                    ],
                    "ACU_TRUNCATION_SEVERITY=PASS",
                )
                profile_path = root / "profiles" / f"{cell['case_id']}.json"
                native = temporary / cell["case_id"] / "native" / "parameters.json"
                probe_path = phase_root / "probes" / f"{sample_id}.json"
                cross.shared.bj(
                    snapshot,
                    cross.SHAPE_PROBE,
                    [
                        "--atlas", camera_gate.RECON_ROOT / "source_atlas_v5.json",
                        "--contract", root / "body_measurement_contract_v2.json",
                        "--profile", profile_path,
                        "--native-parameters", native,
                        "--core-parent", cross.shared.CORE_PARENT,
                        "--output", probe_path,
                        "--width", 1280,
                        "--height", 1024,
                    ],
                    "ACU_SHAPE_COMBINATION_PROBE=PASS",
                )
                required = ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png", "labels.json")
                if not all((sample / name).is_file() for name in required):
                    if sample.exists():
                        sample.rename(sample.with_name(sample.name + "_incomplete_" + datetime.now().strftime("%H%M%S")))
                    cross.shared.bj(
                        snapshot,
                        cross.shared.EXPORT,
                        [
                            "--fixture", root / "engineering_fixture_manual20.json",
                            "--output", sample,
                            "--result", phase_root / "export" / f"{sample_id}.json",
                            "--width", 1280,
                            "--height", 1024,
                        ],
                        "ACU_EXPORT_PRONE_SAMPLE=PASS",
                    )
                probe = read(probe_path)
                cross.shared.overlay_from_probe(sample / "rgb.png", probe, sample / "overlay.png")
                appearance = decoder_gen.appearance(seed, sample_id)
                decoder_gen.apply_appearance(sample / "rgb.png", sample / "skin_mask.png", appearance, sample / "rgb_model.png")
                profile = read(profile_path)
                generic_qc = cross.shared.strict_sample_qc(
                    sample,
                    read(root / "engineering_fixture_manual20.json"),
                    [float(value) for value in profile["betas"]],
                )
                labels = read(sample / "labels.json")
                pose_ok = labels["scene"]["native_pose_parameters_degrees"] == profile["pose_degrees"]
                mesh_hash = probe["model"]["evaluated_local_vertices_float32_sha256"]
                local_mesh_hash = local_mesh_hash or mesh_hash
                replay = camera_gate.geometry_replay(read(source_probe(root, cell["case_id"])), probe)
                camera_qc = camera_gate.scenario_qc(sample, scenario)
                checks = {
                    "sample_qc": generic_qc["passed"],
                    "pose_recorded": pose_ok,
                    "same_geometry_across_cameras": mesh_hash == local_mesh_hash,
                    "geometry_replay": replay["passed"],
                    "camera_qc": camera_qc["passed"],
                    "model_rgb_distinct_from_raw": sha(sample / "rgb_model.png") != sha(sample / "rgb.png"),
                }
                row = {
                    "sample_id": sample_id,
                    "partition": partition,
                    "case_id": cell["case_id"],
                    "camera_id": scenario["camera_id"],
                    "camera_kind": scenario["kind"],
                    "passed": all(checks.values()),
                    "checks": checks,
                    "reason_counts": camera_qc["reason_counts"],
                    "external_details": camera_qc["external_details"],
                    "severity": read(severity_path),
                    "appearance": appearance,
                    "sample": str(sample),
                    "hashes": {
                        name: sha(sample / name)
                        for name in (
                            "rgb.png",
                            "rgb_model.png",
                            "scene_depth_z.npy",
                            "depth_valid_mask.png",
                            "skin_mask.png",
                            "labels.json",
                        )
                    },
                }
                rows.append(row)
                print(
                    partition,
                    len(rows),
                    "/",
                    len(cells) * len(scenarios),
                    sample_id,
                    "PASS" if row["passed"] else "FAIL",
                    flush=True,
                )
    report = {
        "schema": "reliability-dataset-partition-generation-v1",
        "medical_truth": False,
        "partition": partition,
        "passed": len(rows) == len(cells) * len(scenarios) and all(row["passed"] for row in rows),
        "body_count": len(cells),
        "camera_count": len(scenarios),
        "sample_count": len(rows),
        "appearance_seed": seed,
        "freeze_check": freeze,
        "samples": rows,
    }
    write(root / f"{partition.lower()}_generation_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("partition", choices=PARTITIONS)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    generate_partition(args.root.resolve(), args.partition)


if __name__ == "__main__":
    main()
