#!/usr/bin/env python3
"""Run an isolated native-SKEL A/B/C/D/R surface-binding regression.

This orchestrator never writes to the canonical Blend, the formal Atlas, the
formal add-ons, or the release ZIP.  Native SKEL meshes are generated into a
timestamped workstream output and the canonical Blend is opened headlessly
without any save operation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
WORKSTREAM = AI_ROOT / "标注工具" / "blender_mcp" / "workstreams" / "skel_regression"
OUTPUT_ROOT = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "skel_regression"
CANONICAL_BLEND = (
    AI_ROOT
    / "模型资源"
    / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发"
    / "templates"
    / "SKEL"
    / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
)
FORMAL_ATLAS = (
    AI_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "workspace"
    / "导出结果"
    / "20260824_173250_skel_female_1_1"
    / "20260824_173250_skel_female_1_1_正式标注_最新.json"
)
FORMAL_ZIP = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
BLENDER = (
    AI_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "runtime"
    / "blender"
    / "blender.exe"
)
SKEL_ROOT = AI_ROOT / "模型资源" / "SKEL"
SKEL_PYTHON = SKEL_ROOT / ".venv" / "Scripts" / "python.exe"
SKEL_BRIDGE = SKEL_ROOT / "skel_blender_bridge.py"
BLENDER_SCRIPT = WORKSTREAM / "skel_native_regression_blender.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_checked(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def generate_skin(run_dir: Path, scenario: str, betas: list[float], pose_deg: list[float]) -> Path:
    scenario_dir = run_dir / "native_meshes" / scenario
    scenario_dir.mkdir(parents=True, exist_ok=True)
    parameters = {
        "betas": betas,
        "pose": [value * 3.141592653589793 / 180.0 for value in pose_deg],
        "trans": [0.0, 0.0, 0.0],
    }
    parameter_path = scenario_dir / "parameters.json"
    write_json(parameter_path, parameters)
    result = run_checked(
        [
            str(SKEL_PYTHON),
            str(SKEL_BRIDGE),
            "--gender",
            "female",
            "--parameters",
            str(parameter_path),
            "--output",
            str(scenario_dir),
            "--skin-only",
        ],
        cwd=SKEL_ROOT,
    )
    (scenario_dir / "bridge_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (scenario_dir / "bridge_stderr.txt").write_text(result.stderr, encoding="utf-8")
    skin = scenario_dir / "skin_female.obj"
    if not skin.exists():
        raise FileNotFoundError(skin)
    return skin


def build_fixture(run_dir: Path, hashes_before: dict[str, str]) -> Path:
    atlas = json.loads(FORMAL_ATLAS.read_text(encoding="utf-8-sig"))
    fixture = {
        "schema": "skel-native-abcd-regression-fixture-v1",
        "medical_status": "ENGINEERING_TEST_POINTS_ONLY_NOT_MEDICAL_GROUND_TRUTH",
        "source_atlas": str(FORMAL_ATLAS),
        "canonical_blend": str(CANONICAL_BLEND),
        "target": {
            "object_name": "SKEL-skin-female",
            "family": "SKEL",
            "gender": "female",
            "template_id": "skel-female-trunk-limb-v2.3",
            "vertex_count": 6890,
            "polygon_count": 13776,
            "topology_signature_sha256": "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
        },
        "protected_hashes_before": hashes_before,
        "points": [
            {
                "point_id": item["point_id"],
                "code": item["code"],
                "name_zh": item["name_zh"],
                "face_index": item["face_index"],
                "vertex_indices": item["vertex_indices"],
                "barycentric": item["barycentric"],
            }
            for item in atlas["annotations"]
        ],
        "scenario_contract": {
            "A": "native SKEL female, zero betas, zero pose",
            "B": "native SKEL female, small combined nonzero betas; not a sampling distribution",
            "C": "native SKEL female, zero betas, moderate nonzero biomechanical pose",
            "D": "A geometry plus an external occluder placed on the frozen first-point camera ray",
            "R": "independently regenerated zero betas and zero pose",
        },
    }
    fixture_path = run_dir / "projection_probe_fixture.json"
    write_json(fixture_path, fixture)
    return fixture_path


def main() -> int:
    for required in (CANONICAL_BLEND, FORMAL_ATLAS, FORMAL_ZIP, BLENDER, SKEL_PYTHON, SKEL_BRIDGE, BLENDER_SCRIPT):
        if not required.exists():
            raise FileNotFoundError(required)

    run_dir = OUTPUT_ROOT / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=False)
    protected = {
        "canonical_blend": CANONICAL_BLEND,
        "formal_atlas": FORMAL_ATLAS,
        "formal_release_zip": FORMAL_ZIP,
    }
    hashes_before = {name: sha256(path) for name, path in protected.items()}
    fixture_path = build_fixture(run_dir, hashes_before)

    zero_betas = [0.0] * 10
    zero_pose = [0.0] * 46
    b_betas = [0.60, 0.40, -0.35, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    c_pose = [0.0] * 46
    for index, value in {
        17: 7.0,   # lumbar_bending
        18: -8.0,  # lumbar_extension
        19: 8.0,   # lumbar_twist
        20: -5.0,  # thorax_bending
        21: 6.0,   # thorax_extension
        22: -7.0,  # thorax_twist
        26: 5.0,   # right scapula abduction
        29: 8.0,   # right shoulder x
        32: 25.0,  # right elbow flexion
        36: -5.0,  # left scapula abduction
        39: -8.0,  # left shoulder x
        42: 20.0,  # left elbow flexion
    }.items():
        c_pose[index] = value

    scenario_meshes = {
        "A": generate_skin(run_dir, "A", zero_betas, zero_pose),
        "B": generate_skin(run_dir, "B", b_betas, zero_pose),
        "C": generate_skin(run_dir, "C", zero_betas, c_pose),
        "R": generate_skin(run_dir, "R", zero_betas, zero_pose),
    }
    scenario_map_path = run_dir / "scenario_meshes.json"
    write_json(scenario_map_path, {key: str(value) for key, value in scenario_meshes.items()})

    blender_log = run_dir / "blender_stdout_stderr.txt"
    result = run_checked(
        [
            str(BLENDER),
            "--background",
            str(CANONICAL_BLEND),
            "--python",
            str(BLENDER_SCRIPT),
            "--",
            "--fixture",
            str(fixture_path),
            "--scenario-meshes",
            str(scenario_map_path),
            "--output",
            str(run_dir),
        ]
    )
    blender_log.write_text(result.stdout + "\n--- STDERR ---\n" + result.stderr, encoding="utf-8")

    report_path = run_dir / "skel_native_regression_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    hashes_after = {name: sha256(path) for name, path in protected.items()}
    protected_unchanged = hashes_before == hashes_after
    report["protected_files"] = {
        "before": hashes_before,
        "after": hashes_after,
        "unchanged": protected_unchanged,
    }
    report["checks"]["protected_files_unchanged"] = protected_unchanged
    report["source_script_hashes"] = {
        "orchestrator": sha256(Path(__file__).resolve()),
        "blender_regression": sha256(BLENDER_SCRIPT),
        "local_official_skel_bridge_read_only": sha256(SKEL_BRIDGE),
    }
    report["passed"] = bool(report.get("passed_without_post_hash_check", False) and protected_unchanged)
    report["status"] = "PASS" if report["passed"] else "FAIL"
    write_json(report_path, report)

    csv_path = run_dir / "skel_native_regression_points.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario", "point_id", "face_index", "vertex_indices", "x", "y", "z",
                "delta_from_A_m", "ray_hit", "ray_hit_object", "ray_hit_face",
                "ray_error_m", "visible_on_target",
            ]
        )
        for scenario, scenario_data in report["scenarios"].items():
            for point in scenario_data["points"]:
                writer.writerow(
                    [
                        scenario,
                        point["point_id"],
                        point["face_index"],
                        ",".join(str(value) for value in point["vertex_indices"]),
                        *point["xyz_world_m"],
                        point.get("delta_from_A_m", 0.0),
                        point["ray"]["hit"],
                        point["ray"]["hit_object"],
                        point["ray"]["hit_face_index"],
                        point["ray"]["point_error_m"],
                        point["ray"]["visible_on_target"],
                    ]
                )

    (run_dir / "STATUS.txt").write_text(report["status"] + "\n", encoding="ascii")
    readme = f"""# SKEL 原生 A/B/C/D/R 回归门

