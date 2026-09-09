# MHR 背部 Fitability Gate：真实 RGB-D 采集协议 V1

本协议只服务 3–5 人的小型表示能力 Gate，不是正式 30 人训练集。当前两段视频只有 RGB，因此不能从中恢复独立毫米表面，也不能使用 SAM/MHR 自己的深度补齐。

## 最少采集

至少 3 位已核验匿名编号的真人，推荐 5 位。每人 3 个采集 bundle：A 为干净俯卧拟合视图；B 为同一保持姿态下的同步第二视角，专门作 held-out evaluation；C 为重新摆位后的重复性观测。最小为 9 对合格、注册的 RGB-D。先不放机械臂，背部尽量暴露，姿势舒适，允许自然头向和手臂位置变化。

## 标定与注册

保存 RGB/Depth 各自分辨率、`fx fy cx cy`、畸变模型与系数、Depth 到 RGB 的 4×4 米制外参以及原始 depth unit scale。保留 raw RGB、raw depth 和 registered depth，不只保存对齐结果。用覆盖实际工作距离的平面/标定板报告内参重投影 RMS、注册边界误差和深度绝对误差。首轮工程门为 RMS ≤1 px、注册边界中位数 ≤2 px、平面深度中位绝对误差 ≤5 mm、P95 ≤10 mm；不达标时修标定，不能靠放宽 surface 指标继续。

## 可进入 loss 的区域

标注者只能看原 RGB 和注册 Depth，不能看 SAM/MHR overlay。语义分为 `VISIBLE_BARE_BACK`、其它皮肤、机器人、衣物、床、头发、自遮挡、UNKNOWN 和背景。只有 `VISIBLE_BARE_BACK` 且局部深度有效、无飞点/多径/边缘混合的像素可以进入 surface loss。scene depth 不能整体当作 skin depth。

## 拟合和评价分离

优先用 A 视图 fitting、B 视图 evaluation，并用标定外参把预测表面变换到 B 相机。C 用于检查重新摆位后的重复性。若只有单相机同帧，只能把空间区域分成 FIT 与 HELD-OUT；这种结果最多叫 `OPTIMIZATION_FEASIBILITY`，不能判定 Gate PASS。任何用于 loss 的 depth pixel 都不得再次作为 held-out 成绩。

## 数据到位后的执行顺序

网络权重全部冻结，分别从 official、V2 epoch5、可选 epoch10 初始化。先在 1–2 个开发受试者上依次只优化 camera、只优化 pose、只优化 shape/scale，最后 combined；记录 loss/gradient scale 与参数漂移。固定优化器、先验、阈值后再打开其余受试者。主要指标为受试者宏平均的 held-out visible-back point-to-plane mm，并报告 median/P90/P95/max、上中下背与左右区域。DMD37 只报告方法间位移。

机器合同见 `MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.json`，填写模板见 `OBSERVATION_MANIFEST_TEMPLATE.json`。
