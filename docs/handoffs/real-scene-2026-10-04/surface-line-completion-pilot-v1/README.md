# 体表线学习原型：实际训练与评价已完成

**状态：TRAINING_AND_EVALUATION_COMPLETE，2026-10-05。** 恢复既有服务器存储后，重新同步并核验原七个执行脚本与协议，完成GPU正向/反向、数据准备、六模型各120轮训练和216条评价。

[实际结果与完整审查](results-v1/FINAL_REPORT.md) · [全部图](results-v1/figures/INDEX.md) · [固定协议](PROTOCOL.md) · [执行状态](EXECUTION_STATUS.json)

20训练/4开发/6已消费评价来源，两策略×三个初始化。缺失块增强使作者体表线横向差异6.99→4.15 mm；不是穴位误差，不是SAM3D微调，也未确认独立患者划分。模型和全部失败结果保留。

[后续冻结模型俯卧迁移](../../real-scene-2026-10-05/prone-learned-reference-transfer-v1/FINAL_REPORT.md)已经完成，稳定性改善但仍有厘米级分歧；不放行医学定位或伪标签。

## 运行

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004
$PY $ROOT/code/test_data.py
$PY $ROOT/code/test_line.py
$PY $ROOT/code/data_line.py --root $ROOT
$PY $ROOT/code/train_line.py --root $ROOT
$PY $ROOT/code/evaluate_line.py --root $ROOT
$PY $ROOT/code/make_figures.py --root $ROOT
```

原始扫描及六checkpoint位于服务器，不入Git。Git包含代码、协议、派生输入/预测、评价必要目标、全部表图和复算入口。本目录LOCAL_DATA_SANITY是当时本地代码检查；实际GPU证据在results-v1。

历史：2026-10-04初次启动时SSH超时，随后能登录但/raid5/xuhd不可见；当时确实未训练。用户通知恢复后才完成本次执行，没有将待运行阶段改写为已执行。

PointDG作者代码此前取得commit dd5099f1261deeebdb7fa25b23a5c78b681739e3，未运行，不作为已复现比较方法。[来源](https://github.com/malongtan/PointDynamicalGraph-Net)。
