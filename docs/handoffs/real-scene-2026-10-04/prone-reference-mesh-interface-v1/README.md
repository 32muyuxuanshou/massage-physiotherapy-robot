# PRONE_REFERENCE_MESH_INTERFACE_V1

[完整报告](FINAL_REPORT.md) · [协议](PROTOCOL.md) · [配置](CONFIG.json) · [全部图](figures/INDEX.md)

实际20人/3seed/3XYZ方法，180记录、132成功曲线、396固定Mesh绑定、3564工程探针。参考点不带医学穴位标签。原4开发/16已消费测试角色、近似相机/衣物限制保留。

- `curves/`：实际源训练点索引、曲线、支持距离。
- `bindings/`：每个成功曲线在Official/Rigid/RigidD上的9点face/bary/xyz/normal和查询；完整Mesh留服务器。
- `CURVE_RESULTS.csv`、`BINDING_RESULTS.csv`、`STABILITY_RESULTS.csv`：失败及逐人物表。
- `ENGINEERING_TARGETS_EXAMPLE.json`：S107/seed0/GROOVE/RigidD实际工程接口导出。
- `CACHE_VERIFICATION.json`：132曲线和396缓存实际源文件复查。
- `SOURCE_FREEZE_PUBLIC.json`：267项源SHA匿名记录；完整路径映射服务器留存。

数据出处：[PressurePose/Bodies at Rest](https://github.com/Healthcare-Robotics/bodies-at-rest)。本包无原RGB、原全云或授权权重；原数据使用条款照其来源执行。派生参考是程序输出，不是新临床标注。

服务器`xuhd@172.18.18.151:436`，Python`/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`。运行根目录`/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004`。

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004
$PY $ROOT/code/run_interface.py --root $ROOT
$PY $ROOT/code/analyze_interface.py --root $ROOT
$PY $ROOT/code/verify_interfaces.py --root $ROOT
$PY $ROOT/code/export_targets.py --cache $ROOT/bindings/S107_0_GROOVE_DP_RigidD.npz --out $ROOT/ENGINEERING_TARGETS_EXAMPLE.json
```

提取器和投影器依赖已经固定的前两份服务器源码；路径与SHA保存于配置/源冻结。上述命令只读既有输入/网格，不训练或重新拟合。
