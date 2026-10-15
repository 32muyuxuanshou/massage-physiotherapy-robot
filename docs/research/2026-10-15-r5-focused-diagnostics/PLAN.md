# R5 集中诊断计划

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: plan
- Origin Date: 2026-10-15 Asia/Shanghai
- Verification Status: OFFLINE_DIAGNOSIS_COMPLETE_GPU_TIMING_DEFERRED；2,706 条同 Full Coarse/Fine、232 帧 A-only 刚体对照、400 帧原生参数替换已完成
- Version Label: r5_focused_diagnostics_plan_v1

## 本轮问题与范围

解释现有 R5 Full Last 相对 Official+历史 Txyz 的差距，并判断下一项改进应针对更新方式、观测对应还是整体朝向。不以获得更漂亮的数值为完成标准。

使用既有 Last checkpoints，seeds 11/23/37。保留原始结果、权重、样本、点集、评价器和历史 Txyz；不训练、不增加新模块、不重选 Best、不读取封存 TEST，不直接比较 M³ 排名。

这些分析属于已消费开发证据的诊断，不是全新测试。新的假设应在后续独立人群验证。

## 数据与实际可用性

|数据|样本与角色|主指标|用途|
|---|---|---|---|
|Native MHR|50 个 VAL 身份、400 图；TEST 不读|Camera 向量误差、对应顶点误差；两者分开|有原生参数真值的定位/朝向诊断|
|真实 HuMMan|TRAIN 18 人/192 帧；VAL 4 人/40 帧分开|固定 Camera B 2048 点到精确三角面|独立视角几何诊断，A-only 拟合|
|BEHAVE|既有 3 人/90 序列/270 帧|绝对 PVE；固定 K1/K2/K3 观测支撑距离|拟合参考与独立观测分开，保留物体/异常深度限制|

三份数据不合并成一个总毫米值。三 seed 对相同受试者的重复，不算新增受试者。

已检查本地 `output/r5_complete_comparison_v1/final_html/EVALUATION_EVIDENCE.json`：Full Last 的真实数据 records 保留 `camera_xyz_m` 及 `diagnostics.coarse_camera/fine_delta/fine_raw_delta/eigenvalues/visible_queries`。

保存代码表明 Native NPZ 也保存诊断字段；BEHAVE NPZ 使用 `trace_` 前缀。它们的实际字段与逐文件 SHA 须在提取缓存时核对，不以代码存在代替实际缓存核验。

BEHAVE 完整本地卷位于 `output/behave_model_comparison_v1/final/BEHAVE_R5_PRIVATE_DELIVERY.tar.gz`，已核对大小 8,561,981,134 字节；已有完整 SHA 回执。Native/HuMMan 几何输入按既有私有备份索引提取。只提取所需文件，不展开整个数据盘。

2026-10-15：最初连接被拒绝，用户随后恢复原 AutoDL 无卡模式，并明确选择“先保持无卡，先做离线诊断”。实际配额 0.5 核 CPU /2 GiB，CUDA 不可用。服务器只提取已有缓存及进行轻量 MHR CPU 参数重新解码；全量三角面评价在本地 CPU 完成。完整 GPU 计时按用户要求暂缓。

## Q1：同一个 Full 的 Fine 改善了什么

从每个 Full Last checkpoint 自己的输出构造两个结果：

1. `Full_internal_coarse`：同一个冻结身体 + 该 Full 的 `t_coarse`。
2. `Full_final`：相同身体 + `t_coarse + delta_fine`。

独立训练的 `coarse` 模型不能代替 `Full_internal_coarse`。先检查相机组合与原保存结果一致，再用相同评价点和原评价器计算二者。

逐帧记录 coarse/final/Txyz 的平移向量、Fine 前后指标、每轴相对差值、修正范数、可见 Query 数及法线特征值；正负收益按每项指标分别报告。Txyz 的向量仅是基线结果，不是真实 Camera 标签。

只有 Native 可用 `t_GT - t_coarse` 分析 Fine 的方向夹角、平行分量及正交分量。初始误差接近数值零的样本不计算不稳定的幅度比例，仍保留原始误差。真实数据不以“朝向 Txyz 的比例”判定真实方向正确。

Fine 负收益可能来自错误对应、无效/稀疏观测、回归偏差、训练目标、方向衰减或域差异；Query 数和特征值的关联只作线索，不直接判定因果。

## Q2：整体旋转是否存在可恢复价值

### Native：真值参数替换诊断

