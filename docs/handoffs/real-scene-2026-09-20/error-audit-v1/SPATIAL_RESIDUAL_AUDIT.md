# 空间残差审计 V1

## Material Passport

- 状态：`COMPLETE_DESCRIPTIVE`；只读取已有 formal V3 vertices、RGB-D、mask 和 calibration。
- 运行位置：服务器 `/raid5/xuhd/back_local_feasibility_v1/spatial_residual_audit_v1/`。
- 范围：18 timestamps × 3 条件 × 3 held-out cameras × 3 methods；原始记录 954 条。
- 空间定义：将每个 K1/K2/K3 深度点变到 K0，按 K0 mask-derived condition ROI 的投影分成 `roi` / `outside_roi`。
- 距离：项目正式 `point_to_triangle_distances`；每个 camera 固定抽取 500 个深度点，作为空间定位诊断样本。

## 聚合结果（所有相机/帧/sequence/subject 的中位数）

单位 mm；每个格子是区域内深度点到最近 mesh 顶点的中位距离。

| 输入 | 区域 | Official | Txyz | T+Pose |
|---|---|---:|---:|---:|
| FULL | ROI | 34.12 | 14.82 | 13.90 |
| FULL | outside ROI | 2751.26* | 2767.74* | 2760.00* |
| UPPER | ROI | 25.11 | 15.15 | 13.36 |
| UPPER | outside ROI | 58.98 | 48.07 | 42.17 |
| LOCAL_TORSO | ROI | 31.34 | 21.73 | 15.74 |
| LOCAL_TORSO | outside ROI | 46.08 | 35.47 | 30.92 |

`*` FULL 的 outside-ROI 记录主要来自跨相机投影后的畸变/视场边界，不能解释为人体远端误差；FULL 正确解读只看 ROI 行。UPPER/LOCAL 的 outside-ROI 仍是条件外区域的观测点，包含远端人体和交互物体边界，不能直接等价于“不可见人体表面”。

## 这对下一步说明什么

1. Txyz 首先改善的是整体几何位置，LOCAL ROI 也从 31.34 降到 21.73 mm，说明局部输入并没有让可见区域完全失效。
2. T+Pose 在 ROI 内继续下降到 15.74 mm，同时 outside-ROI 也下降到 30.92 mm；这说明当前联合优化可能同时改善远端投影，但不能证明它恢复了正确解剖姿态。
3. 结合逐帧审计，LOCAL 的 T+Pose 有 11/18 帧改善、7/18 帧恶化，故总体空间代理不能支持“稳定泛化”。
4. 本轮已经改用 `point_to_triangle_distances`；由于单次全量精确计算非常昂贵，当前是每 camera 500 点的固定诊断样本，不是主指标的 5000 点全量复算。若写论文，应保存每个残差点的三维位置、K0 投影、区域和误差分位数，并在更大样本上复核。

完整原始结果在 `SPATIAL_RESIDUAL_AUDIT.json`，脚本为 `../code/run_spatial_residual_audit_v1.py`。本审计没有改变训练、评价阈值或样本。
