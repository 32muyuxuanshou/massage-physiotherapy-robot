# R5 集中离线诊断结果

完成同一 Full Last 的 2,706 条 Coarse/Fine 对照、HuMMan 232 帧 Camera A-only 匹配平移/刚体对照、Native 400 帧原生 MHR 真值旋转参数替换。三个 seed 为 11/23/37；没有训练。

|数据 / 指标|Full 内部 Coarse|Full 最终 Fine|Official+历史 Txyz|
|---|---:|---:|---:|
|Native VAL / Camera 向量误差|47.86 ± 0.79|20.61 ± 0.40|—|
|HuMMan TRAIN / 独立 B 表面误差|31.15 ± 0.85|20.52 ± 0.42|24.65（固定参考）|
|HuMMan VAL / 独立 B 表面误差|19.19 ± 1.51|14.36 ± 0.86|11.23（固定参考）|
|BEHAVE / 拟合参考对应顶点 PVE|77.33 ± 5.25|61.06 ± 2.01|56.24 ± 0.00|

Fine 总体有效，但并非处处有效。Native 每个 seed 有 67–72/400 帧 Camera 误差变大，29–40/400 帧修正方向与原生 Camera 真值所需方向相反；95–102/400 帧 Camera 改善但顶点误差恶化。不能只归因为步长不足，也不能拿 Txyz 当真实 Camera 标签。

HuMMan VAL：匹配平移 11.122 mm，匹配刚体 10.322 mm；P95 41.855→39.497 mm。26/40 帧改善、14/40 变差；四个身份三个改善、一个变差。历史 Txyz 11.226 mm 保持不变。这是算法与数据条件下的小幅收益，不是全局最优或增加旋转网络的充分证据。

Native 真值参数替换：Official 157.121 mm；仅换平移 100.227 mm；仅换整体旋转 196.021 mm；同时换两者 140.831 mm。正确重新解码并通过 400 帧物理旋转核验，仍可能恶化。固定错误的内部人体参数时，真值参数替换不是表面误差 oracle。局部姿态补偿等解释尚未因果验证。

建议保留硬解耦与 Fine，下一项集中检查 Fine 的负收益以及 Camera 标签与观测表面目标的错位，不直接展开训练、增加多步或旋转模块。完整 GPU 端到端速度按用户要求暂缓，因此尚不能宣称速度优势。

完整逐 seed、逐人、逐帧结果及全部坏帧见 HTML、SUMMARY.json、PER_FRAME.csv、Q1_RECORDS.json、RIGID_RECORDS.json 和 ALL_FRAME_CHANGE_INDEX.csv。

Native/HuMMan 封存 TEST 未读；BEHAVE 为已消费官方 TEST 子集。没有 Camera B 拟合。三个数据集指标不能混成一个总毫米值；不能据此声称 M³ 同协议领先、裸背精度或穴位精度。
