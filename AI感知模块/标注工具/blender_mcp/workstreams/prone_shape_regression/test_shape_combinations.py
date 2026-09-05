#!/usr/bin/env python3
"""Test a small set of explicit multi-beta combinations in the fixed prone scene."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import run_shape_smoke as smoke


COMBINATIONS = {
    "LATENT_A": [0.40, 0.30, -0.30, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "LATENT_B": [-0.40, -0.15, 0.30, -0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "LATENT_C": [0.25, 0.40, 0.0, 0.0, 0.30, -0.30, 0.25, 0.0, 0.0, 0.0],
    "LATENT_D": [-0.25, 0.0, 0.25, 0.0, -0.30, 0.30, -0.25, 0.0, 0.0, 0.0],
}


def main() -> None:
    previous = smoke.AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / "2026-08-28_16-44-42_shape_smoke"
    baseline = smoke.read_json(previous / "cases" / "A_BASE" / "probe.json")
    fixture = smoke.read_json(smoke.FIXTURE)
    base = smoke.read_json(smoke.PROFILE_BASE)
    output = smoke.AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_shape_combinations")
    output.mkdir(parents=True, exist_ok=False)
    temp_root = smoke.AI_ROOT / "outputs" / "BlenderMCP" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp = temp_root / f"shape_combinations_{uuid.uuid4().hex}"
    temp.mkdir()
    results = []
    previews = []
    for name, betas in COMBINATIONS.items():
        case_dir = output / name
        case_dir.mkdir()
        profile = json.loads(json.dumps(base))
        profile.update({"schema": "skel-native-prone-safe-shape-candidate-v1", "profile_id": name, "medical_truth": False, "betas": betas, "shape_test": {"type": "explicit_multivariate_candidate"}})
        profile_path = case_dir / "profile.json"
        smoke.write_json(profile_path, profile)
        native = temp / f"native_{name}"
        smoke.run([str(smoke.PYTHON), str(smoke.GENERATE), "--profile", str(profile_path), "--output", str(native)])
        snapshot = temp / f"{name}.blend"
        prepare_result = case_dir / "prepare.json"
        smoke.run([str(smoke.BLENDER), "--background", str(smoke.CANONICAL), "--python", str(smoke.PREPARE), "--", "--snapshot", str(snapshot), "--result", str(prepare_result), "--native-pose-dir", str(native), "--pose-profile", str(profile_path), "--fixed-scene-contract", str(smoke.CONTRACT), "--width", "640", "--height", "512"], env=smoke.environment(), sentinel="ACU_PREPARE_PRONE_SCENE=PASS")
        probe_path = case_dir / "probe.json"
        smoke.run([str(smoke.BLENDER), "--background", str(snapshot), "--python", str(smoke.PROBE), "--", "--fixture", str(smoke.FIXTURE), "--output", str(probe_path), "--width", "1280", "--height", "1024"], env=smoke.environment(), sentinel="ACU_POSE_SNAPSHOT_PROBE=PASS")
        preview_path = case_dir / "preview.png"
        smoke.run([str(smoke.BLENDER), "--background", str(snapshot), "--python", str(smoke.RENDER), "--", str(preview_path)], env=smoke.environment(), sentinel="ACU_NATURAL_PRONE_PREVIEW=PASS")
        candidate = smoke.read_json(probe_path)
        analysed = smoke.analyse_case(name, baseline, candidate, fixture)
        # Multivariate candidates are frozen only when they do not enter the rigid bed at all.
        analysed["checks"]["no_bed_penetration"] = analysed["metrics"]["body_clearance_m"] >= 0.0
        analysed["passed_automatic_gate"] = all(analysed["checks"].values())
        results.append(analysed)
        previews.append((name, preview_path))
    passed = [item["case"] for item in results if item["passed_automatic_gate"]]
    report = {"schema": "skel-natural-prone-shape-combinations-v1", "medical_truth": False, "passed": len(passed) >= 2, "safe_candidates": passed, "cases": results, "limitations": ["Latent combinations have no clinical body-type names.", "Visual review is still required.", "No mattress or soft-tissue contact simulation."]}
    smoke.write_json(output / "shape_combination_report.json", report)
    smoke.make_montage(previews, output / "shape_combination_montage.png")
    smoke.manifest(output)
    print(json.dumps({"passed": report["passed"], "output": str(output), "safe_candidates": passed}, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 2)


if __name__ == "__main__":
    main()
