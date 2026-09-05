# ENGINEERING_PILOT_V1

基于已冻结的 17 个 Shape×Pose、正常主相机和 Camera 可见性兼容表，建立约 360 张非医学工程 Pilot。

执行顺序：

1. `freeze_pilot_contract.py`：冻结兼容采样、精确配额、三种分组拆分、可见性损失、RGB 外观变化和数据 schema；
2. `build_pilot_dataset.py`：复用已验收的几何/Depth/Mask/labels，只生成确定性的 RGB 外观变体；
3. `qc_pilot_dataset.py`：验证配额、无 C4 训练泄漏、分组拆分、文件哈希、可见点 Depth 和标签合同；
4. `train_pilot_baseline.py`：分别运行 Combination/Shape/Pose holdout 的 RGB→2D heatmap 基线；
5. `finalize_pilot.py`：汇总 Failure Map、内部证据和审查包。

`C4_SELF_OCCLUSION_STRESS` 只进入 challenge，不进入主 train/val/test。E01–E20 仍是非医学工程点。

## 2026-08-31 结果

- Freeze：360 个主样本 + 12 个 C4 challenge；三种 split 均通过 case/sample 无泄漏检查。
- Dataset QC：360/360 主样本、12/12 challenge 通过；372 张 RGB 唯一；可见点最大 Depth 误差
  2.909 mm。
- `COMBINATION_HOLDOUT`：平均 2D 误差 3.212 px，平均 3D 误差 6.012 mm。
- `SHAPE_HOLDOUT`：平均 2D 误差 3.353 px，平均 3D 误差 6.281 mm。
- `POSE_HOLDOUT`：平均 2D 误差 4.400 px，平均 3D 误差 8.193 mm。
- 最大 3D 误差仍为 69–86 mm；C4 challenge 平均 2D 误差为 185–202 px，均不可用于机器人安全结论。
- 组合留出基线的第二次完整训练与第一次在预测数组、模型张量、曲线和指标上精确一致（排除耗时字段）。

权威目录：

- Freeze：`outputs/内部工程证据/2026-08-31_19-54-55_ENGINEERING_PILOT_DATASET_FREEZE_V1/`
- Dataset：`outputs/内部工程证据/2026-08-31_19-57-10_ENGINEERING_PILOT_DATASET_V1/`
- Training/Evaluation：`outputs/内部工程证据/2026-08-31_20-05-31_ENGINEERING_PILOT_BASELINE_V1/`

下一候选门是受控验证右侧裁切和中/下背遮挡；本 workstream 不自动启动该门。正式插件、canonical
SKEL、Atlas、用户 Blend 和发布 ZIP 未修改。
