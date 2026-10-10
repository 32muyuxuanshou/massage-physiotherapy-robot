# 复现

CPU Python 3.11.9，实际NumPy/SciPy/OpenCV版本见EXECUTION_LEDGER.json；无SAM权重重载/新网络推理。代码中历史Txyz/相机函数通过AST原样读取，不修改其数值实现；精确表面距离为原评价器。包内保存所有本轮脚本和直接历史依赖。

## 输入

- `source`：恢复R4.1私有目录，含原始Official/A点/标定、R4三个G1 Best预测、固定B点、历史corrected结果与code。
- `previous`：恢复R4.2私有目录，含交换raw/corrected网格、全部结果、VISUAL_SELECTION、RGB和POST_EXECUTION_INTEGRITY。
- `work`：恢复本轮私有增量，含官方源文件/标定、raw、ray_cache、结果和图。路径与实际SHA见BACKUP_RECEIPT。

官方标定包和工具箱URLs、实际SHA见OFFICIAL_SOURCE_RECEIPT；只提取29个TRAIN/VAL序列。官方函数直接从原文件AST提取 `compute_transform_from_camera_params/transform_points/perspective_projection`。

## 执行

在仓库根目录或把 `code` 加入PYTHONPATH：

```powershell
python research/rgbd_sam3d_mhr/audit_r42_geometry.py --source output/r41_txyz_diagnostic_v1 --previous output/r42_development --out output/r42_geometry_chain_v1 --workers 4
python research/rgbd_sam3d_mhr/audit_r42_raw.py --work output/r42_geometry_chain_v1 --previous output/r42_development
python research/rgbd_sam3d_mhr/visualize_r42_geometry.py --source output/r41_txyz_diagnostic_v1 --previous output/r42_development --work output/r42_geometry_chain_v1
python research/rgbd_sam3d_mhr/visualize_r42_raw.py --work output/r42_geometry_chain_v1 --previous output/r42_development
```

上列使用本地已恢复资产，**不要求AutoDL/GPU**。换宿主机时替换目录参数即可。导出阶段实际在原无卡AutoDL用其CPU环境执行：

```bash
/root/autodl-tmp/rgbd_sam3d/envs/rgbd/bin/python /root/autodl-tmp/rgbd_sam3d/r42_geometry/export_r42_geometry_raw.py --root /root/autodl-tmp/rgbd_sam3d --out /root/autodl-tmp/rgbd_sam3d/r42_geometry/raw --selection /root/autodl-tmp/rgbd_sam3d/r42_geometry/SELECTION.json
```

导出首次因把selection字典按列表读而失败，修复 `records` 后完整重跑；两日志保留。顺序RGB当前帧和原始Depth/mask必须逐数组相同。邻近帧只做敏感性检查，不重设对齐/评价帧。

## 数值合同

- 主B评价沿历史2048固定点、point→triangle和frame→sequence→identity；本轮没有新拟合或主分数变化。
- 新A诊断从历史A点集确定性取512点，仅作射线检测；透视候选由完整投影三角形AABB产生，双面最近正Z命中。共同命中点取全部14方法交集，命中率单独保留。
- Raw重建用作者mask及100–5000mm有效范围、官方Depth/Color外参，前表面5mm窗口与历史缓存一致。这证明缓存链复现，不证明传感器精度。
- 4px A/B邻近只是观测一致性诊断，包含遮挡/不同面；没有B对齐、筛帧、删异常或调参。
- 原始硬件时钟未提供，不能证明零延时。Depth内填补数据没有当原始GT。

本次closeout重读696历史输入、378网格SHA。Public FILES_MANIFEST按Git交付字节核对；私有增量包含原始54NPZ/PNG、相邻RGB和27射线缓存。权重/Checkpoint与训练结果沿上一轮备份，不复制进Git。
