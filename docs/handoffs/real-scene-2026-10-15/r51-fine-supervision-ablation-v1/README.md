# R5.1：固定Coarse，验证Fine监督与步长正则

本轮实际完成4组×3seed×6轮有限续训、21个唯一选中状态的502帧独立评价，共10542条记录。没有改Body、Coarse、网络结构或原点集，没有给新模型加Txyz。

**主要结论：Camera监督有取舍，但简单降权并未带来实质突破。** 权重0.5只有微小真实收益；完全去掉Camera监督和本次L2均没有稳定的真实优势。按批准的有限预算结束，没有自动组合、扩训或进入R6。

- [直观HTML：分数据集、三seed、三种选模、失败图](reports/R51_监督消融完整结果.html)（GitHub不直接运行HTML，可下载整个目录本地打开）
- [结果总表](reports/FINAL_REPORT.md)
- [大白话分析、逐人核查与下一步判断](reports/ANALYSIS.md)
- [自审与限制](reports/SELF_AUDIT.md)
- [复现步骤与服务器路径](code/REPRODUCE.md)

## 结果：相同6轮预算的Last，三seed均值

|组别|Native对应顶点L2 mm|Native Camera L2 mm|Scan全mask轴向Z median mm|HuMMan VAL B表面median / P95 mm|BEHAVE三机表面median / P95 mm|BEHAVE拟合参考PVE mm|
|---|---:|---:|---:|---:|---:|---:|
|原Full Last父模型|94.524|20.610|52.332|14.359 /44.549|19.827 /83.583|59.640|
|E0 原监督匹配续训|94.332|20.710|52.627|14.246 /43.995|19.682 /83.388|59.403|
|E1 Camera权重0.5|89.189|27.403|52.737|14.202 /43.957|19.640 /83.268|59.193|
|E1 Camera权重0|84.639|45.762|52.856|14.356 /44.516|19.791 /83.466|59.136|
|E2 仅加L2|94.752|21.198|53.510|14.455 /43.966|20.137 /84.158|60.287|

HuMMan VAL历史Official+Txyz为11.226247mm，本轮最好均值仍约14.2mm，没有追平。不同数据集的指标定义不同，禁止混成一个总体毫米误差。

Camera权重0.5相对E0：HuMMan VAL median只改善0.044mm（3/3seed），P95只改善0.038mm（2/3seed）；BEHAVE独立表面改善0.041mm（2/3seed）。不能把这称为稳定的大幅方法升级。删掉Camera使合成顶点改善，但HuMMan VAL median/P95三seed均退化；BEHAVE拟合PVE变好与独立传感表面变差可以同时出现。

原Fine负收益帧仍然存在。[分类转移表](reports/CLASSIFICATION_TRANSFERS.json)同时报告救回与新弄坏：例如Native Camera，权重0的当前坏帧为226/222/224，父模型原67/68/72。只报救回数量会误导。该Camera标签不是独立表面标签。

## 配对实验合同

- Seeds11/23/37分别继承原Full Last；同seed四组共享Coarse、Body、Query、Fine初值和每轮数据顺序。不是3次从头训练。
- E0是固定Coarse后的Fine匹配续训，不是原50轮joint训练复现。
- E0 Camera权重2；E1_half代码名沿用，实际权重0.5（是原来的四分之一）；E1_zero为0；E2保持原权重，加全局公制delta L2。
- L2 λ=0.5933867854225844，仅TRAIN32 Native+32 Scan的初始最后层梯度标定到基准10%，没有用B选系数，没有小残差噪声阈值假设。
- 仅更新rgb_local/local/fine_head；AdamW lr1e-4，weight decay1e-4，clip1；Native16+Scan24，micro4，32step/epoch，6epochs。
- Native Camera SmoothL1 β=.05m，Z β=.02m，Z/轮廓权重.2/.2；Scan Z/轮廓1.0664188982/4.6202386224。loss完整数学实现见[core.py](code/core.py)。

## 数据与隔离

|域|训练|本轮评价|性质|
|---|---|---|---|
|Native MHR合成|原TRAIN哈希固定64身份×8=512张|原VAL50身份400帧|有原生MHR、对应顶点与Camera真值|
|纹理Scan合成|原TRAIN 9身份中按asset×camera-group比例固定768张|原VAL 3身份768视图|扫描表面深度/轮廓，无伪造Camera GT|
|HuMMan真实|本轮不参与训练|原TRAIN18人192帧＋VAL4人40帧|A输入，固定B点独立评价，已消费开发集|
|BEHAVE真实|本轮不参与训练|3人270帧旧官方TEST子集|K0输入，K1/2/3评价，已消费；拟合SMPL仅支持|

