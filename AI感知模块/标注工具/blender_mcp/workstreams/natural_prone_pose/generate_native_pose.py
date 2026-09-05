#!/usr/bin/env python3
"""Generate one full SKEL skin/skeleton/joint output from a frozen pose profile."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
SKEL_ROOT = AI_ROOT / "模型资源" / "SKEL"
SKEL_PYTHON = SKEL_ROOT / ".venv" / "Scripts" / "python.exe"
SKEL_BRIDGE = SKEL_ROOT / "skel_blender_bridge.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8-sig"))
    vector = [float(value) for value in profile["pose_vector_degrees"]]
    betas = [float(value) for value in profile.get("betas", [0.0] * 10)]
    if len(vector) != 46 or len(betas) != 10:
        raise ValueError("SKEL profile requires 46 pose values and 10 betas")
    args.output.mkdir(parents=True, exist_ok=False)
    parameters = {
        "betas": betas,
        "pose": [math.radians(value) for value in vector],
        "trans": [0.0, 0.0, 0.0],
    }
    parameter_path = args.output / "parameters.json"
    parameter_path.write_text(json.dumps(parameters, indent=2) + "\n", encoding="utf-8")
    result = subprocess.run(
        [str(SKEL_PYTHON), str(SKEL_BRIDGE), "--gender", "female", "--parameters", str(parameter_path), "--output", str(args.output)],
        cwd=str(SKEL_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    (args.output / "bridge_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (args.output / "bridge_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    required = [args.output / "skin_female.obj", args.output / "skeleton_female.obj", args.output / "joints_female.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    print(json.dumps({"passed": True, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
