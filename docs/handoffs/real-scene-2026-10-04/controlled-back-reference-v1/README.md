# 已知参考几何与绑定点受控验证 V1

本轮回答：深度修正把表面贴准后，同拓扑的工程点是否也回到了已知位置。使用20份既有预测网格作为程序生成参考，精确虚拟相机，三类固定误差，四种方法；没有新SAM推理或训练，不宣称真人穴位精度。

- [最终结论与边界](FINAL_REPORT.md)
- [执行前协议](PROTOCOL.md)、[机器可读合同](CONTRACT.json)
- [完整汇总](AGGREGATED_RESULTS.json)、[240条逐人物/情况/方法表](PER_SOURCE_CASE_RESULTS.csv)、[120条相对Rigid变化](PAIRED_CHANGES.csv)
- [完整逐case输出](results)、[480逐点指标及240工程点坐标](results)、[60套观测索引](observation_indices)
- [全部60页三视图对照](figures/INDEX.md)、[全案例图](figures/ALL_CASE_COMPARISON.png)、[逐点图](figures/PROBE_ERROR_BREAKDOWN.png)、[观察区内平面反例](figures/PLANAR_OBSERVED_BINDING_WITNESS.png)
- [全部8点展开](ENGINEERING_PROBE_RESULTS.csv)、[配对数量及网格质量极值](PAIRED_COUNT_AUDIT.json)
- [解析检查](GEOMETRY_CHECK.json)、[参考表面核验](REFERENCE_SURFACE_ORACLE_QA.json)、[执行后完整性](POST_EXECUTION_INTEGRITY.json)
- [480份指标/240份探针独立复算](DELIVERY_NUMERICAL_VERIFICATION.json)、[32份可交付冻结源字节核验](DELIVERY_SOURCE_IDENTITY_CHECK.json)、[实际视觉复查](VISUAL_REVIEW.md)
- [执行记录](EXECUTION_LEDGER.json)、[环境](EXECUTION_ENVIRONMENT.json)、[240最终缓存索引](FINAL_MESH_MANIFEST.json)、[服务器输出全清单](SERVER_OUTPUT_MANIFEST.json)
- [复现位置、数据流与文件边界](REPRODUCTION.md)、[代码](code)、[实际基线源码](frozen_baseline_code)、[实际法向D源码](frozen_normal_code)

表面距离与同拓扑对应误差分别报告。虚拟held-out视图仅用于已知几何闭环，不替代真实独立RGB-D、可靠解剖点参考或部署验收。
