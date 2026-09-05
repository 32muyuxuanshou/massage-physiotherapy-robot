from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_dataset as gen  # noqa: E402


def run(root: Path) -> None:
    freeze = gen.verify_freeze(root)
    if not freeze["passed"]:
        raise RuntimeError(freeze)
    design_path = HERE / "camera_reserve_design_v1.json"
    shutil.copy2(design_path, root / design_path.name)
    design = gen.read(design_path)
    replacement = design["replacement"]
    scenario = dict(replacement["scenario"])
    runtime_scenario = {**scenario, "expect": {"minimum_visible": 2, "minimum_out_of_frame": 1}}
    config_path = root / "camera_reserve_runtime.json"
    gen.write(config_path, {"schema": "reliability-camera-reserve-runtime-v1", "scenarios": [scenario]})
    selection = gen.read(root / "qualified_body_selection.json")
    cell = next(row for row in selection["selected"] if row["case_id"] == replacement["case_id"])
    partition = replacement["partition"]
    phase_root = root / "dataset" / partition
    with tempfile.TemporaryDirectory(prefix="acu_reliability_camera_reserve_") as temp_name:
        temporary = Path(temp_name)
        base = gen.camera_gate.build_snapshot(root, cell, temporary / cell["case_id"])
        sample_id = f"{cell['case_id']}__{scenario['camera_id']}"
        sample = phase_root / "samples" / sample_id
        snapshot = temporary / sample_id / f"{sample_id}.blend"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base, snapshot)
        gen.cross.shared.bj(
            snapshot,
            gen.APPLY,
            ["--config", config_path, "--camera-id", scenario["camera_id"], "--result", temporary / sample_id / "camera.json", "--save", snapshot],
            "ACU_APPLY_CAMERA_SCENARIO=PASS",
        )
        severity_path = phase_root / "severity" / f"{sample_id}.json"
        gen.cross.shared.bj(
            snapshot,
            gen.SEVERITY,
            ["--mesh-name", "SKEL-skin-female", "--width", 1280, "--height", 1024, "--output", severity_path],
            "ACU_TRUNCATION_SEVERITY=PASS",
        )
        profile_path = root / "profiles" / f"{cell['case_id']}.json"
        native = temporary / cell["case_id"] / "native" / "parameters.json"
        probe_path = phase_root / "probes" / f"{sample_id}.json"
        gen.cross.shared.bj(
            snapshot,
            gen.cross.SHAPE_PROBE,
            ["--atlas", gen.camera_gate.RECON_ROOT / "source_atlas_v5.json", "--contract", root / "body_measurement_contract_v2.json", "--profile", profile_path, "--native-parameters", native, "--core-parent", gen.cross.shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024],
            "ACU_SHAPE_COMBINATION_PROBE=PASS",
        )
        gen.cross.shared.bj(
            snapshot,
            gen.cross.shared.EXPORT,
            ["--fixture", root / "engineering_fixture_manual20.json", "--output", sample, "--result", phase_root / "export" / f"{sample_id}.json", "--width", 1280, "--height", 1024],
            "ACU_EXPORT_PRONE_SAMPLE=PASS",
        )
        probe = gen.read(probe_path)
        gen.cross.shared.overlay_from_probe(sample / "rgb.png", probe, sample / "overlay.png")
        appearance_seed = int(gen.read(root / "camera_design_v1.json")["partition_appearance_seeds"][partition])
        appearance = gen.decoder_gen.appearance(appearance_seed, sample_id)
        gen.decoder_gen.apply_appearance(sample / "rgb.png", sample / "skin_mask.png", appearance, sample / "rgb_model.png")
        profile = gen.read(profile_path)
        generic = gen.cross.shared.strict_sample_qc(sample, gen.read(root / "engineering_fixture_manual20.json"), [float(v) for v in profile["betas"]])
        replay = gen.camera_gate.geometry_replay(gen.read(gen.source_probe(root, cell["case_id"])), probe)
        camera_qc = gen.camera_gate.scenario_qc(sample, runtime_scenario)
        checks = {
            "generic_qc": generic["passed"],
            "geometry_replay": replay["passed"],
            "camera_qc": camera_qc["passed"],
            "at_least_one_target_out_of_frame": camera_qc["reason_counts"].get("OUT_OF_FRAME", 0) >= 1,
            "at_least_two_targets_visible": camera_qc["reason_counts"].get("VISIBLE", 0) >= 2,
            "no_locator_predictions_exist": not list(root.rglob("*prediction*")),
        }
        report = {
            "schema": "reliability-dataset-camera-reserve-result-v1",
            "passed": all(checks.values()),
            "checks": checks,
            "replaces_sample_id": replacement["replaces_sample_id"],
            "selected_sample_id": sample_id,
            "partition": partition,
            "case_id": cell["case_id"],
            "scenario": scenario,
            "camera_qc": camera_qc,
            "severity": gen.read(severity_path),
            "sample": str(sample),
            "hashes": {name: gen.sha(sample / name) for name in ("rgb.png", "rgb_model.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png", "labels.json")},
        }
        gen.write(root / "camera_reserve_result.json", report)
        print(json.dumps({"passed": report["passed"], "reason_counts": camera_qc["reason_counts"]}, ensure_ascii=False, indent=2))
        if not report["passed"]:
            raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    run(args.root.resolve())


if __name__ == "__main__":
    main()
