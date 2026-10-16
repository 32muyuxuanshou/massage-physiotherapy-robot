# 结果解释与下一步判断

本轮固定Body，只改变平移求解。没有训练、没有新Body能力，也没有对B拟合。下列变化不代表Pose、Shape、解剖或穴位更准。

## 先说结论

1. **直接用完整Txyz替掉Fine，不成立为通用升级。** 同Coarse的密集6步使HuMMan VAL 14.359→12.736mm，但BEHAVE 19.827→21.246mm。BEHAVE seed37退化4.731mm；HuMMan VAL P95也从44.550升到45.322mm。不能只交VAL median。
2. **三维NN不自动优于投影对应。** 在相同Depth格点、相同可见Query、相同一步中位数下，NN相对真实像素投影的误差变化：Native +3.709mm、HuMMan TRAIN +1.771mm、VAL +1.347mm、BEHAVE +2.387mm；四组均3/3seed变差。这否定本对照中“只缺三维最近邻”的解释，不证明所有三维关联方法都无效。
3. **更多Anchor并非总更好。** 256全部相比16384，在HuMMan VAL为11.460对12.736mm；BEHAVE却为21.268对21.246mm。可见子集在HuMMan大幅变差、在BEHAVE改善，说明候选近似、覆盖和方向有明显域依赖，不能统一归因于数量。
4. **点面LS值得留下，但还不是胜出的新模型。** Coarse＋点面LS6步，HuMMan VAL为10.646/42.409mm（median/P95），旧Official＋Txyz为11.226/41.604mm：median略好，P95略差。BEHAVE为18.564/82.194mm，仍弱于旧基线16.524/78.497mm；且BEHAVE seed37比原Fine更差。旧方向衰减在HuMMan仅约0.003mm变化，没有带来新突破。
5. **Coarse的大偏移救回价值保住了。** 原HuMMan 11个fallback帧，在三个seed的Coarse＋历史6步中都不再fallback，子组表面median帧均值降到约12mm。p001195整体从原Fine18.800到12.204mm；但p001196从19.309到19.133mm时P95反而52.150→55.234mm。
6. **顶点更近与Camera参数更准仍有取舍。** Native密集6步顶点94.524→88.375mm，但Camera20.610→44.761mm；点面LS的Camera更到58.610mm。不能把表面拟合量当相机真值。

## 1. 主问题：同Coarse＋完整历史算子能恢复多少

|数据|原Fine|Coarse＋历史6步|Official＋历史6步|相对Fine逐seed变化|
|---|---:|---:|---:|---|
|behave/OFFICIAL_TEST_SUBSAMPLED_PREVIOUSLY_CONSUMED_IDENTITIES|19.827|21.246|16.524|+0.020/-0.494/+4.731|
|native/VAL|94.524|88.375|128.394|-6.269/-5.880/-6.299|
|real/TRAIN|20.524|19.987|24.645|-0.629/-0.151/-0.833|
|real/VAL|14.359|12.736|11.226|-1.212/-2.237/-1.420|

Native为对应顶点均值；真实为独立表面median的层级均值。负变化表示改善。原Fine是Full Last，不能把它写成R5.1 E1的14.20mm。

Native Camera参数误差与对应顶点的相反变化，逐seed/方法见NATIVE_OBJECTIVE_TRADEOFF.json。不能把任何表面较好的平移直接当作Camera GT。

## 2. 逐因子事实

每个数是三个seed的配对差值均值；after减before，负数更好。不是全因子实验，后续对应会随前面更新改变。

|对照|Native顶点|HuMMan TRAIN|HuMMan VAL|BEHAVE独立表面|
|---|---:|---:|---:|---:|
|PRIMARY_fine_to_dense6|-6.149|-0.537|-1.623|+1.419|
|START_official_to_coarse|-40.020|-4.658|+1.510|+4.722|
|STEPS_1_to_2|-3.947|-2.209|-1.408|-1.782|
|STEPS_2_to_3|-1.798|-1.274|-1.150|-1.052|
|STEPS_3_to_6|-1.598|-2.234|-2.146|-1.331|
|COUNT_16384_to_256|-2.027|-1.657|-1.276|+0.022|
|VISIBILITY_all_to_visible|-1.204|+8.401|+6.033|-2.894|
|DIRECTION_o2m_to_m2o|+0.968|-3.428|-4.631|+0.399|
|OPERATOR_median_to_mean|-1.218|-0.993|-0.796|-0.821|
|OPERATOR_median_to_plane|-3.172|-3.108|-2.090|-2.682|
|GATE_plane_to_filtered|-0.085|+0.016|-0.003|-0.112|
|RAY_ASSIGNMENT_query_to_pixel|+0.010|+0.002|+0.001|+0.006|
|MATCH_projective_to_NN|+3.709|+1.771|+1.347|+2.387|
|LATTICE_median_to_mean|-0.999|-0.158|+0.434|-0.180|
|LATTICE_median_to_plane|-4.601|-0.720|-0.437|-1.606|

