# BOUNDED_REFERENCE_CORRESPONDENCE_V1

[报告](FINAL_REPORT.md) · [协议](PROTOCOL.md) · [配置](CONTRACT.json) · [全部图](figures/INDEX.md)

固定拓扑、原RBF准确/带噪、CONVEX4准确/带噪五组完整60case对照。180旧缓存按字节继承、120新增对应、固定Mesh完全未改。

`runs/`保存300个完整face/bary/xyz/normal/offset缓存及结果；`PER_PROBE_RESULTS.csv`为2400点；`NOISE_RESPONSE.json`/`QUERY_NOISE_RESPONSE.json`为输入扰动的真实响应；`CACHE_VERIFICATION.json`是独立缓存复算。源完整路径留服务器，匿名SHA见`SOURCE_FREEZE_PUBLIC.json`。

服务器`xuhd@172.18.18.151:436`：

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/bounded_reference_correspondence_v1_20261004
$PY $ROOT/code/test_convex.py
$PY $ROOT/code/run_bounded.py --root $ROOT
$PY $ROOT/code/analyze_bounded.py --root $ROOT
$PY $ROOT/code/verify_bounded.py --root $ROOT
```

依赖[父对应实验](../reference-assisted-correspondence-v1/README.md)的同一四输入参考/四考试truth、原表面和已有投影/图距离函数；实际SHA已冻结。没有GPU模型加载或临床目标。