在冻结内部关节、体型和尺度的条件下比较 Official、仅替换真实平移、仅替换真实整体旋转、同时替换二者。整体旋转按现有原生 MHR/XYZ 合同重新生成，不在已经包含整体旋转的顶点上重复乘旋转。

报告 Camera、对应顶点及去平移误差，不能把参数替换称为对该指标的全局最优。错误身体在真实平移下未必获得最小顶点误差。

### BEHAVE：拟合参考下的对齐诊断

利用固定 MHR→SMPL 对应，比较去平移与去平移加刚体旋转；尺度固定。若使用最小二乘/Kabsch，明确它优化平方距离，报告其对应的 PVE，不能声称取得平均 L2 的精确最优。

参考只用于离线诊断，不进入预测、A-only 拟合或 checkpoint 选择。已有 PA-PVE 包含尺度，不能直接代替这里的旋转贡献。

### HuMMan：可实现的 A-only 拟合

保留历史 Official+Txyz。追加匹配的平移/刚体拟合作为旋转对照：相同 Official 初值、A 点集、anchors、对应方向、修剪原则与迭代预算；固定尺度，记录全部最终变换和失败。

具体实现和任何新增约束在执行前定稿，不使用 B 的结果挑参数。B 始终仅评价。判断要区分旋转自由度的影响与优化器/约束变化的影响。

单个刚体基线未改善，只能说明该算法与观测条件下收益未建立，不能证明旋转永远无效或冻结旋转全局最优。

## Q3：真实耗时与失败分布

现有代码记录的 cached-head 时间不代表完整系统速度；原始推理入口的首次时间还含初始化，不能直接作为稳定运行耗时。

在相同设备、输入和 batch=1 下，持久加载模型，完成预热与 GPU 同步；比较从已解码 RGB-D 到最终 Mesh 的完整延迟。预处理、官方 Backbone/Decoder、附加 Camera 分支或 Txyz 分别计时，同时报告完整 median/P95 延迟、显存以及 CPU/GPU 配置。文件读取/模型加载时间单列。

计时样本在看到新诊断结果前固定，包含正常与既有失败案例，不只测最好的一帧。尚无完整 GPU 测量时不填速度数字，不宣称 R5 更快。

精度报告全部帧 CDF 和逐人表；HuMMan TRAIN/VAL 分开。原始 fallback、负收益和 P95 失败全部保留，分组解释不从主分数剔除样本。

## 聚合与判断

- Native：图像→身份；HuMMan：帧→序列→身份；BEHAVE 的 PVE 按原主表帧等权，同时列序列/人物结果，观测支撑按 camera→frame→sequence→subject。
- 三 seed 分别报告，再给均值/标准差；不把 seed×frame 当独立受试者扩大样本量。
- 不预设“50%～70% 欠修正”等未经观察的成功模式。不新增事后阈值，不用一个总分决定架构。
- 初步支持欠修正时，多步更新只是下一项候选；负收益与错误对应有关时，先验证原因再考虑筛选；真实 A-only 刚体收益稳定时再列 SE(3)。允许多个原因并存或仍不能判定。
- “合成与真实存在差异”是已有观察；“扫描监督造成 Last 的全部收益”“首次发现通用干扰机制”等因果与新颖性结论仍未建立。

## 交付与结束条件

交付一份 HTML/Markdown 报告、三份互不混算的逐帧/逐人表、Fine 修正方向与收益图、旋转诊断表、完整耗时表及全部失败索引。缓存及输入用原实际 SHA 标识；新诊断在独立目录，不覆盖原结果。

完成标准：可以指出证据最强的瓶颈及其适用条件，并列明剩余未知项；不要求必须得出唯一原因或必须胜过 Txyz。

已完成固定 11 条首批核验后运行全量；A-only 刚体对照也先核验三个固定帧。训练成本为零；完整延迟测量仍需要可用 GPU，本轮没有替代成缓存 Head 计时。结果见 [本轮交付](../../handoffs/real-scene-2026-10-15/r5-focused-diagnostics-v1/README.md)。

新增刚体合同在评价 B 前保存：相同 16,384 anchors、固定 A 点、六轮、80% 保留；匹配的均值平移与固定尺度 Kabsch 对照使用相同步长和平移范数上限。旋转围绕初始 Mesh 质心，超平移上限时整个刚体变换回退。历史中位数 Cheap Txyz 独立保留。这个新增对照是诊断，不替换历史算法。
