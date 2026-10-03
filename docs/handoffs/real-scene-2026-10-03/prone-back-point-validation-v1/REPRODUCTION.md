# 实际执行与复现

服务器`xuhd@172.18.18.151:436`。实际Python3.10.20、Torch2.4.0+cu121、CUDA12.1、NumPy1.26.4、RTX2080Ti 11GB；未新建环境或迁回AutoDL。

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/prone_back_point_validation_20261003
CACHE=/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2
BEHAVE=/raid5/xuhd/behave_rgbd_mesh_v1
SAM=/raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body
ACQUIRED=/raid5/xuhd/datasets/back_prone_acquisition_20261003
```

基线实际ROOT为`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery`。包内frozen_baseline_code与该目录源码逐字节一致，本轮代码仍默认从原路径读取。

weights：`/raid5/xuhd/sam3d_s01_pilot_20260906/weights`，含model.ckpt/model_config.yaml/assets/mhr_model.pt；anchors：`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/run_assets/anchors.npz`。实际checkpoint/MHR/anchor/SAM源码/旧baseline/calibration/table/ROI SHA在运行freeze中，model_config由launcher补充前后校验。权重不打包。

## 执行顺序

```bash
$PY "$ROOT/code/run_cached_point_diagnostics.py" --assets "$ROOT/assets" --cache "$CACHE" --out "$ROOT" --sam-repo "$SAM" --phase assets
$PY "$ROOT/code/run_cached_point_diagnostics.py" --assets "$ROOT/assets" --cache "$CACHE" --out "$ROOT" --sam-repo "$SAM" --phase dev
$PY "$ROOT/code/run_cached_point_diagnostics.py" --assets "$ROOT/assets" --cache "$CACHE" --out "$ROOT" --sam-repo "$SAM" --phase full
$PY "$ROOT/code/summarize_cached_point_tails.py" --root "$ROOT"
$PY "$ROOT/code/run_proxy_rule_comparison.py" --assets "$ROOT/assets" --cache "$CACHE" --out "$ROOT/p4_rule_comparison"

# qualify_public_assets.py: 分别运行 --phase dmd / pcdare / behave
# 参数完整schema见源码；BEHAVE out为ROOT/p2_behave_crossview。
$PY "$ROOT/code/finish_data_qualification.py" --root "$ROOT" --acquired "$ACQUIRED" --reader "$ACQUIRED/back-data-acquisition-v1/code/audit_acquired_assets.py"

# 原RGB review、固定patch表及world-cloud人工QA先完成，再prepare。
$PY "$ROOT/code/run_behave_rigid_d.py" --root "$ROOT" --behave "$BEHAVE" --phase prepare
$PY "$ROOT/code/summarize_behave_cached.py" --root "$ROOT" --behave "$BEHAVE" --phase freeze
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 $PY "$ROOT/code/run_behave_rigid_d.py" --root "$ROOT" --behave "$BEHAVE" --phase smoke
$PY "$ROOT/code/launch_behave_jobs.py"
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 $PY "$ROOT/code/summarize_behave_cached.py" --root "$ROOT" --behave "$BEHAVE" --phase summarize
$PY "$ROOT/code/export_review_assets.py" --root "$ROOT"
$PY "$ROOT/code/export_frame_metadata.py" --root "$ROOT"
```

不要覆盖已完成run：runner要求每帧输出目录不存在。复现要用独立ROOT及审查包恢复/验证的输入、ROI和freeze；文件含绝对路径，迁移后须显式重新冻结，不能冒称同一执行身份。

`freeze_behave_reference_patches.py`保存实际人工RGB选点表；180视图和15页patch实际看过。world点云QA查看16序列数据图，CLOUD_WORLD_VISUAL_QA是人工工程记录，不是脚本自动证明的物理标定。

五个人分别GPU0..4，各9帧，seed0，frame顺序保持原manifest；帧处理时间总和分别约170/176/176/156/164秒，不含模型加载及大文件hash，不能当部署速度。

## 数据流和缓存

P1/P4只读300缓存、0次SAM/拟合。P2每帧保存完整official_prediction和五最终方法NPZ：vertices_m/faces、MHR参数、实际优化点索引；Rigid/D还有显式R/t和optional displacement。Rigid/D的原MHR状态不能单独重建最终表面；vertices_m已是最终camera坐标，画图不再次加cam_t。

K0有效person点优化；K1/K2/K3 never优化。每相机所有方法使用同一posterior索引。射线按pointcloud_table的3D方向求透视交点，指标是camera-Z差；不是显示depth图，也不是沿ray欧氏距离。主指标是精确point→triangle欧氏距离。RGB叠图用cv2.projectPoints原K+dist，painter仅定性。

运行前后source、输入、原RGB/depth/mask完整性通过。固定顺序前三个有效held-out views从cache独立重算，15组distance/ray数组exact equal；没有声称所有225网格的二次指标重算。全部网格另有hash/维度/索引检查。原coarse-camera gate与Smoke字典字段错误保留并解释于最终报告；正式样本、方法权重、ROI未依据模型结果改动。

完整原数据、原路径关联与大NPZ在有授权的服务器复查。公开JSON及SHA不能代替原始坐标数组；公开预测图也不能代替RGB对齐审查。

本地完成下载的 JSON/CSV/JSONL 与预测图镜像后，`code/package_review_delivery.py --workspace E:/项目-按摩理疗机器人` 只打包已有输出、匿名化PCdare路径、重算表格的层级聚合并核验freeze/图hash/链接，不调用模型或拟合。`.gitattributes`禁止本交付的自动换行转换，确保Git blob与文件SHA一致。
