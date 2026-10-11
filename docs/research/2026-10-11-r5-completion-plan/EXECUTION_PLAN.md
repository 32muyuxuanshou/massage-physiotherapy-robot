# 完整 R5 与旧模型新数据公平对照：执行计划

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: plan（按用户已明确的研究目标提出具体方案）
- Origin Date: 2026-10-11，Asia/Shanghai
- Verification Status: FORMAL_RUNNING；完整R5与七组GPU主路径QA通过，14/14 LR筛选完成，21单元正式训练队列已启动；最终效果尚未完成
- Version Label: r5_completion_comparison_plan_v1
- 起点提交：`18706b04cea85e3b8877df9d62498126eb4d2d25`
- 当前授权边界：用户已回复“可以，执行”。代码完成即自审，检查通过自动进入小验证和正式队列，无需每阶段重复申请。当前进度以新增执行交付目录为准。

## 1. 本轮要得到什么

**实现完整的“冻结 Official Body + 公制粗定位 + 可见几何细精修”，再让新旧架构在同一套新数据上完成训练、验证、Depth 消融和真实开发集评价。**

主要问题：完整 R5 是否比旧融合模型、R5 粗定位版和 Official＋Txyz 更稳、更准，细精修是否提供额外价值？不是以训练跑通、梯度非零或某个最好 seed 作为成功。

新模型主结果直接使用模型输出，不外挂 Txyz。Official＋Txyz保留为工程强基线；若给新模型补 Txyz，仅放独立误差诊断表。

## 2. 已有证据和必须处理的差异

1. 上轮实际是 `r5_camera_only/camera_head.py` 的汇总特征 MLP，仅预测 XYZ 平移，未实现 fine、局部对应或方向可观测性处理。
2. 上轮 mixed 的真实 HuMMan VAL 四人 raw 表面指标为 45.08 / 34.19 / 33.67 mm，Official 为 30.59 mm；尚未形成稳定优于 Official 的证据。
3. 上轮保存的 3,480 份新模型原生输出保持 Official Body 不变，因此新增恶化不能归因于这轮新产生的 Pose/Shape 改变。原 Body 本身的误差仍存在。
4. 实际输入有效深度比例：native TRAIN 中位约14.42%，scan TRAIN约17.13%，真实开发集约2.85%。真实注册深度的稀疏采样和空洞与合成不同；该比例还混入人体占画面大小，不是纯传感器质量。
5. 新 scan 的 `prepare_scan.py` 最终只保存 pooled RGB 和全套 Body 的 compact NPZ。**旧融合模型需要空间 backbone 特征图、prepared batch 和完整 crop Depth/rays，不能拿 compact 1280维汇总特征冒充旧模型输入。**
6. `fusion_r4.py` 的 G0 使用与现有 `fusion.py` 相同的 Cross-Attention，未开启 metric Camera。相同输入/训练合同下合并为一组；先用固定样本检查两入口等价。

证据：[完整 raw 审计](../../handoffs/real-scene-2026-10-11/r5-raw-error-analysis-v1/ERROR_ANALYSIS.md)、[历史训练设计](../2026-10-10-rgbd-training-loss-audit/TRAINING_DESIGN.md)、[当晚实际计划](../../handoffs/real-scene-2026-10-11/r5-camera-overnight-v1/NIGHT_PLAN.md)。

## 3. 完整 R5 的实现范围

```text
RGB → 冻结 Official backbone / decoder / MHR
      ├─ 原生 Body、姿态、体型、尺度、整体旋转 → 原样保留
      ├─ 初始位置 t0
      └─ RGB 空间特征图 → Camera 分支读取

Depth + 已知 K + person mask
      → 公制 XYZ / rays / 局部相对形状
      → 粗定位网络 → t_coarse = t0 + Δt_coarse

固定 Body + t_coarse
      → 原 K 透视渲染：可见面、深度、法线、轮廓
      → 在相同投影位置读取实测 Depth / RGB 空间特征
      → 局部几何残差编码 → fine Δt
      → 几何可观测方向处理
      → t_final

输出 = 原生 Official Body + t_final
```

