from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = read_json(args.output / "verification.json")
    metrics = read_json(args.output / "training_metrics.json")
    three_d = read_json(args.output / "predicted_uv_depth_3d_metrics.json")
    manifest = read_json(args.output / "dataset_manifest.json")
    determinism = read_json(args.output / "determinism_report.json")
    inference = read_json(args.output / "inference_replay_report.json")
    source_integrity = read_json(args.output / "source_integrity_report.json")
    combined = {
        "schema": "c-overfit-training-delivery-verification-v1",
        "passed": bool(verification["passed"] and determinism["passed"] and inference["passed"] and source_integrity["passed"]),
        "checks": {
            "training_pipeline": verification["passed"],
            "fresh_process_determinism": determinism["passed"],
            "independent_inference_replay": inference["passed"],
            "frozen_sources_unmodified": source_integrity["passed"],
        },
        "medical_truth": False,
        "generalization_validated": False,
        "allowed_conclusion": verification["allowed_conclusion"],
        "prohibited_conclusions": verification["prohibited_conclusions"],
    }
    (args.output / "delivery_verification.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = f"""# C — 30_SAMPLE_OVERFIT_TRAINING_V1

状态：**{'PASS' if verification['passed'] else 'FAIL'}**

本交付只验证一个受控命题：冻结的 RGB-only 训练管线能否记住 30 张工程合成图，并将预测二维点接入冻结的 Depth→相机三维坐标路径。它不验证泛化、医学准确性、真实相机或机器人执行安全。

## 冻结数据合同

- RGB/Depth/Mask/Camera：`2026-08-28_20-21-54`
- 当前20点派生 labels：`2026-08-29_16-21-55`
- 样本：30/30 一一配对，20点顺序一致。
- `medical_truth=false`、`medical_validated=false`。
- 模型唯一输入是权威 RGB；overlay、Depth、Mask、labels、sample/profile ID 均禁止进入模型。
- GT 深度取样：`floor(u), floor(v)`，不插值、不搜索邻近有效像素；GT 600/600 通过 3 mm Depth/反投影门。

## 训练结果

- 模型：CPU 上的小型确定性 MLP，RGB 转灰度并缩小至 40×32，直接回归 20 个连续 UV。
- 30张全部用于优化和同集评估；无拆分、无翻转、无增强、无预训练权重。
- 训练轮数：{metrics['epochs_completed']}
- 平均二维误差：{metrics['mean_pixel_error']:.6f} px
- 最大二维误差：{metrics['max_pixel_error']:.6f} px
- 同集 PCK：{json.dumps(metrics['pck_same_set'], ensure_ascii=False)}
- 全新 CPU 进程固定种子重跑：{'逐张量/逐预测完全一致' if determinism['passed'] else '未通过'}
- 独立加载模型推理重放：{'预测逐值一致' if inference['passed'] else '未通过'}
- 两份冻结源交付完整性：{'全部哈希一致' if source_integrity['passed'] else '未通过'}

## 预测 UV → Depth → 3D

- 有效：{three_d['valid_3d_count']}/{three_d['point_instance_count']}
- 无效深度：{three_d['invalid_3d_count']}
- 平均相机三维误差：{three_d['mean_xyz_camera_error_m']*1000:.4f} mm
- 最大相机三维误差：{three_d['max_xyz_camera_error_m']*1000:.4f} mm
- 预测点取样仍采用 `floor(pred_u), floor(pred_v)`；无效时只记录原因，不借用 GT 深度，也不搜索邻近像素。

## 重要限制

1. 这是同一训练集上的记忆测试，不是泛化测试。
2. 20点是工程参考，医学命名文本不构成医生确认。
3. 当前 RGB 是工程合成质量，阴影噪点明显。
4. 连续 UV 量化到深度像素会带来毫米级误差。
5. 没有真实 RGB-D、畸变、噪声、真人或机器人坐标链验证。

## 主要文件

- `dataset_manifest.json`：不可变样本配对、哈希、输入白名单。
- `gt_uv_depth_contract.json`：GT UV→Depth→3D 的 600 点证据。
- `training_config.json` / `training_metrics.json`：训练配置与同集指标。
- `training_curve.csv` / `training_curve.png`：训练曲线。
- `model_state.pt`：CPU PyTorch 状态与预处理统计。
- `predictions.npz`：预测 UV、目标 UV、二维误差。
- `determinism_report.json`：全新进程重跑的张量、预测和曲线一致性。
- `inference_replay_report.json`：不调用训练循环的模型加载/推理重放。
- `source_integrity_report.json`：两份冻结输入交付的逐文件哈希复核。
- `predicted_uv_depth_3d_metrics.json`：预测 UV 的 Depth→3D 明细。
- `prediction_montage.png` / `visual_evidence/`：只用于验收，未进入训练。
- `verification.json`：最终门禁。
- `delivery_verification.json`：训练、确定性、独立推理与源完整性的汇总门禁。
"""
    (args.output / "README.md").write_text(readme, encoding="utf-8")
    rows = []
    for path in sorted(item for item in args.output.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(args.output).as_posix()}")
    (args.output / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"passed": verification["passed"], "files_hashed": len(rows), "sample_count": manifest["sample_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
