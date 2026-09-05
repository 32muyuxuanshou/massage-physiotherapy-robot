"""Legacy RGB-only/v1 delivery builder retained for audit history.

Do not use for the current schema.  The active entry point is
``build_rgbd_integration_delivery.py``.
"""

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

from PIL import Image, ImageChops


TOOL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_ROOT.parents[1]
WORKBENCH_ROOT = (
    PROJECT_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
)
TEMPLATE = (
    PROJECT_ROOT
    / "模型资源"
    / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发"
    / "templates"
    / "SKEL"
    / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
)
ATLAS = (
    WORKBENCH_ROOT
    / "workspace"
    / "导出结果"
    / "20260824_173250_skel_female_1_1"
    / "20260824_173250_skel_female_1_1_正式标注_最新.json"
)
BLENDER = WORKBENCH_ROOT / "runtime" / "blender" / "blender.exe"
USER_RESOURCES = WORKBENCH_ROOT / "user_resources"
OFFICIAL_ZIP = PROJECT_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_diff_metrics(first_path: Path, second_path: Path) -> dict[str, float | int | bool]:
    with Image.open(first_path) as first_source, Image.open(second_path) as second_source:
        first = first_source.convert("RGB")
        second = second_source.convert("RGB")
        if first.size != second.size:
            return {
                "same_size": False,
                "max_channel_difference": 255,
                "mean_channel_difference": 255.0,
                "different_channel_fraction": 1.0,
            }
        difference = ImageChops.difference(first, second)
        histogram = difference.histogram()
        total_channels = first.width * first.height * 3
        weighted_sum = sum((index % 256) * count for index, count in enumerate(histogram))
        different_channels = sum(
            count for index, count in enumerate(histogram) if (index % 256) != 0
        )
        max_difference = max(
            (index % 256 for index, count in enumerate(histogram) if count),
            default=0,
        )
        return {
            "same_size": True,
            "max_channel_difference": int(max_difference),
            "mean_channel_difference": float(weighted_sum / total_channels),
            "different_channel_fraction": float(different_channels / total_channels),
        }