状态：**{report['status']}**

- 模型：最终女性 canonical SKEL v2.3（6,890 顶点 / 13,776 三角面）
- 点：来自已主动保存 Atlas 的 3 个冻结工程测试点，**不是医学穴位真值**
- B：SKEL 原生 10 维 beta 的一个小范围组合探针，不代表正式人群采样分布
- C：SKEL 原生 46 维 pose 的一个中等姿态探针，不代表俯卧治疗姿态
- D：在第一个冻结点的相机射线上加入外部遮挡盒
- R：独立重新生成零 beta / 零 pose，恢复误差见报告

主要指标：

- B 冻结点最大变化：{report['metrics']['max_B_point_change_from_A_m']:.9f} m
- C 冻结点最大变化：{report['metrics']['max_C_point_change_from_A_m']:.9f} m
- R 对 A 冻结点最大误差：{report['metrics']['max_R_point_error_from_A_m']:.9f} m
- A/R 全网格最大误差：{report['metrics']['max_R_vertex_error_from_A_m']:.9f} m
- canonical/A 全网格最大误差：{report['metrics']['max_A_vertex_error_from_canonical_m']:.9f} m

`A_overlay.png` 和 `D_external_occlusion_overlay.png` 仅供肉眼检查；权威数值位于
`skel_native_regression_report.json` 和 `skel_native_regression_points.csv`。

明确限制：本次 3 个冻结点均位于正面躯干，没有覆盖冻结的背面自遮挡点；拓扑稳定也部分来自当前更新方式只替换顶点坐标这一结构性保证。详见报告 `limitations`。
"""
    (run_dir / "README.md").write_text(readme, encoding="utf-8")

    inventory = []
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
        inventory.append({
            "path": str(path.relative_to(run_dir)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    write_json(run_dir / "file_inventory_sha256.json", inventory)
    print(f"SKEL_NATIVE_REGRESSION={report['status']}")
    print(f"OUTPUT={run_dir}")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
