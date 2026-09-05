#!/usr/bin/env python3
"""Probe shoulder long-axis rotation after lowering the arms.

The rigid prone transform, camera, and bed remain frozen.  This sweep exists to
find a native SKEL arm pose whose hands do not pass through the fixed bed.
"""

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
PRONE_WS = AI_ROOT / "标注工具" / "blender_mcp" / "workstreams" / "prone_rgbd"
WS = Path(__file__).resolve().parent
PREPARE = PRONE_WS / "prepare_prone_scene.py"
RENDER = WS / "render_preview.py"
CONTRACT = WS / "fixed_scene_contract.json"
OUTPUT_ROOT = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "natural_prone_pose"

INDEX = {
    "head_twist": 25,
    "shoulder_r_x": 29,
    "shoulder_r_y": 30,
    "elbow_flexion_r": 32,
    "shoulder_l_x": 39,
    "shoulder_l_y": 40,
    "elbow_flexion_l": 42,
}
BASE = {
    "head_twist": 18.0,
    "shoulder_r_x": 80.0,
    "elbow_flexion_r": 25.0,
    "shoulder_l_x": -80.0,
    "elbow_flexion_l": 25.0,
}
CANDIDATES = {
    f"YOPP_P{int(angle)}": {**BASE, "shoulder_r_y": angle, "shoulder_l_y": -angle}
    for angle in (18.0, 19.0, 20.0, 21.0)
}


def run(command: list[str], *, cwd=None, env=None, sentinel=None) -> None:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(combined[-8000:])


def main() -> None:
    output = OUTPUT_ROOT / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_shoulder_twist_sweep")
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(
        {
            "BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"),
            "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    summary = {}
    for name, values in CANDIDATES.items():
        directory = output / name
        native = directory / "native"
        native.mkdir(parents=True)
        pose = [0.0] * 46
        for field, degrees in values.items():
            pose[INDEX[field]] = math.radians(degrees)
        profile = {
            "schema": "skel-native-prone-shoulder-twist-candidate-v1",
            "candidate": name,
            "medical_truth": False,
            "betas": [0.0] * 10,
            "pose_degrees": values,
            "pose_vector_degrees": [math.degrees(value) for value in pose],
        }
        profile_path = directory / "pose_profile.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        parameters_path = directory / "parameters.json"
        parameters_path.write_text(
            json.dumps({"betas": [0.0] * 10, "pose": pose, "trans": [0.0, 0.0, 0.0]}, indent=2) + "\n",
            encoding="utf-8",
        )
        run(
            [str(SKEL_PYTHON), str(SKEL_BRIDGE), "--gender", "female", "--parameters", str(parameters_path), "--output", str(native)],
            cwd=SKEL_ROOT,
        )
        snapshot = directory / "preview_scene.blend"
        prepare_result = directory / "prepare.json"
        run(
            [
                str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--",
                "--snapshot", str(snapshot), "--result", str(prepare_result),
                "--native-pose-dir", str(native), "--pose-profile", str(profile_path),
                "--fixed-scene-contract", str(CONTRACT), "--width", "640", "--height", "512",
            ],
            env=env,
            sentinel="ACU_PREPARE_PRONE_SCENE=PASS",
        )
        run(
            [str(BLENDER), "--background", str(snapshot), "--python", str(RENDER), "--", str(directory / "preview.png")],
            env=env,
            sentinel="ACU_NATURAL_PRONE_PREVIEW=PASS",
        )
        prepared = json.loads(prepare_result.read_text(encoding="utf-8-sig"))
        summary[name] = {"body_bounds_world_m": prepared["body_bounds_world_m"], "pose": values}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "output": str(output), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
