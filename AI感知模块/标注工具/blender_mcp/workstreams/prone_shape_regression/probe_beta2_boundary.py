#!/usr/bin/env python3
"""Refine the fixed-bed clearance boundary for the second SKEL beta."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import run_shape_smoke as smoke


def main() -> None:
    output = smoke.AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_beta2_boundary")
    output.mkdir(parents=True, exist_ok=False)
    temp_root = smoke.AI_ROOT / "outputs" / "BlenderMCP" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp = temp_root / f"beta2_boundary_{uuid.uuid4().hex}"
    temp.mkdir()
    base = smoke.read_json(smoke.PROFILE_BASE)
    results = []
    for value in (-0.10, -0.20, -0.25, -0.30, -0.35, -0.40, -0.45):
        name = f"B02_{abs(value):.2f}".replace(".", "p")
        case_dir = output / name
        case_dir.mkdir()
        profile = smoke.make_profile(base, 1, value)
        profile_path = case_dir / "profile.json"
        smoke.write_json(profile_path, profile)
        native = temp / f"native_{name}"
        smoke.run([str(smoke.PYTHON), str(smoke.GENERATE), "--profile", str(profile_path), "--output", str(native)])
        snapshot = temp / f"{name}.blend"
        prepared_path = case_dir / "prepare.json"
        smoke.run([
            str(smoke.BLENDER), "--background", str(smoke.CANONICAL), "--python", str(smoke.PREPARE), "--",
            "--snapshot", str(snapshot), "--result", str(prepared_path), "--native-pose-dir", str(native),
            "--pose-profile", str(profile_path), "--fixed-scene-contract", str(smoke.CONTRACT), "--width", "640", "--height", "512",
        ], env=smoke.environment(), sentinel="ACU_PREPARE_PRONE_SCENE=PASS")
        prepared = smoke.read_json(prepared_path)
        clearance = float(prepared["body_bounds_world_m"]["min"][2])
        results.append({"beta2": value, "body_clearance_m": clearance, "passes_minus_5mm_gate": clearance >= -0.005})
    payload = {"schema": "skel-beta2-fixed-bed-boundary-v1", "medical_truth": False, "results": results}
    smoke.write_json(output / "beta2_boundary_report.json", payload)
    smoke.manifest(output)
    print(json.dumps({"passed": True, "output": str(output), "results": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
