# RTMPOSE_RELIABILITY_V1

为三条冻结 RTMPose-S 定位器分别重建 availability 与 BAD30 拒答模型。复用
`RELIABILITY_DATASET_GATE_V1` 的 24 个新 Shape–Pose 人体及其预冻结 12/6/6
train/calibration/untouched 分区，不复用 Tiny 的模型、特征合同或阈值。

当前 E01–E20 仍为非医学工程点；本门只允许得出合成工程可行性结论。

## 结果

状态：`PASS_SYNTHETIC_RTMPOSE_RELIABILITY_FEASIBILITY_V1`。

- 三条定位器各自训练 availability 与 BAD15，共 6 个逻辑回归模型；
- train/calibration/untouched 按人体保持 12/6/6，不跨定位器池化；
- 未触碰测试的接受率为 80.00% / 57.86% / 77.98%；
- 接受点中的 BAD15 比例为 2.40% / 4.95% / 1.07%，BAD30 均为 0；
- 独立指标重算和完整推理确定性复跑通过。

权威证据：
`outputs/内部工程证据/2026-09-03_12-03-27_RTMPOSE_RELIABILITY_V1/`。

Shape 分支的 BAD15 接受率接近 5% 上限，仍是后续真实 RGB-D 域门的重点风险。本结论不能推广为医学、
真人或机器人安全。
