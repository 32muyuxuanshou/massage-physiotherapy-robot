# 四参考点辅助表面对应 V1

固定上一轮60个D_VECTOR表面，比较固定拓扑、4个精确参考辅助、4个参考带5 mm扰动；仅4个未输入点进入主要评价。这是oracle工程对应诊断，没有临床或部署准确率。

- [最终报告](FINAL_REPORT.md)、[执行前合同](PROTOCOL.md)、[机器可读配置](CONTRACT.json)
- [完整汇总](AGGREGATED_RESULTS.json)、[180条方法结果](PER_CASE_RESULTS.csv)、[1440逐点记录](PER_PROBE_RESULTS.csv)、[逐人配对](PAIRED_CHANGES.csv)
- [60个完整case](runs)、[4点输入](inputs)、[分开的评价真值](evaluation_truth)
- [全部60页图](figures/INDEX.md)、[全案例比较](figures/ALL_CASE_COMPARISON.png)
- [输入/噪声与配对审计](INPUT_NOISE_AND_PAIR_AUDIT.json)、[K0参考可见性](K0_REFERENCE_VISIBILITY_QA.json)、[解析检查](ANALYTIC_CHECK.json)
- [执行记录](EXECUTION_LEDGER.json)、[结束完整性](POST_EXECUTION_INTEGRITY.json)、[固定表面指标](FIXED_SURFACE_METRICS.json)
- [独立交付数值复算](DELIVERY_NUMERICAL_VERIFICATION.json)、[完整交付哈希](FILES_MANIFEST.json)
- [交付核验说明](DELIVERY_CLOSEOUT.md)
- [实际代码](code)、[冻结基线工具](frozen_baseline_code)、[复现及边界](REPRODUCTION.md)

准确参考有帮助不等于当前系统能自动取得这些参考。三种注入情况、输入点和未输入点分别报告，不把它们混成一个“穴位准确率”。
