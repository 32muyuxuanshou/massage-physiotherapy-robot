# R5 Camera-only 夜间交付（进行中）

目的：固定Official RGB人体，只学习公制Camera；先native GT，随后原可微渲染Z/轮廓扫描监督，最后独立HuMMan B评价。

- [执行计划](NIGHT_PLAN.md)
- [当前状态](EXECUTION_LEDGER.json)
- [首批9组训练](NATIVE_INITIAL_REPORT.md)：三个头×三个seed，均30epoch；这只是native Camera误差。
- [恒定特征问题与修正](NORMALIZATION_FIX.md)：历史结果保留，不偷偷改评价。
- [原渲染器与TRAIN权重QA](WEAK_SUPERVISION_FREEZE.json)
- [运行代码](../../../../research/rgbd_sam3d_mhr/r5_camera_only)

原始数据、完整Mesh和checkpoint在私有服务器目录。正文未把合成Camera误差当真实表面/穴位精度，未读取封存TEST，B不拟合或选择模型。最终结果尚未完成。