### 粗定位

- 保留绝对公制 XYZ，同时提供中心化局部形状和相机 rays；不能把 Z 全部归一化后丢掉绝对距离。
- 使用有效人体点的固定预算采样和小型 point-set encoder，加 RGB/Body/K 汇总特征，预测三轴平移残差。点数预算建议2,048，先检查几何和实际吞吐后冻结。
- 不再直接把“crop内有效像素比例”当主要位置特征；该量保留在 QA/分组报表。训练同时改变采样密度，防止把稀疏程度当成距离。
- 深度分位数、点云中心不是 MHR root 真值，网络需学习观测表面与人体 root 的关系。
- 本轮“R5 coarse-only”与完整 R5 共用上述粗模块；旧 pooled MLP 保留原结构，并在相同新数据上重训，区分数据升级与粗模块升级的作用，不混成相同架构。

### 细精修

- 粗对齐后，用原 K 和真实 crop affine 建立可见对应。建议先使用256个固定面/重心表面查询，实际可见数量和对应失败均记录。
- 输入包含预测表面位置、法线、对应观测 XYZ、axial-Z 残差、ray、投影位置、有效标记及该处 RGB 特征；保留局部结构，不压成一个深度中位数。
- 使用共享小 MLP 和集合聚合输出一次 fine 平移。粗、细各前向一次，没有6次配准迭代，不把 Txyz 嵌入新模型。
- 查询只读取当前相机前表面，并处理遮挡/无深度；不让背部观测任意匹配到腿或背面。未命中比例单独报告。
- **可观测性按方向处理。** 法线近共线时主要缺少切向约束，不能把整个 fine 向量清零。深度残差贡献可按法线矩阵的特征方向衰减；切向证据由粗分支和图像轮廓提供。系数由解析平面/曲面 QA 与 TRAIN 小验证确定，并在正式训练前固定。它是几何约束，不新增 learned uncertainty/confidence head。
- 先验证不加方向处理的 fine，检查方向处理的影响再冻结正式版本；两版本都保留记录，不能看 Camera B 后选择。

### 明确保持的边界

Body 不接收 Depth 特征，不只依赖 `detach()` 声称隔离。原生参数保持数值相同；不训练 Pose/Shape/Scale/global rotation，不增加自由顶点形变，不解冻全部 Decoder，不加入穴位模型。

