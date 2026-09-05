# LOCATOR_CAPACITY_COMPARISON_V1

第一步只在冻结的 `POSE_HOLDOUT` 上比较 TinyHeatmapNet 与 RTMPose-S。

- 数据、train/val/test sample ID 和 E01–E20 顺序保持不变；
- 输入为相同的 160×128 RGB；
- 不使用 Depth、Mask、ID 或医学标签；
- 关闭水平翻转和额外增强；
- RTMPose-S 不使用预训练权重，先隔离模型容量差异；
- 本轮仅是非医学合成工程筛选，不建立机器人安全结论。

## 执行结果

`PASS_CANDIDATE_WITH_TAIL_RISK`：RTMPose-S 在 `POSE_HOLDOUT` 的 1,174 个可见点上达到
2.144 px mean / 4.844 px P95。它优于 Tiny 的 expectation decoder，也优于冻结的
`BOUNDARY_HYBRID_V1` 的 mean/P95，但在 `C2_EDGE_CROP` 留下 7 个大于 20 px 的离群点，因此尚未
晋升为替代模型。

完整结果位于：
`outputs/内部工程证据/2026-09-02_17-58-03_LOCATOR_CAPACITY_COMPARISON_V1/`。

## 后续受控修正

7 个尾部错误被确认是同一边界覆盖空洞的外观重复。加入一次冻结的对称微平移训练增强后，三条
Holdout 均完成：Combination / Shape / Pose 的 mean 分别为 1.837 / 2.200 / 1.830 px，P95
分别为 3.937 / 4.462 / 4.112 px，所有 `>20 px` 错误均为 0。Shape mean 仍比 Tiny
Boundary Hybrid 差 13.1%，所以只冻结为下一合成阶段候选。

权威结果位于：
`outputs/内部工程证据/2026-09-02_19-48-21_RTMPOSE_SHIFT_AND_THREE_HOLDOUT_V1/`。
