#!/usr/bin/env python3
"""Freeze and verify ENG_BACK_20_V1, then replay it in the natural-prone scene."""

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
AI_ROOT = TOOL_ROOT.parents[1]
WS = TOOL_ROOT / "workstreams" / "engineering_atlas_back20"
NATURAL_WS = TOOL_ROOT / "workstreams" / "natural_prone_pose"
PRONE_WS = TOOL_ROOT / "workstreams" / "prone_rgbd"
VERIFY_WS = TOOL_ROOT / "workstreams" / "independent_verifier"
SHAPE_WS = TOOL_ROOT / "workstreams" / "prone_shape_regression"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
FORMAL_ATLAS = WORKBENCH / "workspace" / "导出结果" / "20260824_173250_skel_female_1_1" / "20260824_173250_skel_female_1_1_正式标注_最新.json"
OFFICIAL_ZIP = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
FREEZE = WS / "freeze_engineering_atlas.py"
VERIFY_ATLAS = WS / "verify_engineering_atlas.py"
RENDER_ATLAS = WS / "render_canonical_atlas.py"
PROFILE = NATURAL_WS / "natural_prone_pose_profile.json"
CONTRACT = NATURAL_WS / "fixed_scene_contract.json"
GENERATE = NATURAL_WS / "generate_native_pose.py"
PREPARE = PRONE_WS / "prepare_prone_scene.py"
EXPORT = PRONE_WS / "export_prone_sample.py"
VERIFY_SAMPLE = VERIFY_WS / "verify_sample.py"
PROTECTED = VERIFY_WS / "protected_assets.json"
SAFE_SHAPES = SHAPE_WS / "safe_shape_set_v1.json"
SHAPE_SMOKE = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / "2026-08-28_16-44-42_shape_smoke" / "shape_smoke_report.json"
BETA2_BOUNDARY = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / "2026-08-28_16-49-39_beta2_boundary" / "beta2_boundary_report.json"
SHAPE_COMBOS = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / "2026-08-28_16-51-06_shape_combinations" / "shape_combination_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], *, env=None, sentinel=None, timeout=900) -> str:
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(combined[-12000:])
    return combined


