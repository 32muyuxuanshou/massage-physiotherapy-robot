# BEHAVE / R5 对照：科学评价已完成

日期：2026-10-13。状态：**270 帧完整评价、1,620 张可视化与三维查看数据已完成；运行后完整性和本地重聚合核验通过。大文件两卷备份正在传输，最终异机回执尚未完成。**

## 正式交付入口

- [最终报告与独立分析](FINAL_REPORT.md)
- [审计版 HTML（下载后打开）](results/BEHAVE_R5_最终对照_审计版.html)
- [30 个组合的完整汇总](results/AGGREGATED.json) · [8,100 条逐帧表](results/PER_FRAME.csv)
- [全部原始数值结果](results/raw) · [配对失败与回退归因](results/INTERPRETATION.json)
- [运行后实际完整性](results/POST_EXECUTION_INTEGRITY.json) · [实际 checkpoint 轮次](results/CHECKPOINT_EPOCHS.json)
- [异常支撑点：原像素/深度/拟合参考](results/WORST_REFERENCE_SUPPORT_AUDIT.json)
- [全部图片索引与数值](visualizations/VISUALIZATION_MANIFEST.json) · [三维查看索引](results/VERTEX_VIEWER_MANIFEST.json)
- 用户本机已打开私有查看入口：`http://127.0.0.1:8779/`，通过 SSH 连接 AutoDL；双方 HTTP 均仅绑定 localhost，没有公开原始图片。

三 seed 平均：Official PVE **97.64 mm**；Official+Txyz **56.24 mm**；R5 Full Best **89.57 mm**，Last **61.06 mm**。R5 Last 改善位置并保留身体；还没有稳定超过强基线。Best/Last 分开，未用 BEHAVE 重新选 checkpoint。

**观测距离仅按原冻结支撑点诊断。** 数据包含物体/遮挡和异常原始深度，部分 P95 接近 2.8 m；拟合参考也对同点集出现极大残差。全部分数和失败保留，没有事后删点。不能解释成纯人体、裸背或穴位精度。

## 本轮执行进展

- RTX 6000D（实际报告显存 85,651 MiB）已核验可用，没有新增实例、训练或更换 checkpoint。
- 6 帧 × 30 评价组合，共 180 条结果；24 个训练 checkpoint 共 144 个原生预测。R5 Coarse/Full 的 72 个预测、12 项 Body 字段与 Official 实际逐数组相等；加平移误差为零；评价点及参考 SHA 一致。
- 27 个 CPU 评价任务在 8 路并行重算后，与串行 `RESULTS.json` 的实际 SHA **27/27 完全一致**。正式采用 8 路独立评价；算法、样本、点集、聚合、阈值及权重均未改变。
- 首批三 seed 平均表面距离：Official 20.01、Official+Txyz 20.30、G1 Best 24.89、R5 Full Best 35.34 mm。**这是两个 Sub03 序列的 6 帧核验，不是 270 帧结论，不据此调参或换样本。**
- 已生成首批 36 张全部 seed / Best–Last 叠图，以及三维对应顶点查看器。图片是缓存网格生成；不重新拟合。全部正式图片及最终 HTML 将在完整评价后生成。
- 固定 270 帧的 Official 三次重复和 24 个训练模型组合均已完成；8,100 条评价记录齐全。运行前/后实际资产、科学配置和输入清单检查通过。
- 新增的物体遮挡核查仅诊断，不删除测试点：首帧 K1 的 730/2,048 个评价点投影位于官方 rendered object mask 内；这种 mask 含遮挡重叠，不能直接判定所有点都误标。提示背包/衣物表面与潜在人体表面并非同一对象。

[首批数值](smoke/AGGREGATED.json) · [实际完整性](smoke/POST_EXECUTION_INTEGRITY.json) · [并行一致性](smoke/PARALLEL_SCHEDULE_QA.json)

## 已实际完成

