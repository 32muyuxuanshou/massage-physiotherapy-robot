# 固定工程点传播诊断 V1

本轮全在本地执行，0新SAM推理、0几何拟合、0训练。保留20个历史人物、4开发/16已消费验证角色、3个空间块划分和原8个ENG点。

入口：[最终报告](FINAL_REPORT.md) · [全量图索引](VISUAL_INDEX.md) · [受控逐点数据](CONTROLLED_POINTS.csv) · [真人点位稳定性](REAL_STABILITY_PER_SUBJECT.csv)

## 可直接复查

只需 Python 和 NumPy；以下命令不需要服务器、原始患者数据、完整MHR或权重：

```powershell
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/replay.py
```

复算1,920条受控点误差、1,440个真人位置、960个真人三角面绑定、480个跨度和30组主聚合，校验82张图。`replay.py`只写自己的CACHE_REPLAY.json。

## 从原交付重建本目录

需要本Git仓库里三个旧交付缓存、20份后背case JSON，以及本地完整canonical资产：

```powershell
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/analyze.py --cohort dev
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/analyze.py --cohort all
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/visualize.py
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/verify_sources.py
```

`--cohort dev`是S107主路径读取和8面匹配检查，不执行拟合；写canonical小缓存与配置。全量覆盖全部20人。生成图使用Python/NumPy/Matplotlib/Pillow；命令在仓库根目录执行。旧交付只读，新输出在本目录，历史目录不覆盖。

本次canonical资产读取位置是 `output/prone_back_point_validation_v1/assets/mhr_rest_vertices.npy` 与 `mhr_faces.npy`，SHA与原Atlas冻结一致。原始坐标为cm；脚本转m×0.01。后背预测缓存本来就是m，不再应用额外Rigid变换。

本次另生成了一张S107私有原RGB点位图：

```powershell
python docs/handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/code/visualize.py --private-input output/observed_prone_surface_interface_v1/inputs/S107/input.npz --private-out output/engineering_point_transfer_diagnostic_v1/private_review
```

该选项需要既有私有input，输出不入Git。省略该选项即可重画全部公开图。

## 文件说明

| 文件 | 含义 |
|---|---|
| FROZEN_POINTS.json / EXECUTION_CONFIG.json | 固定8点、人物、方法与汇总合同 |
| canonical_cache.npz | 8个标准点三角面和坐标；不含完整MHR |
| controlled_cache.npz | 240×8点的最终/参考坐标与法向；不含完整受控网格 |
| real_cache.npz | 20×3×3×8点坐标/法向/K；Rigid及RigidD的局部8面 |
| CONTROLLED_POINTS.csv | 1,920条已知数字参考误差 |
| CONTROLLED_PER_SUBJECT.csv / CONTROLLED_AGGREGATED.json | 逐人物/扰动/方法与角色汇总 |
| REAL_POSITIONS.csv | 1,440个真人点位置、投影、ROI状态 |
| REAL_STABILITY_POINTS.csv / REAL_STABILITY_PER_SUBJECT.csv / REAL_AGGREGATED.json | 跨划分稳定性；不是定位精度 |
| REAL_MOVEMENT.csv | Rigid→RigidD的移动；不是定位误差 |
| CONTROLLED_POSTCORRECTION_OVER10MM.csv / REAL_OUTSIDE_ROI.csv | 全部相应复查记录，无删除/筛选 |
| SOURCE_MANIFEST.json | 实际读取源路径/大小/SHA；从仓库根目录解析 |
| EXECUTION_LEDGER.json / POST_EXECUTION_SOURCE_INTEGRITY.json | 执行范围与前后源身份 |
| VISUALIZATION_MANIFEST.json / VISUAL_INDEX.md | 82张新图与60张原Mesh叠图链接 |
| CACHE_REPLAY.json / FILES_MANIFEST.json | 独立复算结果与本交付SHA |

大误差和ROI越界点都保留。5/10/20mm阈值只用于工程描述；没有临床放行标准。没有独立患者点真值、没有全网格重算，不能把本轮称作真实穴位精度验证。
