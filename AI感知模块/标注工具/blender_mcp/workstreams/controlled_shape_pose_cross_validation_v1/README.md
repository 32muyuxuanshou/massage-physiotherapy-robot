# CONTROLLED_SHAPE_POSE_CROSS_VALIDATION_V1

受控验证 7 个已冻结 Shape 与 9 个已冻结 Pose 的 63 格候选矩阵。

- 15 格是既有 baseline/Shape-only/Pose-only 回归对照。
- 48 格是真正未验证的 Shape×Pose 交互组合。
- Camera、Bed、Light、Material、刚性俯卧变换、20 点 engineering Atlas 与 RGB-D 数据合同保持冻结。
- 先运行 6 个 Smoke 与恢复/重复门；通过后才运行完整矩阵。
- Geometry preflight 通过后才导出 RGB-D。
- 完整证据写入 `outputs/内部工程证据/`；`outputs/交付文件/` 只生成 GPT 网页端精简审查包。

硬门：控制链、拓扑/绑定、冻结场景、固定床面间隙 `>=3 mm`、工程点二环邻域零重叠。三环或父项之外的新全局重叠只进入 `CAUTION`，不得自动当成合格组合。

当前 E01–E20 仍是工程参考点，不是医学穴位；本工作流不产生医学、完整人体零自交、真实床垫或机器人安全结论。

## 实际结果（2026-08-31）

- Smoke：PASS；6 个高风险格、基线恢复和高风险重复运行均完成。
- 63 格几何预检：全部成功分类，无系统错误、无床面硬拒绝、无二环邻域硬拒绝。
- 分类：3 `QUALIFIED`、44 `CAUTION_THREE_RING_INTERSECTION`、16 `CAUTION_NEW_GLOBAL_OVERLAP`。
- 3 个合格项仅为 `S0_BASE__P0_BASE`、`S0_BASE__P3_ELBOW_22`、
  `S0_BASE__D05_LUMBAR_BENDING_P4`；真正新交互合格数为 0。
- RGB-D：3/3 PASS；全新原生生成与 Blender 进程确定性：3/3 PASS；`R_BASE`：PASS。
- 最终阶段：FAIL。预设门禁要求至少 1 个真正新交互组合合格，不能用对照项替代。
- 完整内部证据：
  `outputs/内部工程证据/2026-08-31_15-07-27_CONTROLLED_SHAPE_POSE_CROSS_VALIDATION_V1/`，
  `SHA256SUMS.txt` 为 540/540 通过。

下一步不是放宽门禁，而是对新增重叠做窄相位/区域诊断和参数回退搜索，再生成新的候选矩阵。
