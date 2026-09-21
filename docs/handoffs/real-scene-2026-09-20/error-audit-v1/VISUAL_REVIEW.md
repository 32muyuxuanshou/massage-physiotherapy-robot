# 叠图视觉复核

叠图目录 `../visual_v3/` 中每帧有两张图：四机位 FULL 对照和 K1 下 FULL/UPPER/LOCAL_TORSO 三输入对照。每个条件颜色固定为 Official=红、Txyz=蓝、T_pose=绿；叠加仅用于形状和相机投影复核，定量结论以 K1/K2/K3 sensor depth 为准。

## 可复核现象

- FULL 的红色 Official 在四机位中通常已经覆盖人体主轮廓；蓝色 Txyz 的平移偏差明显收缩；绿色 T_pose 在坐姿、弯腰和持球动作中局部改变腿/躯干轮廓。
- UPPER 与 LOCAL_TORSO 的输入遮罩只改变 K0 RGB 上下文，图像几何没有重采样；局部输入下红色 mesh 仍可能覆盖大部分人体，但远端肢体和交互物体附近的绿/蓝差异更明显。
- `Sub03/Date03_Sub03_stool_sit/t0015.000` 是应重点审计的失败案例：视觉上可见坐姿与腿部覆盖变化，但数值上 LOCAL 的 T-only 与 T+Pose 都恶化，不能仅凭颜色把它解释成姿态修复成功。
- `Sub04/Date03_Sub04_yogaball_play/t0034.000` 展示了遮挡/持物场景：绿色和蓝色在人体外轮廓接近，但球体不是人体 mesh；此类画面提醒我们不能用背景或交互物体对齐来替代人体 surface 指标。

## 视觉审计边界

当前渲染是顶点投影与颜色覆盖的诊断图，不是有遮挡关系的 z-buffer 真值渲染；因此不能用颜色面积直接估计 IoU、遮挡率或表面完整性。叠图来自 formal V3 的 `Official_vertices/Txyz_vertices/T_pose_vertices`，不是 attribution rerun 的全部分支。完整文件名和来源 hash 见 `ERROR_AUDIT.json`、`SOURCE_SHA256.json`。