文献支持的是公制量与相对几何分离、射线表示和几何监督，并不证明本设计必胜：[MoGe-2 §3.2](https://arxiv.org/html/2507.02546v1#S3.SS2)、[UniDepth](https://arxiv.org/abs/2403.18913)。透视与轮廓梯度复用已核查的 [nvdiffrast](https://nvlabs.github.io/nvdiffrast/)；局部查询和方向处理是本项目待验证的设计。

## 4. 数据：沿用身份，更新输入质量，不临时混标签

|数据|TRAIN|VAL|用途与标签边界|
|---|---:|---:|---|
|原生 MHR 合成|400身份 / 3,200图|50身份 / 400图|真实 MHR 参数、对应顶点、Camera GT；每身份2姿态×4相机|
|HuMMan textured scan 重渲染|9身份 / 2,304图|3身份 / 768图|有纹理、背景、64种相机配置；提供可见扫描表面/Depth/轮廓，不提供原生 MHR root、Pose/Shape真值|
|真实 HuMMan 已消费开发集|18人 / 192帧|4人 / 40帧|两部分均为迁移评价，不作为本轮监督训练；A输入，固定B点独立评价|

- 总计5,504张合成 TRAIN、1,168张合成 VAL；不合并不同数据集的分数。多相机图不是新身份或新姿态。
- native 的50身份 / 400张 TEST 继续封存。若要最终正式 TEST，在所有方案/超参数冻结后另列一次评测；本轮开发不读取。
- 保留全部464张 scan 截断图，按距离、视角、光轴旋转、焦距和截断情况分组；不删除失败图。
- 当前扫描人物主要穿衣，不等同于俯卧裸背皮肤。PressurePose/BEHAVE历史数据不偷偷并入本轮训练；本轮成功也不直接等于最终俯卧部署成功。

### 深度输入升级

保留 clean 几何标签，用相同合同为所有模型生成输入噪声/空洞：

1. 根据已有设备标定和真实 TRAIN Camera A 的观测统计，模拟深度传感器采样，再注册到 RGB 网格；保持原 RGB、K、bbox/affine 的物理对应。
2. 组合稠密、注册稀疏、随机/结构空洞、边界缺测和轻度深度噪声。噪声参数只从 TRAIN A 或事先指定设备合同取得，不从 VAL/B误差调参数。
3. 稀疏采样应保持保留下来的公制点坐标不变。不能用错误 K、随意缩放 XYZ 或补洞后的 Depth 当真值。
4. 固定 seed→sample→epoch 的增强计划，所有模型读取相同版本；保存输入版本与SHA。拍摄几何和输入噪声的变化分开记录。
5. 注册质量验证后统一导出完整空间缓存。native 旧完整缓存可检查后复用；scan 需补导出 spatial features、batch、Depth、valid、rays；不重渲染已完成的全部RGB。

输入升级会改变实验合同，使用独立版本目录，保留原数据和原模型。密度单项消融与整体升级区分，不能把所有提升都归因于架构。

## 5. 公平比较哪些模型

|组|结构|人体输出是否可能改变|正式种子|
|---|---|---|---|
|Official|冻结官方模型|原始人体|固定推理基线|
|Official＋Txyz|原历史配准|只平移|固定拟合与点集|
|RGB-only adapter|旧RGB适配器，无Depth输入|可能改变|11 / 23 / 37|
|RGB-D Spatial Residual|旧空间残差融合|可能改变|11 / 23 / 37|
|RGB-D Cross-Attention / G0|旧全局跨模态Attention|可能改变|11 / 23 / 37|
|G1|旧Cross-Attention＋raw Camera hook|可能改变|11 / 23 / 37|
|现有 R5 pooled MLP|上轮metric_xyz小Camera头，结构不变|保持Official|11 / 23 / 37|
|R5 coarse-only|本轮公制粗定位|保持Official|11 / 23 / 37|
|完整 R5|相同粗定位＋可见几何fine|保持Official|11 / 23 / 37|

**七个可训练组×三个seed，共21个正式训练单元。**现有MLP的三组重训成本小，但能检查是否只是新数据带来提升。G0不当作另一架构重复计算。此前未正式确立的G2/G3不自动扩线。

- 旧架构保留，不用新 R5 头替换后继续沿用旧名字；统一新数据读取与扫描弱监督入口。
- 除已冻结 Official 权重外，从对应适配器的新初始化开始；不让新R5复用训练50轮的旧头而让旧模型从零开始。
- 三seed的 R5 coarse/full 可共享各自seed第一段相同粗定位预热；共享算力/训练步骤明确列账，不重复宣称独立训练。
- RGB-only 可以使用Depth作为训练标签，但推理输入不包含Depth、valid mask或camera rays特征；沿用相同person bbox/prompt。
- Official没有训练seed。每个seed表都列同一冻结基线；若重复推理，实测其非确定性，不伪造三次训练。

## 6. 损失、训练充分性与模型选择

### 标签分配

- native：共同使用公制 Camera 与对应 MHR 几何监督。旧模型保留原来的Body参数监督；R5的Body固定，这些项只监控、不产生可训练Body梯度。
- R5 coarse/final均以原生 Camera GT监督，避免final全救回、coarse任意漂移。Camera Smooth-L1沿用beta0.05m。
- scan：所有可训练组使用相同可见axial-Z与轮廓监督；没有MHR参数标签，不伪造root/对应顶点GT。RGB-only只把它们用作标签。
- 几何损失使用原透视渲染器。可见共同命中深度、命中率、全mask未命中情况分别记录；不能用减少命中点来换漂亮分数。
- 旧native十项损失的形式和权重先保留，修正后公共几何项按逐图归一化。共同深度/轮廓权重使用固定TRAIN批次校准并冻结，不给每个模型看B结果后单独调权重。新coarse/final权重也在TRAIN小验证后冻结，完整披露。

本轮不是“所有模型损失梯度完全相同”的实验：人体可训练范围本来就是架构变量。必须同时报告Camera、局部Body、去平移与最终Camera-space Mesh误差，区分位置和人体变化。

### 统一排程（建议，执行前固化）

1. LR短筛：每组同样比较`1e-4 / 3e-4`，固定筛选seed7、相同5轮native数据，依据synthetic VAL选择；seed7不计正式三seed结果。记录范围有限，不能声称全局最优。
2. 正式每组50轮：native30轮＋native/scan混合20轮。AdamW、weight decay1e-4、clip1、2轮warm-up及cosine；两段调度和重启方式统一冻结。
3. 有效native batch16；mixed每轮完整覆盖3,200 native和2,304 scan，分开microbatch积累。不能继续随机scan4/step却写成每轮全scan训练；每轮scan完整无放回遍历，同时记录分组曝光。
4. R5 full：native前10轮仅预热粗定位；其后20轮启用fine，再混合20轮。coarse-only对应同一前10轮起点，保持native曝光和后续数据顺序一致。
5. 每轮保存last，改善时保存best，另保留关键里程碑。checkpoint统一以native VAL身份等权的Camera-space对应顶点L2选择；Camera L2、scan VAL和真实B指标另报告。**与上轮只用Camera L2选checkpoint的合同不同，必须明确记录。**
6. 每组同样报告best/last、末5轮变化、训练/验证差距与LR曲线。50轮是预算，不等同于已证明收敛；若需追加，只在真实B评测前基于synthetic VAL统一执行规则并披露。

混合多数据不是将loss直接无归一化拼起来，也不以training scalar大小判断梯度是否由某项主导。记录各项实际输出梯度，特别注意穿衣扫描和固定Body的冲突。

## 7. 代码自审与推进顺序

|阶段|具体动作|进入下一步的证据|
|---|---|---|
|A 资产和数据准备|核实218环境/权重/空间；完整缓存；噪声输入QA；冻结数据版本|对应、单位、K/crop合同、清单SHA及备份通过|
|B 实现完整R5与旧模型入口|coarse、fine、几何方向处理；旧模型scan入口；公共评价/保存|完整前向、loss与预测输出实际可运行|
|C 立即自审|检查数据流和梯度、Body隔离、可见对应、代码diff|无具体阻塞；保留审查记录；失败则只修根因|
|D 小验证和吞吐|固定少量TRAIN/VAL；平面/曲面射线QA；不同距离/稀疏度；一张GPU实测|无坐标/泄漏错误、可恢复训练、fine有效且不篡改Body|
|E LR筛选＋21单元训练|旧模型和R5全部新合同；按GPU/内存安排并发|完整best/last、3seed曲线与实际训练曝光|
|F 冻结后的评价/消融|逐数据集评价；正确/扰乱/缺失/偏移Depth；全部失败保留|逐人/逐帧/逐seed结果；数量对账|
|G 交付与备份|图表、报告、代码配置、Git及私有大包|至少计算服务器和本地独立副本校验；完整索引|

用户批准计划后，C/D通过自动运行E–G；不因一般性的理论风险反复停住，也不跳过真实已发现的坐标、数据泄漏或Body隔离错误。

审查重点仅针对本轮主链：

- RGB-only不会读Depth输入；R5 Body路径完全不接收Depth或Camera-head梯度。
- 零初始化/禁用新头时复现Official；新 Camera只应用一次。
- Scan无伪MHR GT；Camera B与TEST不会进入训练、LR/权重/架构选择。
- 同一个crop/K单位、输入增强、固定评价点；透视深度和法线方向正确。
- 截断/稀疏/无命中案例不静默删掉；从保存网格独立重画，不重新拟合。
- checkpoint恢复模型、优化器、调度器和RNG；备份实际读文件SHA，不只记路径。

## 8. 最后怎样评价“哪个好”

三份互不混算的主表：

1. **native合成VAL**：GT Camera XYZ/L2、对应顶点L2、去平移误差、关节、Pose/Shape/Scale；按距离/视角/缺测分组。
2. **scan合成VAL**：可见表面/axial-Z共同命中median/P95、命中率、轮廓IoU；固定评价点和各方法共同命中对照。无命中仍保留，但不能把Z=0差值解释为实际2米表面误差。
3. **真实HuMMan**：固定232帧A输入，B2048点精确点到三角面；TRAIN18人与VAL4人分表。frame→sequence→identity等权，保留P95、50mm覆盖、逐身份/逐seed和所有恶化帧。

深度消融固定RGB/K/prompt，包含正确Depth、同相机条件下的身份错配、同身份姿态错配、局部扰乱、缺Depth、公制Z偏移，以及仅采样密度变化。错配不能同时随意换rays/valid，否则无法识别Depth数值的作用。

所有组分开画整体位置、姿态/体型改变量、局部残差和运行耗时。特别保留p001194/p001195/p001196/p001199以及p100089等已有失败案例，不能只画效果好的人。

主排名使用raw输出。需要回答：

- 完整R5是否在三个seed上稳定超过coarse-only？fine在稀疏、斜视、近距情况下是否仍有价值？
- 新模型相比Official＋Txyz，有没有准确度、失败率或速度上的实际收益？不能只比未修正Official。
- 旧模型若赢，收益来自Body改善还是位置恢复？是否伴随P95/身体异常代价？
- 结果是否只在合成数据好，在真实仍恶化？若如此先保留工程基线，不宣布部署可用。

真实数据没有原生MHR对应GT，点到面改善不是解剖对应、穴位精度或临床接触安全证明。

## 9. 服务器、工期与备份

- 优先`172.18.6.218:436`，账号`xuhd`；历史核实8×2080Ti，执行时重新查可用GPU/CPU/内存/磁盘，不默认当前空闲。
- 旧模型需要解码器反向传播与渲染，冻结权重不等于无激活显存。先做20–50步真实吞吐测试，选择microbatch/梯度积累；优先一GPU一训练任务，小头按实测可并发。不把8卡显存说成单卡88GB。
- AutoDL只在有当前有效授权且确有需要时使用，不自动新租或开付费GPU。用户未要求时不自动关机。
- 工期预估：代码/完整缓存与审查约1–2天，小验证与LR筛选约半天；21个正式单元的GPU时间在吞吐实测后给出，不用上一轮小MLP的速度估旧模型完整解码训练。可独立阶段并行，以进度优先。
- 新服务器工作目录建议`/raid5/xuhd/rgbd_sam3d/r5_complete_comparison_v1`；本地私有备份`E:/项目-按摩理疗机器人/output/r5_complete_comparison_v1`。不得覆盖旧R3/R4/R5结果。
- 第一次改代码前记录旧commit和资产SHA；数据完整缓存生成后做索引/清单备份；每epoch本机保存last/best/状态，每5轮或关键checkpoint同步独立本地副本，训练完成同步全部best/last和评价原始输出。
- 计算机与218是不同副本；若实际在AutoDL运行，结果同时转218与本地。218同盘复制不能冒充异机备份。
- Git提交代码、配置、划分/输入合同、报告、曲线和可展示图；原始数据、授权权重、私人Mesh大包和checkpoint不直接入Git。公开记录备份包路径、大小和SHA回执，不公开密码/token。
- 每阶段留下execution ledger：正在做什么、何时开始结束、失败/恢复、完整或部分、所用commit、环境和真实完成数量。最终报告明确本轮未完成项，不能用计划代替结果。

原计划已经获准执行。运行状态、实测QA和与计划的实现差异见 `docs/handoffs/real-scene-2026-10-11/r5-complete-comparison-v1/README.md`；本文保留原始实验目标，结果不能用计划代替。
