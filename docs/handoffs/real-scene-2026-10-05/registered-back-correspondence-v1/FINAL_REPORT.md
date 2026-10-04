# 注册后背表面身份：实际机制对照

**结论：真实注册扫描上的表面身份可以学习；当前局部/先验设计有小幅增益，尚不是论文主贡献。直接query decoder没有超过对应场反查，不采用为精度改进。**

## 实际完成

服务器下载FAUST_r/SCAPE_r及vts四包，37,835,581 bytes，SHA/文件清单完整；100 FAUST、71 SCAPE全部解析。原数据不进Git。主实验仅FAUST：60来源训练/20开发/20保留考试，900程序观测case、9模型×1200steps、1800次模型评价，训练346.90秒、评价19.25秒。

模板000后背区域472个共享参考采样；每人沿注册对应裁同区域。9×3预设query近邻去重后实际26个。vts是共享样本到每份网格的1-based索引，有重复，**不是MHR顶点映射**。作者编号划分沿最后20份网格，不称20独立受试者。

## 相同局部输入的主对照

| 条件 | 方法 | 观测点canonical median | 可见query身份median | 可见query当前表面位置median | query身份P95 |
|---|---|---:|---:|---:|---:|
| FULL | TEMPLATE_NN | 9.126 | 8.778 | 9.106 | 12.854 |
| FULL | POINT_GLOBAL | 2.141 | 2.274 | 2.286 | 4.028 |
| FULL | PRIOR_GLOBAL | 1.991 | 1.848 | 2.053 | 3.629 |
| FULL | PRIOR_LOCAL | 1.944 | 1.657 | 2.042 | 3.445 |
| PARTIAL_BAND | TEMPLATE_NN | 9.087 | 8.192 | 8.317 | 12.777 |
| PARTIAL_BAND | POINT_GLOBAL | 2.164 | 2.222 | 2.177 | 4.000 |
| PARTIAL_BAND | PRIOR_GLOBAL | 2.024 | 1.783 | 1.959 | 3.779 |
| PARTIAL_BAND | PRIOR_LOCAL | 1.956 | 1.570 | 1.774 | 3.466 |
| NOISY_PARTIAL | TEMPLATE_NN | 9.088 | 8.281 | 8.777 | 12.947 |
| NOISY_PARTIAL | POINT_GLOBAL | 2.143 | 2.127 | 2.212 | 4.129 |
| NOISY_PARTIAL | PRIOR_GLOBAL | 2.035 | 1.828 | 2.020 | 3.546 |
| NOISY_PARTIAL | PRIOR_LOCAL | 1.959 | 1.716 | 1.637 | 3.413 |

单位都是相应单位面积坐标下的距离×100（%sqrt(area)）；**不是mm、测地距离或穴位误差**。完整网格均值/面积用于输入归一化，强于现实单相机条件。后背分割从注册对应取得，是oracle ROI。PARTIAL/NOISY为程序缺失/噪声，不是真实RGB-D测量。

FULL→PARTIAL的点身份误差基本未明显增大，说明这套较轻的缺失合同本身不够困难，不据此宣称真实遮挡鲁棒。部分条件query可见率中位79.49%，未见query不进入定位分数，覆盖单列。

PRIOR_LOCAL相对POINT_GLOBAL在PARTIAL可见query中位2.222→1.570，但强参考与其接近。仅“比近邻强”不足以支持顶会方法主张。

## 作者强参考（额外完整上下文）

DiffusionNet作者HKS checkpoint、commit b1019b0、原functional-map流程实际执行，21份完整网格/180个观测索引对照，实测59.54秒。FULL可见query1.739，PARTIAL1.699，NOISY1.699；完整扫描未受到程序噪声，因此后两者相同是合同的结果。它训练80来源且看到完整几何；与本轮60训练/局部输入不公平，单列支持，不混入主汇总。没有复制GT进入作者forward（vts placeholder为空）。

## 连续query架构对照（同20考试来源已消费）

| 条件 | 查询网络 | query身份median | 当前表面位置median | query身份P95 |
|---|---|---:|---:|---:|
| FULL | Q_GLOBAL | 2.089 | 2.155 | 3.812 |
| FULL | Q_PRIOR_LOCAL | 2.021 | 2.193 | 3.770 |
| PARTIAL_BAND | Q_GLOBAL | 1.996 | 2.030 | 3.777 |
| PARTIAL_BAND | Q_PRIOR_LOCAL | 1.904 | 1.982 | 3.672 |
| NOISY_PARTIAL | Q_GLOBAL | 2.020 | 2.010 | 3.883 |
| NOISY_PARTIAL | Q_PRIOR_LOCAL | 1.915 | 1.980 | 3.759 |

6个query模型实测训练280.77秒/评价18.86秒；1080评价、24048个查询绑定；随机训练query，不是26类分类器。Q_PRIOR_LOCAL的PARTIAL1.904弱于既有身份场反查1.570，保留失败。Face/bary绑定在作者观测扫描上，不是预测SAM/MHR表面，不作为机器人放行。

## 复查与边界

- 主预测1800缓存逐个实际打开并hash，9000数值检查通过；全部900冻结输入/原代码保持不变。
- 查询1080缓存与实际源顶点/三角面角点绑定核验通过，source unchanged，缓存指标exact。
- 完整RESULTS、逐来源CSV、20来源全部指标图、训练/评价ledger、原数据下载inventory、作者结果和全部运行代码在本目录；带几何/标注的缓存与权重仅服务器，路径/hash都可追踪。
- 论文RINO和DV-Matcher已下载，实际读摘要/方法及主架构图；不是全篇附录逐页读完，不声称RINO已复现（作者页Code soon）。
- FAUST与SCAPE原许可限制非商业研究；当前仅学术机制实验。产品训练/部署不能直接继承该数据权利。
- 尚无MHR↔FAUST可靠身份转换、俯卧临床GT或真实部署传感器。没有新SAM推理/训练，没有治疗点放行。

## 下一项已开始的方向

改成模板条件的成对描述子：模板任意query→当前观测候选。该设计不依赖FAUST固定canonical坐标或假设两数据集的vts行跨库同义。用FAUST训练、SCAPE独立的库内对应考试，检验更换模板能否工作，再决定是否进入MHR/俯卧研究接口。

服务器：`xuhd@172.18.18.151:436`；根目录`/raid5/xuhd/datasets/registered_human_correspondence_20261005`；大资产限服务器。

来源：[DiffusionNet数据/作者基线](https://github.com/nmwsharp/diffusion-net/tree/master/experiments/functional_correspondence)，[FAUST与许可证](https://faust-leaderboard.is.tuebingen.mpg.de/license)，[RINO](https://arxiv.org/abs/2603.27773)，[DV-Matcher](https://openaccess.thecvf.com/content/CVPR2025/html/Chen_DV-Matcher_Deformation-based_Non-rigid_Point_Cloud_Matching_Guided_by_Pre-trained_Visual_CVPR_2025_paper.html)。
