# 复算本轮分析

本轮只分析已完成的 R5；不训练、不改变已有模型结果、不重新拟合 Txyz。

源结果 commit：`be5a0f2a585fcd313789ee1ff4e8da8b683b8b08`。

服务器：`xuhd@172.18.6.218:436`。源目录：

```text
/raid5/xuhd/rgbd_sam3d/r5_camera_overnight_v1
```

在该实例上使用 `runtime/env/bin/python`，运行以下分析，CPU 即可：

```bash
python extract_error_audit.py --root "$ROOT" --out "$ROOT/error_analysis_v1"
python check_feature_sensitivity.py --root "$ROOT" --out "$ROOT/error_analysis_v1"
```

`check_feature_sensitivity.py` 与本交付的 `camera_head.py` 放在同一目录。它只加载 frozen best checkpoint，检查原始预测吻合后，仅替换第12维有效深度占比；参考值取 native TRAIN 中位数。没有读取 B，也没有计算干预后的 B 分数。因此这是机制敏感性检查，不能作为新测试成绩或可部署修复。

从服务器取回两份 JSON，或直接使用本包已提供的 JSON，然后在仓库根目录：

```powershell
python research/rgbd_sam3d_mhr/r5_camera_only/analyze_raw_errors.py --source docs/handoffs/real-scene-2026-10-11/r5-camera-overnight-v1 --cache-audit docs/handoffs/real-scene-2026-10-11/r5-raw-error-analysis-v1 --out output/r5_error_analysis_rebuild
```

图像另由实际缓存生成：

```powershell
python research/rgbd_sam3d_mhr/r5_camera_only/visualize_raw_errors.py --inputs output/r5_camera_overnight_v1/real_visual_inputs --source docs/handoffs/real-scene-2026-10-11/r5-camera-overnight-v1 --out output/r5_error_analysis_rebuild
```

大缓存保存在218原目录以及此前已校验的本地备份包，见[真实备份回执](../r5-camera-overnight-v1/REAL_BACKUP_RECEIPT.json)和[权重备份回执](../r5-camera-overnight-v1/GPU_FINAL_BACKUP_RECEIPT.json)。本轮没有启动 GPU，没有重启 AutoDL，没有关闭218。

指标复核：每帧固定2,048个 B 点到预测三角面的最近距离；每帧取 median/P95/≤50mm比例；同 sequence 帧均值→同身份 sequence 等权均值→各身份等权均值。脚本逐项核对与源交付汇总的差值小于 `1e-9`。种子标准差用 `ddof=1`，不是置信区间。
