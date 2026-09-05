#!/usr/bin/env python3
"""Build the native-SKEL natural-prone A/P/R single-sample delivery."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TOOL_ROOT = Path(__file__).resolve().parent
AI_ROOT = TOOL_ROOT.parents[1]
WS = TOOL_ROOT / "workstreams" / "natural_prone_pose"
PRONE_WS = TOOL_ROOT / "workstreams" / "prone_rgbd"
VERIFY_WS = TOOL_ROOT / "workstreams" / "independent_verifier"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
FORMAL_ATLAS = WORKBENCH / "workspace" / "导出结果" / "20260824_173250_skel_female_1_1" / "20260824_173250_skel_female_1_1_正式标注_最新.json"
OFFICIAL_ZIP = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
USER_RESOURCES = WORKBENCH / "user_resources"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
FIXTURE = PRONE_WS / "prone_engineering_fixture.json"
PROFILE_P = WS / "natural_prone_pose_profile.json"
PROFILE_ZERO = WS / "zero_pose_profile.json"
SCENE_CONTRACT = WS / "fixed_scene_contract.json"
GENERATE = WS / "generate_native_pose.py"
PREPARE = PRONE_WS / "prepare_prone_scene.py"
EXPORT = PRONE_WS / "export_prone_sample.py"
PROBE = WS / "probe_pose_snapshot.py"
VERIFY_SAMPLE = VERIFY_WS / "verify_sample.py"
VERIFY_POSE = WS / "verify_pose_regression.py"
RENDER_PREVIEW = WS / "render_preview.py"
RENDER_SIDE_PREVIEW = WS / "render_side_preview.py"
PROTECTED = VERIFY_WS / "protected_assets.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], *, env=None, timeout=900, sentinel=None) -> str:
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(f"failed ({result.returncode}): {command}\n{combined[-12000:]}")
    return combined


def environment() -> dict[str, str]:
    value = os.environ.copy()
    value.update({"BLENDER_USER_RESOURCES": str(USER_RESOURCES), "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    return value


def generate(profile: Path, output: Path) -> str:
    return run([str(PYTHON), str(GENERATE), "--profile", str(profile), "--output", str(output)])


def prepare(native: Path, profile: Path, snapshot: Path, result: Path) -> str:
    return run([
        str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--",
        "--snapshot", str(snapshot), "--result", str(result), "--native-pose-dir", str(native),
        "--pose-profile", str(profile), "--fixed-scene-contract", str(SCENE_CONTRACT),
        "--width", "1280", "--height", "1024",
    ], env=environment(), sentinel="ACU_PREPARE_PRONE_SCENE=PASS")


def export(snapshot: Path, sample: Path, result: Path) -> str:
    return run([
        str(BLENDER), "--background", str(snapshot), "--python", str(EXPORT), "--",
        "--fixture", str(FIXTURE), "--output", str(sample), "--result", str(result), "--width", "1280", "--height", "1024",
    ], env=environment(), sentinel="ACU_EXPORT_PRONE_SAMPLE=PASS")


def probe(snapshot: Path, output: Path) -> str:
    return run([
        str(BLENDER), "--background", str(snapshot), "--python", str(PROBE), "--",
        "--fixture", str(FIXTURE), "--output", str(output), "--width", "1280", "--height", "1024",
    ], env=environment(), sentinel="ACU_POSE_SNAPSHOT_PROBE=PASS")


def render_preview(snapshot: Path, output: Path) -> str:
    return run([str(BLENDER), "--background", str(snapshot), "--python", str(RENDER_PREVIEW), "--", str(output)], env=environment(), sentinel="ACU_NATURAL_PRONE_PREVIEW=PASS")


def render_side_preview(snapshot: Path, output: Path) -> str:
    return run([str(BLENDER), "--background", str(snapshot), "--python", str(RENDER_SIDE_PREVIEW), "--", str(output)], env=environment(), sentinel="ACU_NATURAL_PRONE_SIDE_PREVIEW=PASS")


def make_overlay(sample: Path) -> None:
    sys.path.insert(0, str(TOOL_ROOT))
    from server import _overlay
    _overlay(sample / "rgb.png", sample / "labels.json", sample / "overlay.png")


def comparison(left_path: Path, right_path: Path, output: Path) -> None:
    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        left = left_image.convert("RGB")
        right = right_image.convert("RGB")
        if right.size != left.size:
            right = right.resize(left.size, Image.Resampling.LANCZOS)
        header = 46
        canvas = Image.new("RGB", (left.width * 2, left.height + header), "white")
        canvas.paste(left, (0, header))
        canvas.paste(right, (left.width, header))
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        draw.text((16, 15), "A: rigid prone / native zero pose", fill="black", font=font)
        draw.text((left.width + 16, 15), "P: native SKEL natural prone pose", fill="black", font=font)
        canvas.save(output)


def manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    required = [CANONICAL, FORMAL_ATLAS, OFFICIAL_ZIP, BLENDER, PYTHON, FIXTURE, PROFILE_P, PROFILE_ZERO, SCENE_CONTRACT, GENERATE, PREPARE, EXPORT, PROBE, VERIFY_SAMPLE, VERIFY_POSE, RENDER_PREVIEW, RENDER_SIDE_PREVIEW, PROTECTED]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    delivery = AI_ROOT / "outputs" / "交付文件" / timestamp
    delivery.mkdir(parents=True, exist_ok=False)
    temp_root = (AI_ROOT / "outputs" / "BlenderMCP" / "tmp").resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    temp = (temp_root / f"natural_prone_{uuid.uuid4().hex}").resolve()
    if temp_root not in temp.parents:
        raise RuntimeError("temp path escaped approved root")
    temp.mkdir()
    protected_paths = {"canonical_skel": CANONICAL, "formal_atlas": FORMAL_ATLAS, "official_zip": OFFICIAL_ZIP}
    before = {key: sha256(path) for key, path in protected_paths.items()}
    logs = {}
    success = False
    try:
        native = {"A": temp / "native_A", "P": temp / "native_P", "R": temp / "native_R"}
        logs["generate_A"] = generate(PROFILE_ZERO, native["A"])
        logs["generate_P"] = generate(PROFILE_P, native["P"])
        logs["generate_R"] = generate(PROFILE_ZERO, native["R"])

        snapshots = {"A": delivery / "A_zero_pose_snapshot.blend", "P": delivery / "P_natural_prone_snapshot.blend", "R": delivery / "R_restored_zero_pose_snapshot.blend"}
        prepare_results = {key: delivery / f"prepare_{key}.json" for key in snapshots}
        for key, profile in (("A", PROFILE_ZERO), ("P", PROFILE_P), ("R", PROFILE_ZERO)):
            logs[f"prepare_{key}"] = prepare(native[key], profile, snapshots[key], prepare_results[key])

        sample = delivery / "sample_natural_prone_000001"
        replay = temp / "replay_P"
        logs["export_P"] = export(snapshots["P"], sample, temp / "export_P.json")
        logs["replay_P"] = export(snapshots["P"], replay, temp / "replay_P.json")
        make_overlay(sample)

        independent = delivery / "independent_verification.json"
        logs["independent"] = run([
            str(PYTHON), str(VERIFY_SAMPLE), "--sample", str(sample), "--scene-blend", str(snapshots["P"]),
            "--blender-exe", str(BLENDER), "--protected-manifest", str(PROTECTED), "--compare-sample", str(replay),
            "--require-rgbd", "--output", str(independent),
        ], env=environment())

        probes = {key: delivery / f"probe_{key}.json" for key in snapshots}
        for key in snapshots:
            logs[f"probe_{key}"] = probe(snapshots[key], probes[key])
        pose_report = delivery / "pose_regression.json"
        logs["pose_verify"] = run([
            str(PYTHON), str(VERIFY_POSE), "--a", str(probes["A"]), "--p", str(probes["P"]), "--r", str(probes["R"]),
            "--fixture", str(FIXTURE), "--sample", str(sample), "--independent-report", str(independent), "--output", str(pose_report),
        ])

        logs["preview_A"] = render_preview(snapshots["A"], delivery / "A_rigid_prone_preview.png")
        logs["preview_P"] = render_preview(snapshots["P"], delivery / "P_natural_pose_preview.png")
        logs["side_preview_P"] = render_side_preview(snapshots["P"], delivery / "P_natural_pose_side_preview.png")
        comparison(delivery / "A_rigid_prone_preview.png", delivery / "P_natural_pose_preview.png", delivery / "pose_comparison.png")

        independent_payload = json.loads(independent.read_text(encoding="utf-8-sig"))
        pose_payload = json.loads(pose_report.read_text(encoding="utf-8-sig"))
        if not independent_payload.get("passed") or not pose_payload.get("passed"):
            raise AssertionError("verification failed")
        after = {key: sha256(path) for key, path in protected_paths.items()}
        if before != after:
            raise AssertionError("protected asset changed")

        for source in (PROFILE_P, PROFILE_ZERO, SCENE_CONTRACT, FIXTURE):
            shutil.copy2(source, delivery / source.name)
        labels = json.loads((sample / "labels.json").read_text(encoding="utf-8-sig"))
        summary = {
            "schema": "skel-native-natural-prone-delivery-v1",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "passed": True,
            "medical_truth": False,
            "profile": json.loads(PROFILE_P.read_text(encoding="utf-8-sig")),
            "visibility": {point["point_id"]: point["visibility_reason"] for point in labels["points"]},
            "independent_summary": independent_payload["summary"],
            "pose_regression_summary": pose_payload["summary"],
            "protected_assets_before": before,
            "protected_assets_after": after,
            "limitations": pose_payload["limitations"],
            "conclusion": "A/P/R native-SKEL pose propagation and the P RGB-D single sample passed independent replay; this does not validate medical acupoint propagation or batch production.",
        }
        write_json(delivery / "verification.json", summary)
        (delivery / "README.md").write_text(
            "# SKEL 原生自然俯卧 Pose 单样本\n\n"
            "结果：**PASS**。A 和 R 由官方 SKEL 桥接器分别独立生成零姿态；P 使用冻结的原生姿态：双肩 X 为 +80°/-80°、双肩 Y 为 +18°/-18°、双肘 25°、头部旋转 18°，其余关节和 10 维 Shape 为 0。\n\n"
            "P 样本包含对齐的 RGB、camera-Z Depth、Depth Valid Mask、Skin Mask、labels 和 overlay。固定的 6 个背部工程锚点仍可见，2 个前侧对照点仍不可见；A→P 表面和锚点发生变化，P→R 后完整网格、锚点 XYZ 和 UV 恢复。\n\n"
            "所有 ENG_* 都不是医学穴位。该姿态只是自然外观的工程姿态，尚未经过医生确认；没有枕头/面孔托、床垫形变、呼吸、软组织接触或自交求解。`.blend` 含授权模型，仅限内部研究，不得外发。\n",
            encoding="utf-8",
        )
        (delivery / "交付清单.md").write_text(
            "# 交付清单\n\n"
            "- `sample_natural_prone_000001/`：P 姿态 RGB-D/Mask/labels/overlay\n"
            "- `A_*.blend` / `P_*.blend` / `R_*.blend`：A/P/R 独立重放快照\n"
            "- `probe_A/P/R.json`：独立网格、锚点、相机和射线探针\n"
            "- `pose_regression.json`：原生 Pose 变化与恢复专项验收\n"
            "- `independent_verification.json`：P 样本逐像素 RGB-D 与精确重导出验收\n"
            "- `pose_comparison.png`：A/P 视觉对比\n"
            "- `P_natural_pose_side_preview.png`：床面间隙与手臂高度侧视检查\n"
            "- `*_profile.json` / `fixed_scene_contract.json` / `prone_engineering_fixture.json`：冻结输入合同\n"
            "- `verification.json` / `SHA256SUMS.txt`：汇总与全量哈希\n",
            encoding="utf-8",
        )
        manifest(delivery)
        success = True
        print(json.dumps({"passed": True, "delivery": str(delivery)}, ensure_ascii=False))
    except Exception:
        write_json(delivery / "FAILED_DO_NOT_DELIVER.json", {"passed": False, "notice": "Failed attempt; do not deliver.", "log_tails": {key: value[-4000:] for key, value in logs.items()}})
        raise
    finally:
        if success and temp.is_dir() and temp_root in temp.parents:
            shutil.rmtree(temp)


if __name__ == "__main__":
    main()
