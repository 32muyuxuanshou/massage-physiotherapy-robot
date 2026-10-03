# Back Geometry / Correspondence V2

已执行，2026-10-03 启动、2026-10-04 完成。旧交付 `fa054c5` 不覆盖。

主结论：法向 D 减少切向移动，但距离略差于原 D，轮廓/网格质量及种子波动仍存在；保留为基线。BEHAVE 新 cohort 未满足资格，不运行新模型。没有训练或医学标签。

- [最终报告](FINAL_REPORT.md)
- [执行总账](EXECUTION_LEDGER.json)
- [复现、服务器与本地路径](REPRODUCTION.md)
- [全量图与 RGB 复核入口](VISUALIZATION_INDEX.md)
- [实际视觉检查与限制](VISUAL_REVIEW.md)
- [新 8 点 atlas](results/a_atlas/ENGINEERING_BACK_ATLAS_V2.json)
- [BEHAVE 资格不足结论](results/b_qualification/COMMON_SUPPORT_COHORT_LIMITS.json)
- [四方法聚合](results/c_pressure_normal/AGGREGATED_RESULTS.json)
- [逐人结果](results/c_pressure_normal/PER_SUBJECT_RESULTS.csv)
- [实际执行源码](code/)、[原基线源码快照](frozen_baseline_code/)、[旧审计工具快照](frozen_audit_code/)
- [60 个原始划分索引](indices/)、[240 份逐点距离/射线指标](per_point_metrics/)、[240 份缓存元数据](cache_metadata/)
- [运行后源与缓存核验](results/c_pressure_normal/POST_EXECUTION_INTEGRITY.json)
- [服务器产出文件清单](SERVER_OUTPUT_MANIFEST.json)、[原图可视化位置](SERVER_PRIVATE_VISUAL_MANIFEST.json)
- [公开包边界](PUBLIC_DATA_BOUNDARY.json)、[交付文件 SHA 清单](FILES_MANIFEST.json)

原始 RGB/Depth/点云、native MHR 资产、权重与大型最终网格 NPZ 不入 Git。公开黄点是中性 ENG 预测探针，不是临床穴位；紫色填充与绿色轮廓均为同一个预测 Mesh。
