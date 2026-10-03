# 实际视觉检查范围

本记录区分数据选区审查与模型输出审查，不将全量绘图当作全量人工验收。

- 模型执行前，实际看过 BEHAVE 全部 180 原始相机视图及 15 页最终 posterior patch 对照，冻结 ROI；实际查看了 16 个 sequence 的 world-cloud QA 图。
- DMD 实际查看全部 35 页，覆盖 205 图片；只确认 dmd_audit_020 为支撑面上的俯卧裸背。未做临床穴位标注审核。
- 模型执行后重点查看了下面的原始 RGB 叠图与对应公开预测图。全部 105 页新叠图均生成、数量/hash核对；没有声称全部新模型叠图已人工逐页看完。

## 代表性诊断

1. PressurePose S141 / seed1：切向最大移动出现在旧 GV14 标识附近，旧种子不是医学中线点。局部形变与整体轮廓错位应分开看，不能因为点云残差更小就称定位更准。[不含原图的点位对照](figures/p1/S141/seed_1.jpg)
2. BEHAVE Date05_Sub06_stool_sit / t0015.000：K0 Rigid→D 后背距离约 8.20→3.93 mm，held-out K3 约 59.83→60.27 mm，保留输入改善、独立机位退化。原叠图显示可评价后背仅为小块，不能替代整背质量判断。[预测图](figures/p2/Date05_Sub06_stool_sit/t0015.000.jpg)
3. BEHAVE Date03_Sub05_stool / t0019.000：K3 Rigid→D 约 11.15→9.11 mm，T+Pose 约 25.22 mm。方法不是各帧一致排名，原图中身体轮廓仍有偏差。[预测图](figures/p2/Date03_Sub05_stool/t0019.000.jpg)

原 RGB 对照页的位置与全部公开图见[全量索引](VISUALIZATION_INDEX.md)。紫色面与绿色轮廓是预测；青色区域是输出前冻结的后背参考小块，不是数据集真实 Mesh。对应数值可查[全部逐帧元数据](results/p2/ALL_FRAME_EVALUATIONS_AND_METADATA.json)。

## 尚未完成的验收

独立真实穴位位置、真实椎体水平、部署标定精度与机器人执行没有验证。旧点位语义为 HOLD，新规则坐标也是工程代理。即使所有图都人工检查完成，也不会自动升级为上述验收通过。