def run_blender(work_blend: Path, script: Path, environment: dict[str, str], sentinel: str) -> str:
    result = subprocess.run(
        [str(BLENDER), "-b", str(work_blend), "--python", str(script)],
        cwd=str(work_blend.parent),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    if sentinel not in combined:
        raise RuntimeError(f"Blender step failed ({sentinel} missing):\n{combined[-5000:]}")
    return combined


for required in (TEMPLATE, ATLAS, BLENDER, USER_RESOURCES, OFFICIAL_ZIP):
    if not required.exists():
        raise FileNotFoundError(required)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
delivery_root = PROJECT_ROOT / "outputs" / "交付文件" / timestamp
delivery_root.mkdir(parents=True, exist_ok=False)
sample_dir = delivery_root / "sample_000001"
sample_dir.mkdir()

temporary_parent = PROJECT_ROOT / "outputs" / "BlenderMCP" / "tmp"
temporary_parent.mkdir(parents=True, exist_ok=True)
temporary_root = temporary_parent / f"single_point_{uuid.uuid4().hex}"
temporary_root.mkdir()
work_blend = temporary_root / "SKEL_FEMALE_REOPEN_TEST_COPY.blend"
replay_dir = temporary_root / "replay_sample"
replay_dir.mkdir()
export_result_path = temporary_root / "export_result.json"
verify_result_path = temporary_root / "verify_result.json"
shutil.copy2(TEMPLATE, work_blend)

template_hash_before = sha256(TEMPLATE)
work_hash_before = sha256(work_blend)
atlas_hash = sha256(ATLAS)
zip_hash_before = sha256(OFFICIAL_ZIP)

environment = os.environ.copy()
environment.update(
    {
        "BLENDER_USER_RESOURCES": str(USER_RESOURCES),
        "ACUPOINT_MCP_PROJECT_ROOT": str(PROJECT_ROOT),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "ACU_DELIVERY_ATLAS": str(ATLAS),
        "ACU_DELIVERY_SAMPLE_DIR": str(sample_dir),
        "ACU_DELIVERY_EXPORT_RESULT": str(export_result_path),
    }
)

try:
    first_log = run_blender(
        work_blend,
        TOOL_ROOT / "tests" / "delivery_export_blender.py",
        environment,
        "ACU_DELIVERY_EXPORT=PASS",
    )
    if sha256(work_blend) != work_hash_before:
        raise AssertionError("first Blender process saved or modified the work Blend")

    sys.path.insert(0, str(TOOL_ROOT))
    from server import _overlay

    rgb_path = sample_dir / "rgb.png"
    labels_path = sample_dir / "labels.json"
    overlay_path = sample_dir / "overlay.png"
    _overlay(rgb_path, labels_path, overlay_path)

    verify_environment = environment.copy()
    verify_environment.update(
        {
            "ACU_DELIVERY_LABELS": str(labels_path),
            "ACU_DELIVERY_RGB": str(rgb_path),
            "ACU_DELIVERY_REPLAY_DIR": str(replay_dir),
            "ACU_DELIVERY_VERIFY_RESULT": str(verify_result_path),
        }
    )
    second_log = run_blender(
        work_blend,
        TOOL_ROOT / "tests" / "delivery_verify_blender.py",
        verify_environment,
        "ACU_DELIVERY_VERIFY=PASS",
    )
    work_hash_after = sha256(work_blend)
    if work_hash_after != work_hash_before:
        raise AssertionError("reopened Blender process saved or modified the work Blend")

    export_result = json.loads(export_result_path.read_text(encoding="utf-8-sig"))
    independent = json.loads(verify_result_path.read_text(encoding="utf-8-sig"))
    if not independent["passed"]:
        raise AssertionError(independent)
    replay_rgb_path = Path(independent["replay"]["rgb_path"])
    rgb_metrics = image_diff_metrics(rgb_path, replay_rgb_path)
    rgb_pixels_consistent = bool(
        rgb_metrics["same_size"]
        and rgb_metrics["max_channel_difference"] <= 2
        and rgb_metrics["mean_channel_difference"] <= 0.02
    )
    independent["checks"]["reopen_reexport_rgb_pixel_metrics"] = rgb_metrics
    independent["checks"]["reopen_reexport_rgb_pixels_consistent"] = rgb_pixels_consistent
    independent["passed"] = bool(independent["passed"] and rgb_pixels_consistent)
    if not independent["passed"]:
        raise AssertionError(independent)

    verification = {
        "schema": "skel-single-point-delivery-verification-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "passed": True,
        "scope": {
            "model": "SKEL female v2.3 trunk/limb canonical template",
            "point_id": "11_MIDLINE",
            "point_name": "111",
            "medical_truth": False,
            "purpose": "software and geometry closed-loop engineering test",
        },
        "camera": {
            "name": "ACU_TRAIN_CAMERA_TEST",
            "preset": "front",
            "lens_mm": 55.0,
            "sensor_width_mm": 36.0,
            "resolution": [1024, 1024],
            "real_robot_camera": False,
        },
        "source_assets": {
            "template": str(TEMPLATE),
            "template_sha256_before": template_hash_before,
            "template_sha256_after": sha256(TEMPLATE),
            "atlas": str(ATLAS),
            "atlas_sha256": atlas_hash,
            "official_zip": str(OFFICIAL_ZIP),
            "official_zip_sha256_before": zip_hash_before,
            "official_zip_sha256_after": sha256(OFFICIAL_ZIP),
        },
        "no_save_reopen": {
            "work_blend_sha256_before": work_hash_before,
            "work_blend_sha256_after_first_process": work_hash_before,
            "work_blend_sha256_after_reopen_process": work_hash_after,
            "unchanged": work_hash_before == work_hash_after == template_hash_before,
        },
        "export": export_result,
        "independent_verification": independent,
        "blender_process_evidence": {
            "first_success_sentinel": "ACU_DELIVERY_EXPORT=PASS" in first_log,
            "reopen_success_sentinel": "ACU_DELIVERY_VERIFY=PASS" in second_log,
        },
        "conclusion": (
            "The saved engineering point 11_MIDLINE completed SKEL surface binding -> "
            "evaluated 3D -> synthetic camera 2D -> visibility -> training sample export."
        ),
        "not_proven": [
            "medical acupoint correctness",
            "medical propagation across body shapes and poses",
            "real RGB-D camera calibration or distortion",
            "robot execution coordinates",
            "readiness for bulk training-set production",
        ],
    }
    verification_path = delivery_root / "verification.json"
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = f"""# 正式 SKEL 单点闭环交付

## 结果

本次在冻结的女性 SKEL v2.3 躯干与四肢规范模板上，使用主动保存的正式
`smpl-acupoint-annotation-v5` Atlas，将工程测试点 `11_MIDLINE / 111` 跑通：

`face_index + barycentric -> 当前 evaluated SKEL 三维坐标 -> 55 mm 合成相机二维像素 -> 场景可见性 -> 单训练样本`

全部自动验收通过。`111` 不是医生确认的医学穴位，本交付只验证软件与几何闭环。

## 固定输入

- 模型：SKEL female v2.3，6890 顶点、13776 三角面
- 模板 SHA-256：`{template_hash_before}`
- Atlas SHA-256：`{atlas_hash}`
- 点：`11_MIDLINE`，face index `13745`
- 相机：`ACU_TRAIN_CAMERA_TEST`，正面，55 mm，36 mm sensor width
- 输出分辨率：1024 × 1024
- 坐标：Blender 世界坐标；相机标签同时给出 OpenCV `+X右/+Y下/+Z前`

## 独立复核

- verifier 没有调用正式插件的 `_surface_sample`；它独立读取 evaluated mesh 三角面并计算重心坐标。
- `xyz_world` 允许误差 `< 1e-6 m`。
- `uv` 允许误差 `< 1e-3 px`。
- 可见性、原因、射线命中对象和面编号必须完全一致。
- 第一进程退出后重新打开同一未保存测试 Blend，再导出标签和 RGB；结果必须一致。
- 测试 Blend、源模板和正式 v2.3 ZIP 均未被覆盖。

详见 `verification.json`；文件哈希见 `SHA256SUMS.txt`。

## 不能据此宣称

- 不能宣称穴位医学位置正确。
- 不能宣称穴位对体型/姿态的传播已获医生认可。
- 不能宣称 Blender 相机等同真实 RGB-D 相机。
- 不能把 Blender 坐标直接发送给机器人。
- 不能据此开始批量生产正式训练集。
"""
    readme_path = delivery_root / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    hash_targets = [
        readme_path,
        verification_path,
        rgb_path,
        overlay_path,
        labels_path,
    ]
    hash_lines = [
        f"{sha256(path)}  {path.relative_to(delivery_root).as_posix()}" for path in hash_targets
    ]
    (delivery_root / "SHA256SUMS.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
finally:
    resolved_temp = temporary_root.resolve()
    resolved_parent = temporary_parent.resolve()
    if resolved_temp.parent != resolved_parent or not resolved_temp.name.startswith("single_point_"):
        raise RuntimeError(f"refusing to remove unexpected temporary path: {resolved_temp}")
    shutil.rmtree(resolved_temp)

print(f"ACU_SINGLE_POINT_DELIVERY={delivery_root}")
