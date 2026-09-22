# Rule-first 穴位工程流程执行报告 V1

## 结论

已完成一个可复现的工程闭环：同一份规则合同在 canonical MHR 与 B1–B5 预测 Mesh 上计算背部工程点，并把每个目标投影到固定的后背候选表面。6 个样本均输出 8 个规则点，`RULE_OUTPUT_QA` 检查通过。

这不是医生验证，也没有证明穴位定位准确率。所有结果保持 `ENGINEERING_PROXY_ONLY`、`medical_truth=false`。

## 运行资产

- 规则：`RULE_ENGINE_CONFIG_V1.json`
- 规则计算：`rule_engine.py`
- 代理参考框架生成：`make_proxy_landmarks.py`
- 批量 sanity：`run_rule_engine_sanity.py`
- 规则与旧 topology seed 对照：`compare_rule_and_transfer.py`
- 结果目录：`rule_sanity_v1/`

每个样本保存 `PROXY_LANDMARKS.json` 与 `RULE_OUTPUT.json`。输出字段包括规则目标、表面坐标、face index、barycentric、surface normal、投影距离和未校准 confidence 状态。

## 坐标合同的修正

canonical MHR 与 B1–B5 prediction mesh 的纵向/侧向坐标方向不同。本轮没有静默翻转坐标，而是将 `vertical_order` 与 `lateral_sign` 写入代理参考框架。这样工程结果可追溯；后续真实输入必须由 Mesh/相机坐标合同提供同样的信息。

## 结果如何使用

`RULE_ONLY_GEOMETRY_SANITY_V1.json` 的 projection distance 只表示“规则目标到候选表面”的几何投影距离；`RULE_ONLY_VS_TRANSFER_GEOMETRY_V1.json` 只表示“规则代理点”和“旧 atlas seed topology 点”的分歧。两者都不能解释为穴位误差、医生一致性或机器人安全阈值。

## 后续工作

工程链先继续完善 Mesh 质量、坐标变换、可视化和机器人接口。等流程稳定后，再引入医生或独立真人标注，替换代理参考框架并决定是否需要 landmark/visibility/residual 学习模块。
