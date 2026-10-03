# 实际执行与复现位置

服务器：`xuhd@172.18.18.151:436`。SSH 使用既有 key；密码/token 不写入交付。

| 内容 | 实际路径 |
|---|---|
| 本轮代码/输出 | `/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003` |
| 新法向 D 与四方法缓存 | 上述根目录下 `c_pressure_normal` |
| 首次诊断断言失败批次 | 上述根目录下 `c_pressure_normal_attempt1`，保留 57 个成功缓存与代码快照 |
| 新 atlas / 2,400 传播 | 上述根目录下 `a_atlas` |
| 300 候选资格、点索引和 world 点 | 上述根目录下 `b_qualification` |
| 原 300 俯卧缓存 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2` |
| 原冻结基线代码/合同 | 同一 corrected_comparison_v2 根下 `delivery` |
| 旧审计工具/原生资产 | `/raid5/xuhd/datasets/prone_back_point_validation_20261003` |
| BEHAVE 原数据/标定/官方实现 | `/raid5/xuhd/behave_rgbd_mesh_v1` |
| 既有 SAM 源/授权权重 | `/raid5/xuhd/sam3d_s01_pilot_20260906`；本轮未加载权重 |
| Python | `/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python` |

Python 3.10.20、NumPy 1.26.4、SciPy 1.15.3、Torch 2.4.0+cu121、CUDA 12.1、OpenCV 4.11.0。新求解用 4 个 CPU 人物进程；没有新 GPU 推理/模型加载。SAM 源目录没有 Git metadata，不能把历史 cache SHA 冒称本轮重新加载模型的身份。[实查环境](EXECUTION_ENVIRONMENT.json)

## 当次命令顺序

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003

$PY "$ROOT/code/build_atlas.py"
$PY "$ROOT/code/screen_behave.py" --phase inventory
# 实际看过 15 页原 K0 contact 后冻结 B/N 编码：
$PY "$ROOT/code/freeze_k0_review.py"
$PY "$ROOT/code/screen_behave.py" --phase fourcam
# 原图选块、中心修订、共同深度支持与最终源块检查：
$PY "$ROOT/code/freeze_source_roi_review.py"
$PY "$ROOT/code/qualify_common_patch.py" --overrides "$ROOT/b_qualification/SOURCE_CENTER_OVERRIDES.json"
$PY "$ROOT/code/finish_qualification.py"
# 资格 NO GO，不启动 BEHAVE SAM / Rigid / D。

$PY "$ROOT/code/test_normal_d.py"
$PY "$ROOT/code/run_pressure_normal.py" --phase prepare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY "$ROOT/code/run_pressure_normal.py" --phase dev --workers 4
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY "$ROOT/code/run_pressure_normal.py" --phase validation --workers 4
# 第一次断言失败批次已整体保留为 c_pressure_normal_attempt1。
# 正交投影诊断修正后，上述 prepare/dev/validation 在独立新目录完整重跑。
$PY "$ROOT/code/run_pressure_normal.py" --phase integrity
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY "$ROOT/code/analyze_pressure.py"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY "$ROOT/code/validate_completion.py"
$PY "$ROOT/code/audit_rerun_agreement.py"
$PY "$ROOT/code/export_delivery.py"
```

`qualify_common_patch.py` 最终执行通过 `--overrides` 读取保存的 RGB 中心修订；最初不带 overrides 的默认中心草案另存 `draft_default_source`，完整顺序不是只跑一次。#153 前胸候选在该脚本内排除；其余最终源块排除在 `finish_qualification.py` 内。

这些命令描述实际流程，**不要在完成目录重跑 prepare 或模型分支**。`common.py` 保存当次绝对路径，新的复现必须先复制至独立根目录，显式修改 ROOT 并重新冻结、记录新的身份；不能覆盖当前缓存后仍称同一次运行。这里只复算指标可读取原完成目录。

`run_pressure_normal` 从旧冻结路径导入优化/渲染/评价工具，包内 `frozen_baseline_code` 为实际源码字节快照，`frozen_audit_code` 含传播及 Date loader，`reference_code/kinect_transform.py` 为实际对照的官方函数文件。新求解代码直接审查 `normal_d.py`，小型测试审查 `test_normal_d.py`。

## 怎么从文件追到数字

每人/seed/method：

1. `c_pressure_normal/meshes/Sxxx/seed_y/*.npz` 为最终 camera-space `vertices_m/faces`，同时存初始 MHR 状态、实际优化索引；Rigid/D 分支另有 R/t，法向 D 还有 u、固定法向与位移。
2. `inputs/Sxxx/input.npz` 和 `split_y.npz` 为冻结输入/划分；优化函数只收 `points_m[train_idx]`。NPZ symlink 指向旧输入，不改原文件。
3. `evaluation/Sxxx/seed_y/*_metrics.npz` 保存 posterior/torso point index、逐点欧氏距离、ray Z residual、hit/common-hit；Git 完整镜像这些文件。
4. `evaluation/Sxxx/results.json` 是缓存指标及元数据，`ALL_METHOD_RESULTS.json` 增加从逐点数组计算的 50 mm coverage；汇总不拟合。
5. `visualizations/Sxxx/seed_y/` 保存同一缓存的透视 depth、overlay 和 RGB comparison；最终顶点已包含变换，不再次叠加 cam_t。

470 源/输入/合同 freeze、240 cache 校验、180 原指标 exact agreement、4 个缓存独立重算分开记录。三种子平均后再汇总人物；公共图投影 8 ENG 点没有遮挡筛选、confidence 或医学定位声明。

## 本地复核副本

`E:/项目-按摩理疗机器人/output/back_geometry_correspondence_v2/private_review/`

- `INDEX.html`：全部私有原图复核图入口。
- `pressurepose/Sxxx_seed0.jpg` 等：60 页原 RGB + 四方法对照。
- `behave/`：15 页全候选 K0、29 页候选四机位、8 页源块、8 页 Sub07 投影块。

Git 路径为 `docs/handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2`。目录沿用启动日期；实际完成日期为 10/04。服务器自身时钟与桌面时钟有分钟级偏差，ledger 的当地日期不从服务器文件 mtime 推断。
