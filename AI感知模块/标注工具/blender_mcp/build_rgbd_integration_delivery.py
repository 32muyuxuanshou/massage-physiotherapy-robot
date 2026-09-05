"""Build and independently verify the canonical-SKEL RGB-D integration delivery."""

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
WORKSTREAM = TOOL_ROOT / "workstreams" / "integrated_rgbd"
VERIFIER_ROOT = TOOL_ROOT / "workstreams" / "independent_verifier"
WORKBENCH = (
    PROJECT_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
)
CANONICAL = (
    PROJECT_ROOT
    / "模型资源"
    / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发"
    / "templates"
    / "SKEL"
    / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
)
ATLAS = (
    WORKBENCH
    / "workspace"
    / "导出结果"
    / "20260824_173250_skel_female_1_1"
    / "20260824_173250_skel_female_1_1_正式标注_最新.json"
)
OFFICIAL_ZIP = PROJECT_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
USER_RESOURCES = WORKBENCH / "user_resources"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
PROTECTED = VERIFIER_ROOT / "protected_assets.json"
PREPARE = WORKSTREAM / "prepare_integration_scene.py"
EXPORT = WORKSTREAM / "export_integrated_sample.py"
VERIFY = VERIFIER_ROOT / "verify_sample.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    timeout: int = 600,
    sentinel: str | None = None,
) -> str:
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
    if completed.returncode != 0 or (sentinel is not None and sentinel not in combined):
        raise RuntimeError(
            f"Command failed ({completed.returncode}, sentinel={sentinel!r}): {command}\n"
            f"STDOUT/STDERR tail:\n{combined[-12000:]}"
        )
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


def prepare_snapshot(snapshot: Path, result: Path, *, occluded: bool) -> str:
    command = [
        str(BLENDER),
        "--background",
        str(CANONICAL),
        "--python",
        str(PREPARE),
        "--",
        "--snapshot",
        str(snapshot),
        "--result",
        str(result),
        "--width",
        "1024",
        "--height",
        "1024",
    ]
    if occluded:
        command.append("--occluded")
    return run_checked(
        command,
        environment=blender_environment(),
        sentinel="ACU_PREPARE_INTEGRATION_SCENE=PASS",
    )


def export_sample(snapshot: Path, sample: Path, result: Path) -> str:
    sample.mkdir(parents=True, exist_ok=False)
    command = [
        str(BLENDER),
        "--background",
        str(snapshot),
        "--python",
        str(EXPORT),
        "--",
        "--atlas",
        str(ATLAS),
        "--output",
        str(sample),
        "--result",
        str(result),
        "--width",
        "1024",
        "--height",
        "1024",
    ]
    return run_checked(
        command,
        environment=blender_environment(),
        sentinel="ACU_EXPORT_INTEGRATED_SAMPLE=PASS",
    )


def verify_sample(sample: Path, snapshot: Path, replay: Path, output: Path) -> str:
    return run_checked(
        [
            str(PYTHON),
            str(VERIFY),
            "--sample",
            str(sample),
            "--scene-blend",
            str(snapshot),
            "--blender-exe",
            str(BLENDER),
            "--protected-manifest",
            str(PROTECTED),
            "--compare-sample",
            str(replay),
            "--require-rgbd",
            "--output",
            str(output),
        ],
        environment=blender_environment(),
        timeout=900,
    )


def make_overlay(sample: Path) -> None:
    sys.path.insert(0, str(TOOL_ROOT))
    from server import _overlay

    _overlay(sample / "rgb.png", sample / "labels.json", sample / "overlay.png")


def manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    required = [CANONICAL, ATLAS, OFFICIAL_ZIP, BLENDER, PYTHON, PROTECTED, PREPARE, EXPORT, VERIFY]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    delivery = PROJECT_ROOT / "outputs" / "交付文件" / timestamp
    delivery.mkdir(parents=True, exist_ok=False)
    temp_parent = (PROJECT_ROOT / "outputs" / "BlenderMCP" / "tmp").resolve()
    temp_parent.mkdir(parents=True, exist_ok=True)
    temporary = (temp_parent / f"rgbd_integration_{uuid.uuid4().hex}").resolve()
    if temp_parent not in temporary.parents:
        raise RuntimeError("temporary path escaped the approved root")
    temporary.mkdir()

    protected_before = {
        "canonical_skel": sha256(CANONICAL),
        "formal_atlas": sha256(ATLAS),
        "official_zip": sha256(OFFICIAL_ZIP),
    }
    baseline_snapshot = delivery / "verification_scene_snapshot.blend"
    occlusion_snapshot = delivery / "occlusion_scene_snapshot.blend"
    baseline_sample = delivery / "sample_000001"
    occlusion_sample = delivery / "occlusion_diagnostic"
    replay_baseline = temporary / "replay_baseline"
    replay_occlusion = temporary / "replay_occlusion"
    logs: dict[str, str] = {}

    success = False
    try:
        logs["prepare_baseline"] = prepare_snapshot(
            baseline_snapshot, temporary / "prepare_baseline.json", occluded=False
        )
        logs["prepare_occlusion"] = prepare_snapshot(
            occlusion_snapshot, temporary / "prepare_occlusion.json", occluded=True
        )
        logs["export_baseline"] = export_sample(
            baseline_snapshot, baseline_sample, temporary / "export_baseline.json"
        )
        logs["export_baseline_replay"] = export_sample(
            baseline_snapshot, replay_baseline, temporary / "export_baseline_replay.json"
        )
        logs["export_occlusion"] = export_sample(
            occlusion_snapshot, occlusion_sample, temporary / "export_occlusion.json"
        )
        logs["export_occlusion_replay"] = export_sample(
            occlusion_snapshot, replay_occlusion, temporary / "export_occlusion_replay.json"
        )
        make_overlay(baseline_sample)
        make_overlay(occlusion_sample)

        baseline_report = delivery / "independent_verification_sample_000001.json"
        occlusion_report = delivery / "independent_verification_occlusion.json"
        logs["verify_baseline"] = verify_sample(
            baseline_sample, baseline_snapshot, replay_baseline, baseline_report
        )
        logs["verify_occlusion"] = verify_sample(
            occlusion_sample, occlusion_snapshot, replay_occlusion, occlusion_report
        )
        baseline_verification = json.loads(baseline_report.read_text(encoding="utf-8-sig"))
        occlusion_verification = json.loads(occlusion_report.read_text(encoding="utf-8-sig"))
        if not baseline_verification.get("passed") or not occlusion_verification.get("passed"):
            raise AssertionError("independent verification failed")

        protected_after = {
            "canonical_skel": sha256(CANONICAL),
            "formal_atlas": sha256(ATLAS),
            "official_zip": sha256(OFFICIAL_ZIP),
        }
        if protected_after != protected_before:
            raise AssertionError("a protected source asset changed")

        baseline_labels = json.loads((baseline_sample / "labels.json").read_text(encoding="utf-8-sig"))
        occlusion_labels = json.loads((occlusion_sample / "labels.json").read_text(encoding="utf-8-sig"))
        baseline_point = baseline_labels["points"][0]
        occlusion_point = occlusion_labels["points"][0]
        if baseline_point["visibility_reason"] != "VISIBLE":
            raise AssertionError(baseline_point)
        if occlusion_point["visibility_reason"] != "EXTERNAL_OCCLUDED":
            raise AssertionError(occlusion_point)

        verification = {
            "schema": "canonical-skel-rgbd-integration-delivery-v1",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "passed": True,
            "medical_truth": False,
            "point": "11_MIDLINE / 111 is an engineering test point only",
            "protected_assets_before": protected_before,
            "protected_assets_after": protected_after,
            "snapshots": {
                "baseline": {"path": baseline_snapshot.name, "sha256": sha256(baseline_snapshot)},
                "occlusion": {"path": occlusion_snapshot.name, "sha256": sha256(occlusion_snapshot)},
            },
            "sample_000001": {
                "visibility_reason": baseline_point["visibility_reason"],
                "independent_summary": baseline_verification["summary"],
            },
            "occlusion_diagnostic": {
                "visibility_reason": occlusion_point["visibility_reason"],
                "ray_hit_object": occlusion_point["ray_hit_object"],
                "independent_summary": occlusion_verification["summary"],
            },
            "conclusion": (
                "Canonical SKEL surface binding to RGB, camera-Z depth, visible-skin mask, "
                "camera labels, and scene-level occlusion passed an independent replay check."
            ),
            "limitations": [
                "The point is not medically validated.",
                "The camera is synthetic and has no real RGB-D distortion/noise model.",
                "This is a frontal canonical engineering scene, not the final prone treatment scene.",
                "This delivery does not authorize large-scale dataset production.",
            ],
        }
        write_json(delivery / "verification.json", verification)
        (delivery / "README.md").write_text(
            "# canonical SKEL 单点 RGB-D 闭环\n\n"
            "结果：**PASS**。`sample_000001` 是正常可见单点样本；"
            "`occlusion_diagnostic` 是外部遮挡分支诊断，不是第二个生产样本。\n\n"
            "每个目录的核心文件为 `rgb.png`、`scene_depth_z.npy`、"
            "`depth_valid_mask.png`、`skin_mask.png`、`labels.json` 和 `overlay.png`。\n\n"
            "Depth 是 OpenCV 相机坐标的第一可见场景表面 Zc，单位米，背景为 0。"
            "Skin Mask 只表示第一可见表面为 SKEL 皮肤的像素。\n\n"
            "`11_MIDLINE / 111` 只是工程测试点，不是医生确认的医学穴位。"
            "两份 `.blend` 仅用于内部独立重放验收，禁止作为模型资产外发。\n",
            encoding="utf-8",
        )
        (delivery / "交付清单.md").write_text(
            "# 交付清单\n\n"
            "- `sample_000001/`：正常可见单点 RGB-D 样本\n"
            "- `occlusion_diagnostic/`：外部遮挡诊断\n"
            "- `verification_scene_snapshot.blend`：基线重放场景\n"
            "- `occlusion_scene_snapshot.blend`：遮挡重放场景\n"
            "- `independent_verification_*.json`：独立验收报告\n"
            "- `verification.json`：汇总结论\n"
            "- `SHA256SUMS.txt`：全量文件校验\n",
            encoding="utf-8",
        )
        manifest(delivery)
        success = True
        print(json.dumps({"passed": True, "delivery": str(delivery)}, ensure_ascii=False))
    except Exception:
        failure = delivery / "FAILED_DO_NOT_DELIVER.json"
        write_json(
            failure,
            {
                "passed": False,
                "notice": "This directory is a failed integration attempt and must not be delivered.",
                "log_tails": {name: value[-4000:] for name, value in logs.items()},
            },
        )
        raise
    finally:
        if success and temporary.is_dir() and temp_parent in temporary.parents:
            shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
