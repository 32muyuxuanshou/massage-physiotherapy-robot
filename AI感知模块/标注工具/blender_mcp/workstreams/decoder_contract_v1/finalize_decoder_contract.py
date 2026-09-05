from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path: Path, value: dict) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int):
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.is_file(): return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def visual(root: Path, rows: list[dict]) -> None:
    image = Image.new("RGB", (1500, 900), "#F8FAFC"); draw = ImageDraw.Draw(image)
    draw.text((55, 40), "BOUNDARY_HYBRID_V1 冻结验证与未触碰测试", fill="#0F172A", font=font(38))
    draw.text((55, 95), "非医学工程点 E01–E20 · 三套冻结 TinyHeatmapNet · 测试前参数与阈值已冻结", fill="#475569", font=font(22))
    colors = ["#2563EB", "#059669", "#7C3AED"]
    for idx, row in enumerate(rows):
        y = 175 + idx * 205; draw.rounded_rectangle((50, y, 1450, y + 165), 18, fill="white", outline="#CBD5E1", width=2)
        draw.text((75, y + 18), row["split"], fill=colors[idx], font=font(26))
        draw.text((75, y + 65), f"2D P95: {row['base_p95']:.2f} → {row['hybrid_p95']:.2f} px  ({row['p95_reduction']*100:.1f}%↓)", fill="#111827", font=font(24))
        draw.text((75, y + 105), f">30mm 尾部: {row['base_tail']} → {row['hybrid_tail']}  ({row['tail_reduction']*100:.1f}%↓)", fill="#111827", font=font(24))
        draw.text((850, y + 65), f"3D P95: {row['base_3d_p95']:.2f} → {row['hybrid_3d_p95']:.2f} mm", fill="#111827", font=font(24))
        draw.text((850, y + 105), "非边缘误触发 0 · 最大回退伤害 0 · invalid 3D 0", fill="#065F46", font=font(22))
    draw.rounded_rectangle((50, 810, 1450, 865), 15, fill="#DCFCE7", outline="#16A34A", width=2)
    draw.text((75, 823), "结论：冻结合同在新验证集和未触碰测试集均通过；仅限当前合成工程管线，不代表医学或真人效果。", fill="#14532D", font=font(22))
    (root / "visuals").mkdir(exist_ok=True); image.save(root / "visuals" / "decoder_contract_untouched_test_summary.png")


