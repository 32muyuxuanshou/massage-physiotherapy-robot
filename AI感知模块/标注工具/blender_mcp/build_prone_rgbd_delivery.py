#!/usr/bin/env python3
"""Build and independently verify the first prone-back SKEL RGB-D sample."""

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


TOOL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_ROOT.parents[1]
WORKSTREAM = TOOL_ROOT / "workstreams" / "prone_rgbd"
VERIFIER_ROOT = TOOL_ROOT / "workstreams" / "independent_verifier"
WORKBENCH = PROJECT_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
CANONICAL = PROJECT_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
FORMAL_ATLAS = WORKBENCH / "workspace" / "导出结果" / "20260824_173250_skel_female_1_1" / "20260824_173250_skel_female_1_1_正式标注_最新.json"
OFFICIAL_ZIP = PROJECT_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
USER_RESOURCES = WORKBENCH / "user_resources"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
PROTECTED = VERIFIER_ROOT / "protected_assets.json"
FIXTURE = WORKSTREAM / "prone_engineering_fixture.json"
PREPARE = WORKSTREAM / "prepare_prone_scene.py"
EXPORT = WORKSTREAM / "export_prone_sample.py"
VERIFY = VERIFIER_ROOT / "verify_sample.py"
VERIFY_PRONE = WORKSTREAM / "verify_prone_contract.py"
CORE_SOURCE = PROJECT_ROOT / "标注工具" / "blender_addons" / "modules" / "training_export_core" / "render_buffers.py"
CORE_RUNTIME = USER_RESOURCES / "scripts" / "addons" / "modules" / "training_export_core" / "render_buffers.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(command: list[str], *, environment=None, timeout=900, sentinel=None) -> str:
    completed = subprocess.run(
        command,
        cwd=str(TOOL_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(f"Command failed ({completed.returncode}): {command}\n{combined[-12000:]}")
    return combined


def blender_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "BLENDER_USER_RESOURCES": str(USER_RESOURCES),
            "ACUPOINT_MCP_PROJECT_ROOT": str(PROJECT_ROOT),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return environment


def prepare(snapshot: Path, result: Path) -> str:
    return run_checked(
        [
            str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--",
            "--snapshot", str(snapshot), "--result", str(result), "--width", "1280", "--height", "1024",
        ],
        environment=blender_environment(),
        sentinel="ACU_PREPARE_PRONE_SCENE=PASS",
    )


def export(snapshot: Path, output: Path, result: Path) -> str:
    return run_checked(
        [
            str(BLENDER), "--background", str(snapshot), "--python", str(EXPORT), "--",
            "--fixture", str(FIXTURE), "--output", str(output), "--result", str(result),
            "--width", "1280", "--height", "1024",
        ],
        environment=blender_environment(),
        sentinel="ACU_EXPORT_PRONE_SAMPLE=PASS",
    )


def independent_verify(sample: Path, snapshot: Path, replay: Path, output: Path) -> str:
    return run_checked(
        [
            str(PYTHON), str(VERIFY), "--sample", str(sample), "--scene-blend", str(snapshot),
            "--blender-exe", str(BLENDER), "--protected-manifest", str(PROTECTED),
            "--compare-sample", str(replay), "--require-rgbd", "--output", str(output),
        ],
        environment=blender_environment(),
    )


def prone_verify(sample: Path, independent: Path, output: Path) -> str:
    return run_checked(
        [
            str(PYTHON), str(VERIFY_PRONE), "--sample", str(sample), "--fixture", str(FIXTURE),
            "--independent-report", str(independent), "--output", str(output),
        ],
        environment=blender_environment(),
    )


def make_overlay(sample: Path) -> None:
    sys.path.insert(0, str(TOOL_ROOT))
    from server import _overlay

    _overlay(sample / "rgb.png", sample / "labels.json", sample / "overlay.png")


def write_manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    required = [CANONICAL, FORMAL_ATLAS, OFFICIAL_ZIP, BLENDER, PYTHON, PROTECTED, FIXTURE, PREPARE, EXPORT, VERIFY, VERIFY_PRONE, CORE_SOURCE, CORE_RUNTIME]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    if sha256(CORE_SOURCE) != sha256(CORE_RUNTIME):
        raise RuntimeError("training_export_core source/runtime render_buffers.py differ")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    delivery = PROJECT_ROOT / "outputs" / "交付文件" / timestamp
    delivery.mkdir(parents=True, exist_ok=False)
    temp_parent = (PROJECT_ROOT / "outputs" / "BlenderMCP" / "tmp").resolve()
    temp_parent.mkdir(parents=True, exist_ok=True)
    temporary = (temp_parent / f"prone_rgbd_{uuid.uuid4().hex}").resolve()
    if temp_parent not in temporary.parents:
        raise RuntimeError("temporary path escaped approved root")
    temporary.mkdir()

    protected_before = {"canonical_skel": sha256(CANONICAL), "formal_atlas": sha256(FORMAL_ATLAS), "official_zip": sha256(OFFICIAL_ZIP)}
    snapshot = delivery / "prone_scene_snapshot.blend"
    sample = delivery / "sample_prone_000001"
    replay = temporary / "replay"
    independent_report = delivery / "independent_verification.json"
    prone_report = delivery / "prone_acceptance.json"
    success = False
    logs = {}
    try:
        logs["prepare"] = prepare(snapshot, temporary / "prepare.json")
        logs["export"] = export(snapshot, sample, temporary / "export.json")
        logs["replay"] = export(snapshot, replay, temporary / "replay.json")
        make_overlay(sample)
        logs["independent"] = independent_verify(sample, snapshot, replay, independent_report)
        logs["prone"] = prone_verify(sample, independent_report, prone_report)

        independent = json.loads(independent_report.read_text(encoding="utf-8-sig"))
        prone = json.loads(prone_report.read_text(encoding="utf-8-sig"))
        if not independent.get("passed") or not prone.get("passed"):
            raise AssertionError("verification report did not pass")
        protected_after = {"canonical_skel": sha256(CANONICAL), "formal_atlas": sha256(FORMAL_ATLAS), "official_zip": sha256(OFFICIAL_ZIP)}
        if protected_after != protected_before:
            raise AssertionError("protected source asset changed")

        shutil.copy2(FIXTURE, delivery / FIXTURE.name)
        labels = json.loads((sample / "labels.json").read_text(encoding="utf-8-sig"))
        verification = {
            "schema": "skel-prone-rgbd-delivery-v1",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "passed": True,
            "medical_truth": False,
            "scene": "rigid prone transform, back upward, overhead synthetic camera, bed first-surface geometry",
            "fixture_sha256": sha256(FIXTURE),
            "snapshot_sha256": sha256(snapshot),
            "protected_assets_before": protected_before,
            "protected_assets_after": protected_after,
            "source_runtime_core_match": sha256(CORE_SOURCE) == sha256(CORE_RUNTIME),
            "independent_summary": independent["summary"],
            "prone_summary": prone["summary"],
            "visibility": {point["point_id"]: point["visibility_reason"] for point in labels["points"]},
            "conclusion": "The first controlled prone-back SKEL RGB/Z-depth/valid-mask/skin-mask/labels sample passed independent reopen and exact replay checks.",
            "limitations": [
                "All ENG_* points are engineering anchors, not medical acupoints.",
                "This is a rigid prone transform; SKEL articulated pose parameters remain canonical.",
                "The synthetic pinhole camera has no real RGB-D calibration, distortion, or noise.",
                "This single sample does not authorize batch dataset production or medical propagation claims.",
            ],
        }
        write_json(delivery / "verification.json", verification)
        (delivery / "README.md").write_text(
            "# 第一个俯卧背部 SKEL 单样本闭环\n\n"
            "结果：**PASS**。人体为 canonical 女性 SKEL 的刚性俯卧工程场景：背部朝上、头部在图像上方、相机位于床面上方。\n\n"
            "`sample_prone_000001/` 包含 `rgb.png`、`scene_depth_z.npy`、`depth_valid_mask.png`、`skin_mask.png`、`labels.json`、`render_metadata.json` 与 `overlay.png`。"
            "Depth 是 OpenCV 相机坐标第一可见场面的 Zc（float32 米，背景 0）；床面进入 Scene Depth，但不进入 Skin Mask。\n\n"
            "6 个 ENG_BACK_* 背部工程锚点可见；2 个 ENG_FRONT_* 前胸/腹部对照点按互斥规则标为 BACK_FACING。独立射线另行确认相机到这些前侧点的路径先命中背部皮肤，因此人体自遮挡成立。\n\n"
            "所有 ENG_* 都不是医学穴位。此场景只是单样本工程门，尚未加入医生正式 Atlas、真实相机标定/噪声或批量随机化。`.blend` 含授权模型，仅限内部研究，不得外发。\n",
            encoding="utf-8",
        )
        (delivery / "交付清单.md").write_text(
            "# 交付清单\n\n"
            "- `sample_prone_000001/`：对齐的 RGB / Z-Depth / Valid Mask / Skin Mask / labels / overlay\n"
            "- `prone_scene_snapshot.blend`：独立重放场景（内部授权模型，不得外发）\n"
            "- `prone_engineering_fixture.json`：8 个冻结工程锚点夹具\n"
            "- `independent_verification.json`：通用几何、深度、逐像素射线与重放验收\n"
            "- `prone_acceptance.json`：俯卧场景专项验收\n"
            "- `verification.json`：汇总结论与限制\n"
            "- `SHA256SUMS.txt`：交付目录全量校验\n",
            encoding="utf-8",
        )
        write_manifest(delivery)
        success = True
        print(json.dumps({"passed": True, "delivery": str(delivery)}, ensure_ascii=False))
    except Exception:
        write_json(
            delivery / "FAILED_DO_NOT_DELIVER.json",
            {"passed": False, "notice": "Failed build; do not deliver.", "log_tails": {key: value[-4000:] for key, value in logs.items()}},
        )
        raise
    finally:
        if success and temporary.is_dir() and temp_parent in temporary.parents:
            shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
