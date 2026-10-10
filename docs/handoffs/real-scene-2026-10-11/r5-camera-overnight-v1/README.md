# R5 Camera-only 夜间交付（完成）

目的：固定Official RGB人体，只学习公制Camera；先native GT，随后原可微渲染Z/轮廓扫描监督，最后独立HuMMan B评价。

- [执行计划](NIGHT_PLAN.md)
- [最终报告](FINAL_REPORT.md)：新扫描监督有收益，但未超过Official＋Txyz；暂不替换工程基线。
- [完整逐seed结果](summary/PER_SEED_RESULTS.md)
- [全部可视化入口](VISUAL_INDEX.md)：12张扫描、81张真实，含全部历史fallback。
- [逐帧/逐身份配对](summary)：15组各232帧，无删除。
- [当前状态](EXECUTION_LEDGER.json)
- [首批9组训练](NATIVE_INITIAL_REPORT.md)：三个头×三个seed，均30epoch；这只是native Camera误差。
- [恒定特征问题与修正](NORMALIZATION_FIX.md)：历史结果保留，不偷偷改评价。
- [原渲染器与TRAIN权重QA](WEAK_SUPERVISION_FREEZE.json)
- [运行代码](../../../../research/rgbd_sam3d_mhr/r5_camera_only)

原始数据、完整Mesh和checkpoint在218及本地核验备份。未把合成Camera误差当真实表面/穴位精度，未读取封存TEST，B不拟合或选择模型。AutoDL完成备份后已执行关机命令；218保持开启。计划窗口提前完成，未为凑时长追加训练。