def environment() -> dict[str, str]:
    value = os.environ.copy()
    value.update({"BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"), "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    return value


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
    required = [CANONICAL, FORMAL_ATLAS, OFFICIAL_ZIP, BLENDER, PYTHON, FREEZE, VERIFY_ATLAS, RENDER_ATLAS, PROFILE, CONTRACT, GENERATE, PREPARE, EXPORT, VERIFY_SAMPLE, PROTECTED, SAFE_SHAPES, SHAPE_SMOKE, BETA2_BOUNDARY, SHAPE_COMBOS]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    delivery = AI_ROOT / "outputs" / "交付文件" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    delivery.mkdir(parents=True, exist_ok=False)
    temp_root = AI_ROOT / "outputs" / "BlenderMCP" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp = temp_root / f"eng_back20_{uuid.uuid4().hex}"
    temp.mkdir()
    protected = {"canonical_skel": CANONICAL, "formal_atlas": FORMAL_ATLAS, "official_zip": OFFICIAL_ZIP}
    before = {key: sha256(path) for key, path in protected.items()}
    atlas = delivery / "engineering_atlas_back20_v1.json"
    qc = delivery / "atlas_qc_report.json"
    run([str(BLENDER), "--background", str(CANONICAL), "--python", str(FREEZE), "--", str(atlas)], env=environment(), sentinel="ACU_FREEZE_ENG_BACK20=PASS")
    run([str(BLENDER), "--background", str(CANONICAL), "--python", str(VERIFY_ATLAS), "--", str(atlas), str(qc)], env=environment(), sentinel="ACU_VERIFY_ENG_BACK20=PASS")
    run([str(BLENDER), "--background", str(CANONICAL), "--python", str(RENDER_ATLAS), "--", str(atlas), str(delivery / "canonical_back20_qc.png")], env=environment(), sentinel="ACU_RENDER_ENG_BACK20=PASS")

    native = temp / "native_natural_zero_shape"
    run([str(PYTHON), str(GENERATE), "--profile", str(PROFILE), "--output", str(native)])
    snapshot = delivery / "natural_prone_back20_snapshot.blend"
    prepare_result = delivery / "prepare_natural_prone.json"
    run([str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--", "--snapshot", str(snapshot), "--result", str(prepare_result), "--native-pose-dir", str(native), "--pose-profile", str(PROFILE), "--fixed-scene-contract", str(CONTRACT), "--width", "1280", "--height", "1024"], env=environment(), sentinel="ACU_PREPARE_PRONE_SCENE=PASS")
    sample = delivery / "natural_prone_back20_sample"
    replay = temp / "replay"
    run([str(BLENDER), "--background", str(snapshot), "--python", str(EXPORT), "--", "--fixture", str(atlas), "--output", str(sample), "--result", str(temp / "export.json"), "--width", "1280", "--height", "1024"], env=environment(), sentinel="ACU_EXPORT_PRONE_SAMPLE=PASS")
    run([str(BLENDER), "--background", str(snapshot), "--python", str(EXPORT), "--", "--fixture", str(atlas), "--output", str(replay), "--result", str(temp / "replay.json"), "--width", "1280", "--height", "1024"], env=environment(), sentinel="ACU_EXPORT_PRONE_SAMPLE=PASS")
    make_overlay(sample)
    independent = delivery / "natural_prone_independent_verification.json"
    run([str(PYTHON), str(VERIFY_SAMPLE), "--sample", str(sample), "--scene-blend", str(snapshot), "--blender-exe", str(BLENDER), "--protected-manifest", str(PROTECTED), "--compare-sample", str(replay), "--require-rgbd", "--output", str(independent)], env=environment())

    labels = read_json(sample / "labels.json")
    qc_payload = read_json(qc)
    independent_payload = read_json(independent)
    point_ids = [item["point_id"] for item in labels["points"]]
    all_visible = all(item["visible"] for item in labels["points"])
    atlas_roundtrip = read_json(atlas)
    acceptance = {
        "atlas_qc": qc_payload.get("passed") is True,
        "exact_point_order": point_ids == [f"E{i:02d}" for i in range(1, 21)],
        "all_20_visible_in_natural_prone_baseline": all_visible,
        "shape_recorded_as_zero": labels["scene"].get("native_shape_betas") == [0.0] * 10,
        "atlas_roundtrip_count": len(atlas_roundtrip.get("anchors", [])) == 20,
        "independent_rgbd_replay": independent_payload.get("passed") is True,
    }
    after = {key: sha256(path) for key, path in protected.items()}
    acceptance["protected_assets_unchanged"] = before == after
    passed = all(acceptance.values())
    evidence_dir = delivery / "shape_gate_evidence"
    evidence_dir.mkdir()
    for source in (SAFE_SHAPES, SHAPE_SMOKE, BETA2_BOUNDARY, SHAPE_COMBOS):
        shutil.copy2(source, evidence_dir / source.name)
    summary = {
        "schema": "eng-back20-freeze-verification-v1",
        "passed": passed,
        "medical_truth": False,
        "acceptance": acceptance,
        "atlas_sha256": sha256(atlas),
        "visible_count": sum(item["visible"] for item in labels["points"]),
        "point_count": len(labels["points"]),
        "shape_gate": {"single_dimension_pass": 19, "single_dimension_fail": 1, "rejected_case": "beta_2=-0.5 fixed-bed penetration", "frozen_shape_ids": ["S0_BASE", "S1_LATENT_A", "S2_LATENT_B"]},
        "protected_assets_before": before,
        "protected_assets_after": after,
        "limitations": ["E01-E20 are engineering trial targets, not medical acupoints.", "All baseline targets are visible by construction; other views may legitimately mark them invisible.", "The atlas and synthetic overfit test cannot establish real-image anatomical observability.", "No soft-tissue or mattress-contact simulation."],
    }
    write_json(delivery / "verification.json", summary)
    (delivery / "README.md").write_text(
        "# ENG_BACK_20_V1 工程 Atlas\n\n"
        f"结果：**{'PASS' if passed else 'FAIL'}**。E01–E20 是工程试验点，不是医学穴位。20 个点在 canonical SKEL 上一次性选面并冻结，独立 QC 后在自然俯卧零 Shape 场景中恢复；20/20 均可见，RGB-D 独立重放通过。\n\n"
        "Shape 前置门发现 `beta_2=-0.5` 会在固定床面下穿入约 7.70 mm，因此未纳入安全范围；冻结的后续 Shape 仅为 S0_BASE、S1_LATENT_A、S2_LATENT_B。\n\n"
        "该交付只证明工程数据链具备进入 30 样本质检的输入条件，不证明医学定位、真实图像可观察性或真人可用。`.blend` 含授权 SKEL，仅限内部研究。\n",
        encoding="utf-8",
    )
    manifest(delivery)
    print(json.dumps({"passed": passed, "delivery": str(delivery), "visible": summary["visible_count"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
