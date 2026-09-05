#!/usr/bin/env python3
"""Record the human visual gate after pose_montage.png has been inspected."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import run_enhanced_pose_only as b


def manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{b.sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=b.OUT)
    parser.add_argument("--status", choices=("pass", "fail"), required=True)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    verification = b.read(root / "verification.json")
    provisional = b.read(root / "candidate_pose_profiles_base_shape_v1.json")
    visual_pass = args.status == "pass"
    visual = {
        "schema": "enhanced-pose-visual-review-v1",
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviewed_asset": "pose_montage.png",
        "passed": visual_pass,
        "notes": args.notes,
        "scope": "Frozen back camera only; no complete-body physiological or medical claim.",
    }
    b.write(root / "visual_review.json", visual)
    passed = bool(
        visual_pass and verification["automatic_gates_passed"] and verification["determinism_passed"]
        and verification["baseline_restore_passed"] and verification["source_inputs_unchanged"]
    )
    verification.update({
        "passed": passed,
        "visual_review": "PASS" if visual_pass else "FAIL",
        "status": "QUALIFIED_BASE_SHAPE_ONLY" if passed else "REJECTED_OR_INCOMPLETE",
        "complete_body_self_intersection_free": False,
        "medical_truth": False,
        "medical_validated": False,
    })
    b.write(root / "verification.json", verification)
    if passed:
        qualified = {
            "schema": "qualified-pose-profiles-base-shape-v1",
            "profile_set_id": "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1",
            "status": "QUALIFIED_FOR_FIXED_PRONE_ENGINEERING_SCENE_AT_BETA_ZERO_ONLY",
            "medical_truth": False,
            "medical_validated": False,
            "betas": [0.0] * 10,
            "profiles": provisional["profiles"],
            "hard_self_intersection_gate": "zero overlap pairs in frozen 20-point 2-ring neighborhoods",
            "global_overlap_notice": "The baseline has 293 historical global nonadjacent overlap pairs; no complete-body self-intersection-free claim is made.",
            "cannot_generalize_to_other_shapes": True,
            "next_required_stage": "SHAPE_X_POSE requires separate user authorization and cross-product validation",
        }
        b.write(root / "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1.json", qualified)
    report = b.read(root / "pose_only_report.json")
    sensitivity = b.read(root / "pose_sensitivity_report.json")
    readme = f"""# ENHANCED_POSE_ONLY_V1

结果：**{'PASS（仅 beta=0 固定俯卧工程场景）' if passed else 'FAIL/INCOMPLETE'}**。

- 既有 Pose：5 个；它们来自 2026-08-28 的已交付证据，不是首次实验。
- 新增诊断 Pose：7 个；总计 {report['case_count']} 个 Profile。
- F 自相交硬门：20个工程参考点的2-ring邻域必须为0；完整网格基线已有293对历史 overlap，因此不声称完整人体无自交。
- 自动门：{verification['automatic_gates_passed']}；全新进程确定性：{verification['determinism_passed']}；显式 R_BASE 恢复：{verification['baseline_restore_passed']}；目视门：{verification['visual_review']}。
- 当前20点是 engineering reference，`medical_truth=false / medical_validated=false`。
- 结论只对 beta=0、固定 Camera/Bed/Light/Atlas 成立，不能推广到其他 Shape。

主要文件：`existing_pose_audit.json`、`pose_sensitivity_report.json/.csv`、`pose_montage.png`、`pose_only_report.json`、`determinism_report.json`、`visual_review.json`、`verification.json`。{(' 已生成 `QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1.json`。' if passed else '')}

本任务没有启动 Shape×Pose、训练、医学验证或大规模生成。SKEL 是结构先验，不是患者 CT；Blender 坐标不是机器人执行坐标。
"""
    (root / "README.md").write_text(readme, encoding="utf-8")
    manifest(root)
    print(json.dumps({"passed": passed, "qualified_profiles": len(provisional["profiles"]) if passed else 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
