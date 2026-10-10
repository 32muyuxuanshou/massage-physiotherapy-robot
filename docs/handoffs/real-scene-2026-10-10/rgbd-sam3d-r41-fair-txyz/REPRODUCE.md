# 恢复、审查与重算

本轮只需要 CPU、Python 3.11、NumPy 2.4.6、SciPy 1.17.1；图需 Pillow/Matplotlib。不需要 Torch、GPU 或重新运行 SAM。

私有几何包路径见 `BACKUP_RECEIPT.json`。还需要旧两个依赖：

- R3.1 native：`/raid5/xuhd/rgbd_sam3d_backups/2026-10-10_r31_diagnosis_pilot_v1/r31_native_outputs_v1.tar.gz`，SHA256 `167b70eab3884f5c65dbebe9a1869ed1b7df4fe199e8b50e09685ffc6b6a7b3e`。
- R4 formal：`/raid5/xuhd/rgbd_sam3d_backups/2026-10-10_r4_geometry_v1/r4_formal_native_v1.tar.gz`，SHA256 `caa531e2b878d46f7e17b60f21bc2f838ccf8dd5b03599ecd7e30b9658115c9f`。

先核对三包 SHA，然后在新目录恢复（替换路径）：

```text
python code/restore_r41_assets.py --work NEW_WORK --r41 R41_ARCHIVE --r31 R31_ARCHIVE --r4 R4_ARCHIVE --historical-results ../rgbd-sam3d-r31-diagnosis-pilot/diagnostics/CHEAP_TXYZ_COMPARISON.json
python NEW_WORK/code/run_r41_txyz.py --work NEW_WORK --workers 6
python NEW_WORK/code/analyze_r41_txyz.py --work NEW_WORK
python NEW_WORK/code/auxiliary_r41_components.py --work NEW_WORK
python NEW_WORK/code/audit_r41_txyz.py --work NEW_WORK
python NEW_WORK/code/visualize_r41_txyz.py --work NEW_WORK
```

恢复器只取 232 个 TRAIN/VAL native 和冻结点集，不提取 checkpoint、合成 TEST 或新训练数据。Native checkpoints 本身仍在旧备份中；本轮只读取与 Best SHA 绑定的预测。

`run_r41_txyz.py`先校验全部实际输入 SHA，再4固定帧回归，随后232帧Official回归Gate；任何回归不一致会中止，不继续比较G0/G1。历史函数由 AST 精确载入以避免 GPU 依赖，完整源文件及哈希都在交付中。几何统一 metre，距离展示 mm。

每个corrected NPZ保存vertices_camera_A/B、pred_cam_t、global_rot、body_pose、shape、scale、raw/applied T。拓扑共享original official faces。`distances`保存每帧2048个before/after距离；`regions`保存每点固定区域及最近reference face。报告和图只从这些缓存产生。

单独审计缓存：运行 `audit_r41_txyz.py`，会重开全部1624原始/最终文件，检查只平移一次及参数不变，并对8例不调用fit而直接重算精确距离。

备份保留运行科学资产和最终脚本；Git保存最终文本、完整表和全部48张科研对照图。原始RGB-D、点云、权重和完整Mesh不在公开Git。区域标签的公开副本在 `manifests/REGION_LABELS.json`，仅为固定工程诊断，不是医学atlas。