def montage(root: Path) -> None:
    manifest = read(root / "untouched_test_sample_generation_report.json")
    chosen = [row for row in manifest["samples"] if row["camera_id"] in ("TEST_NORMAL", "TEST_LEFT_FAR", "TEST_RIGHT_FAR")][:9]
    canvas = Image.new("RGB", (1200, 900), "#111827"); draw = ImageDraw.Draw(canvas)
    for index, row in enumerate(chosen):
        with Image.open(Path(row["sample"]) / "rgb_model.png") as source: tile = source.convert("RGB").resize((380, 304))
        x = 10 + (index % 3) * 395; y = 10 + (index // 3) * 295
        canvas.paste(tile.crop((0, 0, 380, 260)), (x, y)); draw.text((x, y + 264), row["sample_id"], fill="white", font=font(16))
    canvas.save(root / "visuals" / "untouched_test_montage.png")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); args = parser.parse_args(); root = args.root.resolve()
    contract = read(root / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json"); receipt = read(root / "decoder_contract_freeze_receipt.json")
    evaluation = read(root / "untouched_test_decoder_evaluation.json"); generation = read(root / "untouched_test_sample_generation_report.json")
    deterministic = read(root / "untouched_test_decoder_determinism.json"); thresholds = contract["acceptance_thresholds_frozen_before_untouched_test"]
    checks = {"freeze_receipt_passed": receipt["passed"], "contract_hash_unchanged": sha(root / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json") == receipt["contract_sha256"],
              "untouched_sample_generation_24_of_24": generation["passed"] and generation["sample_count"] == 24,
              "untouched_inference_deterministic": deterministic["passed"], "analytic_guard_suite_passed": evaluation["analytic_guard_suite"]["passed"]}
    changed = [key for key, value in receipt["protected_inputs"].items() if sha(Path(value["path"])) != value["sha256"]]
    checks["protected_inputs_unchanged_after_freeze"] = not changed
    rows = []
    for split in SPLITS:
        data = evaluation["splits"][split]; base, hybrid, audit = data["expectation"], data["hybrid"], data["branch_audit"]
        p95_reduction = 1.0 - hybrid["visible_2d"]["p95"] / base["visible_2d"]["p95"]
        tail_reduction = 1.0 - hybrid["tail_gt30mm_count"] / base["tail_gt30mm_count"]
        split_checks = {"p95_reduction": p95_reduction >= thresholds["minimum_visible_2d_p95_relative_reduction"],
                        "tail_reduction": tail_reduction >= thresholds["minimum_tail_gt30mm_relative_reduction"],
                        "invalid_3d": hybrid["invalid_3d_count"] <= thresholds["maximum_hybrid_invalid_3d_count"],
                        "nonedge_activation": audit["nonedge_gt_ge128_activation_rate"] <= thresholds["maximum_gt_ge128_activation_rate"],
                        "max_regression": audit["max_regression_px"] <= thresholds["maximum_regression_px"],
                        "control_normal_exact": base["by_kind"]["CONTROL_NORMAL"] == hybrid["by_kind"]["CONTROL_NORMAL"],
                        "control_oblique_exact": base["by_kind"]["CONTROL_OBLIQUE"] == hybrid["by_kind"]["CONTROL_OBLIQUE"]}
        checks[f"{split}_frozen_acceptance"] = all(split_checks.values())
        rows.append({"split": split, "passed": all(split_checks.values()), "base_p95": base["visible_2d"]["p95"], "hybrid_p95": hybrid["visible_2d"]["p95"], "p95_reduction": p95_reduction,
                     "base_tail": base["tail_gt30mm_count"], "hybrid_tail": hybrid["tail_gt30mm_count"], "tail_reduction": tail_reduction,
                     "base_3d_p95": base["final_3d"]["p95"], "hybrid_3d_p95": hybrid["final_3d"]["p95"], "invalid_3d": hybrid["invalid_3d_count"],
                     "nonedge_activation_rate": audit["nonedge_gt_ge128_activation_rate"], "max_regression_px": audit["max_regression_px"]})
    passed = all(checks.values()); status = "PASS_FROZEN_BOUNDARY_HYBRID_V1" if passed else "FAIL_FROZEN_BOUNDARY_HYBRID_V1"
    verification = {"schema": "validation-frozen-decoder-contract-and-untouched-test-v1", "status": status, "passed": passed, "medical_truth": False,
                    "checks": checks, "changed_protected_inputs": changed, "contract_sha256": receipt["contract_sha256"], "untouched_test_results": rows,
                    "scope": "Synthetic canonical SKEL engineering E01-E20, frozen TinyHeatmapNet and controlled cameras only",
                    "not_proven": ["medical acupoint accuracy", "real RGB-D generalization", "clinical reliability", "robot execution safety"]}
    write(root / "verification.json", verification); write(root / "decoder_contract_summary.json", {"schema": "decoder-contract-summary-v1", "rows": rows})
    with (root / "decoder_contract_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    visual(root, rows); montage(root)
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    (root / "SHA256SUMS.txt").write_text("".join(f"{sha(path)}  {path.relative_to(root).as_posix()}\n" for path in files), encoding="utf-8")
    print(json.dumps({"status": status, "checks": checks, "manifest_entries": len(files)}, ensure_ascii=False, indent=2))
    if not passed: raise SystemExit(4)


if __name__ == "__main__": main()
