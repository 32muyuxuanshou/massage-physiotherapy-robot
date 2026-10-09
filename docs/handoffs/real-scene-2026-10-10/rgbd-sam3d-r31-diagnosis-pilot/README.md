# R3.1 完整审查交付

已完成诊断、两个独立候选实际训练、匹配小规模对照、Depth/机制消融和真实Camera B评价。**有Depth响应，但没有证明新候选稳定胜过Official+Cheap Txyz。** R4是另一个授权任务，不混入本轮结果。

从 [FINAL_REPORT.md](FINAL_REPORT.md) 开始。继续看 [RESULT_TABLES.md](RESULT_TABLES.md)、[R31_SUMMARY.json](R31_SUMMARY.json)、[EXPERIMENT_CONTRACT.md](EXPERIMENT_CONTRACT.md)、[ARCHITECTURES.md](ARCHITECTURES.md)、[LITERATURE_DECISIONS.md](LITERATURE_DECISIONS.md)、[REPRODUCE.md](REPRODUCE.md)。

图片：[全部16张新对照](VISUAL_INDEX.md) · [14张历史失败审计](failure_visuals) · [训练曲线](figures/TRAINING_CURVES.png) · [真实独立相机对照](figures/REAL_CAMERA_B_COMPARISON.png) · [Depth来源消融](figures/DEPTH_SOURCE_DIAGNOSTIC.png) · [Cheap Txyz强基线](figures/CHEAP_TXYZ_STRONG_BASELINE.png)。

逐帧全表：`diagnostics`、`pilots`、`ablations`、`real_mechanisms`。点集/身份/配置/hash：`manifests`。训练commit源码：`code_training`；机制干预源码：`code_inference`。没有只给截图或转述数字。

本轮计算和私有原生缓存：`/root/autodl-tmp/rgbd_sam3d/runs/r31_diagnosis_pilot_v1`。完整checkpoint/native输出归档及持久化目标见 `BACKUP_RECEIPT.json`。原始数据、权重和可恢复大缓存不入Git。

服务器继续执行用户后续授权的R4；AutoDL关机放在R4完成/截止并完成备份后，R3.1结束不关机。
