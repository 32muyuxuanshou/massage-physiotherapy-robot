#!/usr/bin/env python3
"""Generate a small, explicit native-SKEL shoulder-axis probe set."""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime
from pathlib import Path


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
SKEL_ROOT = AI_ROOT / "模型资源" / "SKEL"
SKEL_PYTHON = SKEL_ROOT / ".venv" / "Scripts" / "python.exe"
SKEL_BRIDGE = SKEL_ROOT / "skel_blender_bridge.py"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
PREPARE = AI_ROOT / "标注工具" / "blender_mcp" / "workstreams" / "prone_rgbd" / "prepare_prone_scene.py"
RENDER = Path(__file__).resolve().parent / "render_preview.py"
OUTPUT_ROOT = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "natural_prone_pose"

FIELDS = {
    "head_twist": 25,
    "shoulder_r_x": 29,
    "shoulder_r_y": 30,
    "shoulder_r_z": 31,
    "elbow_flexion_r": 32,
    "shoulder_l_x": 39,
    "shoulder_l_y": 40,
    "shoulder_l_z": 41,
    "elbow_flexion_l": 42,
}
CANDIDATES = {
    "X60": {"shoulder_r_x": 60.0, "shoulder_l_x": -60.0},
    "Y60": {"shoulder_r_y": 60.0, "shoulder_l_y": -60.0},
    "Z60": {"shoulder_r_z": 60.0, "shoulder_l_z": -60.0},
    "X80_E25": {"shoulder_r_x": 80.0, "shoulder_l_x": -80.0, "elbow_flexion_r": 25.0, "elbow_flexion_l": 25.0},
}


def run(command: list[str], *, cwd=None, env=None, sentinel=None) -> None:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(f"failed: {command}\n{combined[-8000:]}")


def main() -> None:
    output = OUTPUT_ROOT / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.update({"BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"), "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    for name, values in CANDIDATES.items():
        candidate = output / name
        native = candidate / "native"
        native.mkdir(parents=True)
        pose = [0.0] * 46
        for field, value in values.items():
            pose[FIELDS[field]] = math.radians(value)
        profile = {
            "schema": "skel-native-prone-pose-candidate-v1",
            "candidate": name,
            "medical_truth": False,
            "betas": [0.0] * 10,
            "pose_degrees": values,
            "pose_vector_degrees": [math.degrees(value) for value in pose],
        }
        profile_path = candidate / "pose_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        parameters = {"betas": [0.0] * 10, "pose": pose, "trans": [0.0, 0.0, 0.0]}
        parameters_path = candidate / "parameters.json"
        parameters_path.write_text(json.dumps(parameters, indent=2) + "\n", encoding="utf-8")
        run([str(SKEL_PYTHON), str(SKEL_BRIDGE), "--gender", "female", "--parameters", str(parameters_path), "--output", str(native)], cwd=SKEL_ROOT)
        snapshot = candidate / "preview_scene.blend"
        run([str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--", "--snapshot", str(snapshot), "--result", str(candidate / "prepare.json"), "--native-pose-dir", str(native), "--pose-profile", str(profile_path), "--width", "640", "--height", "512"], env=environment, sentinel="ACU_PREPARE_PRONE_SCENE=PASS")
        run([str(BLENDER), "--background", str(snapshot), "--python", str(RENDER), "--", str(candidate / "preview.png")], env=environment, sentinel="ACU_NATURAL_PRONE_PREVIEW=PASS")
    print(json.dumps({"passed": True, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
