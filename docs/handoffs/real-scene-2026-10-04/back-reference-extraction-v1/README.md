# BACK_REFERENCE_EXTRACTION_V1

[最终报告](FINAL_REPORT.md) · [执行前协议](PROTOCOL.md) · [配置](CONFIG.json) · [全部图](figures/INDEX.md)

30真实背部XYZ扫描、3几何方法、90预测缓存。估计器不读原标记或体表画线；之后独立对照作者画线。不是穴位GT或部署相机验收。

- `code/`：估计、评价、作图、解析检查、独立缓存复算。
- `curves/`：90个最终曲线与原扫描点索引。
- `PER_SCAN_RESULTS.csv` / `PER_REFERENCE_POINT.csv` / `RESULTS.json`：全部评价，含共同覆盖。
- `PREDICTION_FREEZE.json` / `EVALUATION_INTEGRITY.json`：预测与评价隔离证据。
- `CACHE_REPLAY_VERIFICATION.json`：90缓存主指标独立复算。
- `SOURCE_FREEZE_PUBLIC.json`：匿名源文件身份，原路径映射服务器保留。

复现服务器：`xuhd@172.18.18.151:436`，根目录`/raid5/xuhd/datasets/back_reference_extraction_v1_20261004`。数据/环境依赖见[父审计复现说明](../real-back-reference-qualification-v1/REPRODUCTION.md)。

在服务器依次运行：

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/back_reference_extraction_v1_20261004
$PY $ROOT/code/test_geometry.py
$PY $ROOT/code/run_extraction.py --root $ROOT
$PY $ROOT/code/evaluate_curves.py --root $ROOT
$PY $ROOT/code/make_figures.py --root $ROOT
$PY $ROOT/code/verify_results.py --root $ROOT --reference-root /raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004
```

本地可用本目录和父交付直接执行`verify_results.py --root 本目录 --reference-root 父交付目录`，不加载模型、不重新估计。