父模型此前见过完整400个Native训练身份及完整Scan训练集，不能说模型从来只见过本轮子集。Native/HuMMan封存TEST未读；BEHAVE已消费官方TEST子集明确保留，不以含糊的“TEST完全未读”掩盖。

Native/Scan的共同命中、全mask、命中率、IoU均保留；未命中Z=0进入full-mask惩罚。HuMMan/BEHAVE使用历史精确点到三角面评价器，B完全不用于拟合、训练或checkpoint选择。Body冻结，本轮误差变化来自最终平移，不是Pose/Shape变准。

## 选模、口径与旧报告对账

旧Best：最小Native身份等权顶点误差。联合Best：Native/Scan分别相对初始值的全mask Z median，两个比值等权，要求各域IoU和命中率≥初始−.01。0/2/4/6轮可选，包含epoch0，平分取早。两套规则在真实评价前冻结，Last同样完整报告，没有事后指定有利主规则。

指标先逐帧计算，再frame→sequence→identity各层等权。BEHAVE每帧先三相机等权；Scan为frame→camera-group→asset→identity。表中的P95是逐帧P95的层级均值，不是合并全体点后的P95。

**旧61.06与本轮59.64不是一次新改善。** 原Full Last在BEHAVE的逐帧值相符，旧61.0638为帧均值，本轮59.6396为序列/人物等权。Official+Txyz对应56.2400/55.7337。两者都保存在[对账JSON](reports/AGGREGATION_RECONCILIATION.json)，没有修改评价点或偷偷改模型。

## 完整审查索引

- [冻结配置](code/EXPERIMENT.json)、[数据划分与来源hash](evidence/DATA_MANIFEST.json)、[训练科学文件冻结](evidence/SCIENCE_FREEZE.json)、[选模冻结](evidence/SELECTION_FREEZE.json)。
- [代码主路径QA](evidence/PREFLIGHT.json)、[48次原模型重装QA](evidence/FULL_FORWARD_REINSERTION_QA.json)、[旧评价器先导QA](evidence/REAL_EVALUATOR_PILOT.json)、[结束后二次完整性](evidence/POST_INTEGRITY.json)。
- [全部训练曲线与逐轮参数记录](reports/TRAINING_ALL.json)、[完整梯度账本](reports/GRADIENT_LEDGER_ALL.json)、[全部合成逐epoch结果](synthetic_validation)。
- [合成分域三seed汇总](reports/SYNTHETIC_RESULTS.json)、[真实分域三seed汇总](reports/REAL_RESULTS.json)、[全部10542真实逐帧记录](reports/REAL_JOBS.json)。
- [逐人末轮表](reports/PER_IDENTITY_LAST.json)、[部位proxy](reports/REGION_LAST.json)、[配对逐帧CSV](reports/PAIRED_REAL_FRAMES.csv)、[全部负收益转移CSV](reports/CLASSIFICATION_TRANSFERS.csv)。
- [Native逐帧CSV](reports/NATIVE_FRAME_RESULTS.csv)、[Scan逐帧CSV](reports/SCAN_FRAME_RESULTS.csv)、[失败选例规则](evidence/FIGURE_SELECTION.json)。
- [历史评价器原代码](historical_code)、[当前代码](code)、[实际环境](evidence/EXECUTION_ENVIRONMENT.txt)。

POST_INTEGRITY实际重读27503文件、84个权重并核验10542预测与对应评价。数据准备阶段发现Scan缺失，随后补齐；[DATA_READY](evidence/DATA_READY.json)记录解决链，原MISSING回执保留。

## 备份与下一步

计算与原始资产位于218：`/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1`；Windows备份：`E:/项目-按摩理疗机器人/output/r51_fine_supervision_ablation_v1`。三卷TRAINING_CHECKPOINTS.tar.gz、PREPARED_FINE_INPUTS.tar、R51_FINAL_RESULTS.tar.gz的实际SHA见evidence中的BACKUP_RECEIPT三份回执。原始数据、权重、NPZ不入Git。

本轮结束，不自动叠加正则或扩大训练。保留原R5与0.5候选，后续若获批准，应以更具体的观测对应/几何信息假设推进，避免继续凭小幅权重收益包装创新。当前没有验证真正俯卧后背、解剖或穴位精度，也没有完整端到端GPU耗时证据。服务器保持开启。
