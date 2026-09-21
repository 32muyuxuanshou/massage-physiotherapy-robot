# 空间残差审计 V1

## Material Passport

- 状态：`COMPLETE_DESCRIPTIVE`；只读取已有 formal V3 vertices、RGB-D、mask 和 calibration。
- 运行位置：服务器 `/raid5/xuhd/back_local_feasibility_v1/spatial_residual_audit_v1/`。
- 范围：18 timestamps × 3 条件 × 3 held-out cameras × 3 methods；原始记录 954 条。
- 空间定义：将每个 K1/K2/K3 深度点变到 K0，按 K0 mask-derived condition ROI 的投影分成 `roi` / `outside_roi`。
- 距离：点到预测 mesh **最近顶点**的距离，作为空间定位 proxy；不是正式点到三角面距离，因此只能诊断区域，不替代主指标。

## 聚合结果（所有相机/帧/sequence/subject 的中位数）

单位 mm；每个格子是区域内深度点到最近 mesh 顶点的中位距离。

| 输入 | 区域 | Official | Txyz | T+Pose |
|---|---|---:|---:|---:|
| FULL | ROI | 33.58 | 16.92 | 15.70 |
| FULL | outside ROI | 2740.02* | 2751.49* | 2768.57* |
| UPPER | ROI | 26.59 | 17.39 | 15.96 |
| UPPER | outside ROI | 55.75 | 42.92 | 38.56 |
| LOCAL_TORSO | ROI | 32.42 | 22.57 | 17.39 |
| LOCAL_TORSO | outside ROI | 44.78 | 36.22 | 30.54 |

`*` FULL 的 outside-ROI 记录主要来自跨相机投影后的畸变/视场边界，不能解释为人体远端误差；FULL 正确解读只看 ROI 行。UPPER/LOCAL 的 outside-ROI 仍是条件外区域的观测点，包含远端人体和交互物体边界，不能直接等价于“不可见人体表面”。

## 这对下一步说明什么

1. Txyz 首先改善的是整体几何位置，LOCAL ROI 也从 32.42 降到 22.57 mm，说明局部输入并没有让可见区域完全失效。
2. T+Pose 在 ROI 内继续下降到 17.39 mm，同时 outside-ROI 也下降到 30.54 mm；这说明当前联合优化可能同时改善远端投影，但不能证明它恢复了正确解剖姿态。
3. 结合逐帧审计，LOCAL 的 T+Pose 有 11/18 帧改善、7/18 帧恶化，故总体空间代理不能支持“稳定泛化”。
4. 当前脚本使用最近顶点以快速定位误差区域；下一步若要成为论文证据，应改为复用 `point_to_triangle_distances`，并保存每个残差点的三维位置、K0 投影、区域和误差分位数。

完整原始结果在 `SPATIAL_RESIDUAL_AUDIT.json`，脚本为 `../code/run_spatial_residual_audit_v1.py`。本审计没有改变训练、评价阈值或样本。
