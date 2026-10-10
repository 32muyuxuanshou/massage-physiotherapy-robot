# 首批原生Camera-only训练结果

只使用旧native TRAIN/VAL缓存，TEST与真实B均未参与训练。每头30epoch、seeds11/23/37；最佳checkpoint由400张native VAL、50身份等权Camera误差选择。

|头|seed11|seed23|seed37|均值±标准差（mm）|
|---|---:|---:|---:|---:|
|raw_bounded|32.71|33.54|33.41|33.22 ± 0.44|
|metric_xyz|32.32|33.63|32.61|32.85 ± 0.69|
|rgb_only_xyz|75.25|75.86|76.82|75.98 ± 0.79|

Official起点Camera误差153.36mm。这里是**合成MHR根位置误差**，不是真实Camera B表面距离、穴位误差或机器人接触精度。

两个RGB-D头都明显优于小RGB-only头；当前三seed的差异不足以说明公制XYZ一定优于raw bounded。下一步仍按预注册计划做native-only/mixed对照及真实开发评价，不根据这些结果临时改参数。

全部Body输出固定，局部顶点/去平移顶点、Pose、Shape、Scale不能因此宣布改善。9组best/last已保存，正文与逐身份/逐图数值见native_results/。