密集/256改变的是NN的候选Mesh近似；初始可见子集另改变覆盖范围。Mesh→Obs与Obs→Mesh改变配对数量与方向。投影/格点NN控制共享Depth，并分离原Fine将Z赋给Query射线的像素量化差别；但直接中位数更新不是最优投影求解，不能证明投影信息本身的上限。点面LS和衰减的效果也不能从单个例子推广。

## 3. 已知失败身份与P95

|人物|Coarse median/P95|Fine median/P95|Coarse＋历史6 median/P95|Official＋历史6 median/P95|
|---|---:|---:|---:|---:|
|p001195|62.131/105.122|18.800/64.989|12.204/52.070|131.495/177.704|
|p001196|29.595/75.576|19.309/52.150|19.133/55.234|13.118/46.559|

## 4. 原Txyz fallback与初始化范围

fallback上限相对于各自起点。学习的Coarse可先移动超过177.888mm，随后几何修正仍在自身177.888mm内；这不等于几何求解在同一个Official半径内击败旧优化。以下保留原fallback子组，不从总分剔除。

seed11：原fallback 11帧；coarse median帧均值 84.317 mm（本方法fallback 0）；fine median帧均值 20.898 mm（本方法fallback 0）；hist_med6 median帧均值 12.551 mm（本方法fallback 0）；official_hist6 median帧均值 184.250 mm（本方法fallback 11）。

seed23：原fallback 11帧；coarse median帧均值 60.887 mm（本方法fallback 0）；fine median帧均值 17.936 mm（本方法fallback 0）；hist_med6 median帧均值 11.982 mm（本方法fallback 0）；official_hist6 median帧均值 184.250 mm（本方法fallback 11）。

seed37：原fallback 11帧；coarse median帧均值 61.328 mm（本方法fallback 0）；fine median帧均值 20.957 mm（本方法fallback 0）；hist_med6 median帧均值 12.057 mm（本方法fallback 0）；official_hist6 median帧均值 184.250 mm（本方法fallback 11）。

这里是固定fallback子组的帧均值，不与总体的序列/人物等权均值混称同一口径。全部原fallback帧名、每方法和每seed保存在FALLBACK_SUBGROUP.json。

## 5. 判断边界与下一步

本轮主对照是预先固定的hist_med6，不依据B从18组挑一个新正式模型。若某分支分数更小，只能证明这套观测/求解在已消费开发集的可见表面评价更好；不能把其平移当Camera GT。Native Camera L2与对应顶点必须单独读。

本轮不能将约3mm差距按比例归到MLP、点数、射线或优化步数。原Fine同时使用RGB并受Camera/表面混合训练目标约束；几何算子不使用相同训练目标。没有进行同输入、同监督的head训练替换，因此“MLP不会精确求解”仍未得到证明。已经成立的是这几个固定几何干预的实际效果，以及简单“三维NN必更好”解释的反例。

下一阶段优先考虑受约束的几何求解与对应可靠性，保留投影信息，不整体替换成三维最近邻。不再将“MLP不会算几何”“点数少就是唯一原因”当已证实机制。点面LS可作为候选参考，必须同时针对真实P95和跨域退化验证；学习权重只有超过这些不学习的稳健算子才有增量意义。此次结束，不自动重构、组合或训练。DGR/PointDSC已有学习权重与几何求解路线，采用这类模块本身不是足够的新颖性证明。

POST_INTEGRITY、逐人P95、所有失败与完整seed结果是本次交付的一部分。负收益转移Native按对应顶点误差定义，真实按表面median定义，不冒充旧Native Camera负收益计数。完整RGB→Mesh端到端耗时本轮仍未测，缓存求解的吞吐不能替代它。
