# BEHAVE / R5 对照：无卡准备交付

日期：2026-10-13。状态：**全部无卡准备完成；等待用户开启原实例 GPU。** 本页不是模型精度结果。

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

GPU 开启后先运行 `run_benchmark.py --scope smoke`；确认原生输出、Body 保留、三 seed 对照和评价结果正常，再运行 `--scope formal`。无卡准备不运行这两个命令。

RGB 核查图和原始数据仅保留本地/私有服务器；Git 不上传原始图像、人体资产和权重。正式 HTML、全部失败可视化、完整几何评价及最终备份尚未完成。

## 当前不能下的结论

尚未得到本轮任何新模型 PVE；不能说 R5 已超过 M³、Official 或 Official+Txyz。BEHAVE 不是专门的俯卧床上数据，不能把本轮结果当成按摩穴位精度。