- 从官方 Date03 ZIP 按字节读取所需文件，没有重新下载 44.89 GB 整包。270 帧、90 个官方 TEST 序列全部覆盖，包含四机位 RGB/Depth/person mask、拟合 Mesh/参数及必要标定。
- 目标文件共约 1.050 GB（包括序列元数据和标定）；所下载文件完成原 ZIP CRC 和实际 SHA256 核验。首次连接被远端中断，保留已完成文件；续传重新 CRC 检查并复用已有文件，没有改样本。
- 三个身份：Sub03 105 帧、Sub04 105 帧、Sub05 60 帧。90 个序列属于官方 TEST 子采样；不是更多人物，也不是全部未见身份。与历史 45 帧清单重合 25 帧。
- 24 个 checkpoint：RGB-only/G1/R5 Coarse/R5 Full × seeds 11/23/37 × Best/Last。服务器实际 SHA 与本地实际 SHA、既有 218 备份回执一致。没有选择新 checkpoint 或训练模型。
- 3 个已有 Sub03 帧 × K0–K3 的真实坐标核查通过：与直接导入的官方 `KinectTransform` 最大数值差 `3.552713678800501e-15 m`；传感器点重投影的最高逐相机 P95 差 `9.94772849670926e-05 px`。
- 参考 Mesh 为 6,890 顶点 / 13,776 三角面；不调用重新拟合，不改顶点顺序。四相机云的 broad sanity 通过，不能解释为毫米级外参精度。
- 首批 6 帧及完整 270 帧 CPU 输入均已实际生成。重新打开 810 个 input/reference/heldout 文件并核验 SHA、布局及 A-only 模型输入，全部通过；每个 held-out camera 均固定 2,048 点。
- 正常路径自检 3/3：ZIP 解压/CRC；针孔 RGB/轴向 Z 与固定点索引；按帧均值和按序列→人物均值确实分开计算。Python 语法检查通过。

上述极小差异是代码数值和像素对应的一致性，不是人体模型误差，也不是皮肤/穴位真值精度。拟合参考与观测顶点之间仍有厘米量级差别，QA 不将它当成精确皮肤。

## 冻结的评价

主方法为 Official、Official+R3.1/R4.1 Cheap Txyz、G1、R5 Coarse、R5 Full，另加 RGB-only 训练控制。Best 和第 50 轮 Last 分开列，全部保留三个 seed。

- 主指标：固定官方 MHR→SMPL 映射，逐帧 6,890 个对应顶点平均 L2，再按帧等权平均；补充序列→人物等权。
- 身体几何诊断：去质心平移 PVE、PA-PVE。只平移的 R5/Txyz 必须保持去质心 PVE，不能宣称改好了身体。
- 独立表面证据：K1/K2/K3 各 2,048 个固定原始传感器点到精确三角面；camera→frame→sequence→subject，每层等权均值。
- K0 最多 5,000 点可用于 Txyz；B/C/D 和拟合参考只用于评价，分别保存在独立 NPZ。新模型不加 Txyz。
- M³ 的 93.1 / 70.9 mm 只列论文报告参考，分别注明未/已在 BEHAVE TRAIN 微调；作者对齐、采样和汇总细节未确认，不宣称同协议排名。

本轮统一使用 K0 去畸变 RGB（LINEAR）、registered axial Z/mask（NEAREST），目标 K 保持官方值；dataset-mask bbox 外扩 25 px，并使用同样的 mask 输入。独立点云仍由原始 ray table 得到。此处理与旧 distorted-RGB 实验有区别，也不能推定与 M³ 的前景处理相同。

## 执行位置与代码

- AutoDL：`/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1/`
- 原始子集：`data/sequences/`；冻结选帧：`data/FROZEN_INPUT_MANIFEST.json`。
- CPU 输入：`inputs/`；首批六帧：`inputs_smoke/`。参考/held-out NPZ 与模型输入分开。
- 现有权重：`/root/autodl-tmp/rgbd_sam3d/runs/r5_complete_comparison_v1/formal/`。
- [执行代码](../../../../research/behave_metric_alignment)；[完整计划](../../../research/2026-10-13-behave-model-comparison-plan/PLAN.md)。

已依次完成 `--scope smoke` 和固定 `--scope formal --evaluation-workers 8`。科学计算未重跑；画图采用通过 36 张实际 JPEG SHA 等价验证的独立范围并行调度，见 `VISUALIZATION_EXECUTION_REVISION.json`。

RGB 和原始数据留在本地/私有服务器；Git 不上传原始图片、人体资产、权重和大型 NPZ。正式 HTML、全量可视化及几何评价已完成。两卷备份分别保存全部实验资产、6 个运行资产与 24 个 checkpoint；正在进行 Windows/218 实际 SHA 核验。后续监控只收尾备份，不追加训练或关闭服务器。

## 当前不能下的结论

不能说本轮严格超过 M³、已经解决身体几何或达到按摩穴位精度。BEHAVE 不是专门的俯卧床上数据；M³ 的对齐/采样/前景协议尚未完整确认，不能按两个不同协议的毫米值排名。
