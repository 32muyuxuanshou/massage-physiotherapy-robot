# 2026-10-05 恢复服务器后的两阶段交付

**实际训练、迁移、作图和缓存重算均完成。没有新的SAM推理或Mesh拟合。**

1. [真实体表线训练报告](../../real-scene-2026-10-04/surface-line-completion-pilot-v1/results-v1/FINAL_REPORT.md)：20训练/4开发/6已消费评价来源，两策略×三初始化，各120轮。缺失条件作者线差异6.99→4.15 mm，六来源均改善。
2. [俯卧迁移完整报告](FINAL_REPORT.md)：原20人、360曲线、1080绑定包、9720ENG点。与历史沟槽共同12人绑定输入跨度25.41→16.66 mm；完整16人相对普通模型13改善、3退化；不同初始化间仍15.17 mm。
3. [全部20人图](figures/INDEX.md)、[逐人CSV](PER_SUBJECT_RESULTS.csv)、[完整机器结果](RESULTS.json)。图中的点是工程探针；跨度是稳定性，不是穴位误差。
4. [运行与核验](EXECUTION_LEDGER.json)、[实际源网格/曲线核验](CACHE_VERIFICATION.json)、[本地缓存重算](CACHE_REPLAY_VERIFICATION.json)、[收尾范围](CLOSEOUT_RECEIPT.json)。

服务器：`xuhd@172.18.18.151:436`。学习运行根：`/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004`，迁移运行根：`/raid5/xuhd/datasets/prone_learned_reference_transfer_v1_20261005`。权重在学习根`checkpoints/`；原始照片在迁移根`private_rgb/`，不进入公开Git。

训练实际约11分钟，迁移推理约41秒；人工审查与交付另计。现役状态统一见[CURRENT_STATUS](../../../CURRENT_STATUS.md)。当前可作为离线工程基线，不能作为治疗穴位定位或论文强结论。
