# PARALLEL_A_B_C_F_V1

本目录是 2026-08-31 获用户授权的并行工程门。它只协调 A/B/C/F 四条内部研究线，不修改正式插件、canonical SKEL、正式 Atlas、用户 Blend 或既有交付包。

## 冻结输入

- 场景与 RGB-D：`outputs/交付文件/2026-08-28_20-21-54`
- 当前20点工程参考 Atlas 与派生标签：`outputs/交付文件/2026-08-29_16-21-55`
- 增强单维 Shape 分析：`outputs/交付文件/2026-08-30_19-24-33`

三份输入必须按 `baseline_manifest.json` 验证；任何哈希变化都终止下游实验。

## 工作流边界

- A：`candidate_shape_combination_v1/`，只写多 beta 组合验证代码和 A 线输出。
- B：`enhanced_pose_only_v1/`，只写 Pose-only 诊断代码和 B 线输出。
- C：`overfit_training_v1/`，只写30样本清单、转换、训练和评估代码及 C 线输出。
- F：`qa_infrastructure_v1/`，只写 truth/schema/provenance、自相交和统一验收工具及 F 线输出。

各线不得修改其他线目录。共同输出根为 `outputs/交付文件/2026-08-31_13-36-44/`，各线使用独立子目录。

## 真值边界

当前 E01-E20 是 engineering reference，强制：

```text
medical_truth = false
medical_validated = false
```

源 Atlas 的历史 `medical_status` 文本不构成医生确认，且不得传播为医学真值。

## 允许的结论

- A 只能形成固定俯卧场景限定的 qualified Shape profiles。
- B 只能形成 beta=0 限定的 qualified Pose profiles。
- C 只能验证训练管线能否记住30个工程样本，不能声称泛化或医学准确。
- F 提供验收门，不产生医学结论。

D 真实相机和 E 医生 Atlas 本轮未获授权，不启动。

## 最终状态（2026-08-31）

- A：PASS，冻结 baseline + 6 个组合 Shape；1 个组合因工程点二环邻域重叠被拒。
- B：PASS，beta=0 下冻结 9 个 Pose；2 个因局部重叠、1 个因固定床面穿透被拒。
- C：PASS，30 图 RGB-only 同集过拟合和预测 UV→Depth→3D 闭环通过；不证明泛化。
- F：PASS，三份基线、A/B/C 哈希、工程真值隔离、测量合同与局部自交门均通过。

权威机器可读结果见 `outputs/交付文件/2026-08-31_13-36-44/`。A/B 中标为 diagnostics、superseded 或 `FAILED_DO_NOT_DELIVER_*` 的运行只用于解释已修复问题，不是现役结论。
