# 运行与复查位置

本轮服务器：`xuhd@172.18.18.151:436`。

- 工作根：`/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004`
- Python：`/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`
- PCdare原下载：`/raid5/xuhd/datasets/back_prone_acquisition_20261003/pcdare_35f7a1d9`
- 上轮完整扫描/标注路径索引：`/raid5/xuhd/datasets/prone_back_point_validation_20261003/p3_data_qualification`
- PressurePose原输入：`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2/inputs`

已运行，单CPU审计、没有GPU模型加载：

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY "$ROOT/code/test_reference_frame.py"
$PY "$ROOT/code/audit_pressurepose.py"
$PY "$ROOT/code/audit_references.py"
$PY "$ROOT/code/make_reference_figures.py"
$PY "$ROOT/code/verify_results.py"
# 结果后的只读分歧审计；没有重新调门槛或修改参考包
$PY "$ROOT/code/audit_marker_line_consistency.py"
```

六个原执行脚本、协议、已使用原文件及20个俯卧输入在主扫描审计前冻结，共1043项。原路径完整冻结为服务器 `SOURCE_FREEZE.json`，含原文件名/session信息，不进入Git；[匿名哈希映射](SOURCE_FREEZE_PUBLIC.json)保留全部1043项的SHA、字节数和类型。原扫描/标注重放脚本需要服务器既有私有路径索引，不声称仅下载本Git目录就能恢复全部原始云。

`reference_packets/*.npz`只有四标记、体表线、局部坐标、重绑定索引/距离，不含完整扫描。`REFERENCE_PACKET_MANIFEST.json`记录原扫描SHA、原标注SHA、派生包SHA；`ALL_CANDIDATES.csv`保留全部1326候选及排除/重复状态，失败没有删掉。每包有原来源标签候选，但`anatomical_accuracy_validated/acupoint_gt/calibrated_prone_rgbd`均为false。

`audit_marker_line_consistency.py`是结果后新增的第七脚本，其SHA保存在分歧JSON；它量化标记与连续体表画线的几何差异，并实算原30包未变。没有更改最初6脚本、协议或资格门槛。

交付缓存可独立检查：在该交付目录执行 `python code/verify_public_delivery.py`，只需NumPy，不需要原扫描或重新估计。该第八脚本是结果后的导出核验，检查30包/30图/1326行/20 RGB身份，不能替代服务器的原扫描核验。最终审查文件由 `FILES_MANIFEST.json` 和Git提交绑定。

私有RGB复查页在服务器 `private_review/pressurepose_review_1.jpg`、`pressurepose_review_2.jpg`；本地同名页在 `E:/项目-按摩理疗机器人/output/real_back_reference_qualification_v1`。公开图是扫描在参考坐标中的正交几何绘图，不是校准相机叠图。汇总图及逐包图全部从缓存生成。
