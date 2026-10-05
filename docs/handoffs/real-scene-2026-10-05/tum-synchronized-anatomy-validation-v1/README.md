# TUM同步解剖外部验证V1

[最终报告](FINAL_REPORT.md) → [事实结果](RESULTS.json) → [两参考结果](REFERENCE_ASSIST_RESULTS.json) → [逐例表](REFERENCE_CASE_TABLE.csv)。

- 来源：[作者数据](https://mediatum.ub.tum.de/1846795)，[PLOS论文](https://doi.org/10.1371/journal.pone.0353213)；衍生输入/图/标签按CC BY 4.0归属原作者，改变包括后侧代理抽取、光栅化和推理。非临床穴位真值。
- 事前：[PROTOCOL](PROTOCOL.json)、[两参考合同](REFERENCE_ASSIST_PROTOCOL.json)、[来源坐标修订](SOURCE_COORDINATE_AMENDMENT.json)、[17例manifest](CASE_MANIFEST.json)、[原header](NATIVE_HEADERS.json)。
- 执行：[模型冻结](MODEL_IDENTITY.json)、[首次适配器修复](EVALUATOR_ADAPTER_FIX.json)、[最终执行冻结](EXECUTION_FREEZE_V1_1.json)、[先验训练来源](REFERENCE_PRIOR_FIT.json)、[执行账本](EXECUTION_LEDGER.json)、[执行后完整性](FINAL_INTEGRITY.json)。
- 可独立重算：`inputs/`、`predictions/external_TUM/`、`reference_predictions/`；[普通重算](DELIVERY_REPLAY.json)、[参考重算](REFERENCE_DELIVERY_REPLAY.json)。
- 全量展示：`figures/`、`reference_figures/`、正确坐标标签的`qualification_review/`、[9页索引](VISUAL_REVIEW.md)、`montages/`。原`qualification_figures/`保留执行期标签历史，以`qualification_review/`为坐标说明权威。
- 代码：`code/`；`frozen_model.py`和`frozen_evaluate_pilot.py`为旧模型/evaluator字节相同审查副本，正式脚本仍读取原pilot路径。

CPU重算：
```powershell
python code/replay_delivery.py --root .
python code/review_delivery.py
```

实际运行机`xuhd@172.18.18.151:436`：`/raid5/xuhd/datasets/tum_synchronized_anatomy_validation_20261005`。Python位于`/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`；读取header用独立`deps`中的nibabel。原CT衍生mesh、pickle及checkpoint不入Git。源文件[选择清单](DOWNLOAD_SELECTION.json)与[268个实际下载回执](DOWNLOAD_RESULT.json)可核对。
