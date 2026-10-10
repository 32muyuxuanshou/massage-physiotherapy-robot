# 实跑目录与复现

计算服务器：`connect.cqa1.seetacloud.com:39846`，RTX6000D。根目录 `/root/autodl-tmp/rgbd_sam3d`，Python `envs/rgbd/bin/python`，本轮独立代码 `r4_code`，输出 `runs/r4_geometry_v1`。

旧 `project_snapshot/research/rgbd_sam3d_mhr` / R3 / R3.1 完整保留。R4 没有重算3600张既有 backbone cache；仅新增16张物理距离探针的缓存。原始数据和权重不进Git。

```bash
R=/root/autodl-tmp/rgbd_sam3d
PY=$R/envs/rgbd/bin/python
C=$R/r4_code
W=$R/runs/r4_geometry_v1

# 已执行，不能直接向同一已存在目录重复覆盖。
$PY -u "$C/check_r4.py" --root "$R" --out "$W/qa"
$PY -u "$C/check_r4_resume.py" --root "$R" --out "$W/resume_qa_v2" --source-commit <QA_COMMIT>
$PY -u "$C/physical_camera_probe_r4.py" --root "$R" --out "$W/physical_camera_data"
$PY -u "$C/benchmark_r4.py" --root "$R" --out "$W/concurrency"
$PY -u "$C/run_r4_pilots.py" --root "$R" --source-commit <PILOT_COMMIT>
$PY -u "$C/run_r4_evaluations.py" --root "$R" --cells "$W/pilots" --names g0 g1 g2 g3

# 同一合成身份划分；checkpoint仅按synthetic VAL选。
$PY -u "$C/train_r4.py" --root "$R" --out <FRESH_RUN_DIR> --mode g1 --seed 11 --epochs 30 --train-ids 400 --source-commit <FORMAL_COMMIT>
# 恢复必须保持完全相同的seed/epochs/train-ids/source-commit和训练源文件。
$PY -u "$C/train_r4.py" --root "$R" --out <EXISTING_RUN_DIR> --mode g1 --seed 11 --epochs 30 --train-ids 400 --source-commit <FORMAL_COMMIT> --resume
$PY -u "$C/evaluate_r4_humman.py" --root "$R" --out <FRESH_REAL_DIR> --checkpoint <BEST_PT>
$PY -u "$C/evaluate_r4_physical.py" --root "$R" --out <PHYSICAL_JSON> --checkpoint <BEST_PT>
$PY -u "$C/ablate_r4.py" --root "$R" --out <ABLATION_DIR> --checkpoint <BEST_PT>
$PY -u "$C/summarize_r4.py" --run "$W" --out "$W/summary"
```

全量真实评价仍复用原 `evaluate_r3_humman.py` 的点到精确三角面、Camera A→world→B、逐帧→等权sequence→等权identity聚合。新增的remove_hooks只负责释放Camera hook，不改变评价点或指标。

Camera B 的原始固定点集 manifest SHA记录在 `qa/RUNTIME_ASSETS.json`，与R3/R3.1共享。后续测试可能受Official预训练数据重叠影响，目前未知。

R4训练不保证逐位相同。保存best/last、Adam状态、scheduler、CPU/CUDA RNG及numpy sampler，支持epoch边界恢复；自审已验证恢复状态及开发指标一致性。混合精度只保留官方backbone native BF16，adapter/公制几何FP32。每个模型/seed在独立进程运行。

本轮已完成。正式训练源commit：`6c39a027db66e4d8f4b6604ead55926e1bbc3a28`；Best/Last的执行身份与各训练文件SHA保存在每cell。公开交付commit含后续分析/报告，不能替代此训练源版本。完整checkpoint/native缓存已传至本地和持久服务器 `/raid5/xuhd/rgbd_sam3d_backups` 并核对SHA，关机实际状态见 `SHUTDOWN_RECEIPT.json` 和执行Ledger。

```bash
# 下列只读取完成结果/保存Mesh，不重新训练或拟合。
$PY "$C/attribute_r4_camera.py" --root "$R" --base "$W/formal/g0_seed11/real" --new "$W/formal/g1_seed11/real" --out "$W/formal_camera_attribution_seed11.json"
# 同样对seed23/37运行。
$PY "$C/visualize_r4.py" --root "$R" --cells "$W/formal" --names g0_seed11 g1_seed11 --out "$W/formal_visuals"
$PY "$C/closeout_r4_native.py" --root "$R"

# 公共JSON本地重算三seed、逐人、配对帧与统计图；不需要GPU或私有Mesh。
python research/rgbd_sam3d_mhr/analyze_r4_delivery.py \
  --delivery docs/handoffs/real-scene-2026-10-10/rgbd-sam3d-r4-metric-local \
  --baseline docs/handoffs/real-scene-2026-10-10/rgbd-sam3d-r31-diagnosis-pilot/diagnostics/CHEAP_TXYZ_COMPARISON.json
```

`closeout_r4_native.py`会重新校验完成结果并写正式备份档案；重跑应先保留现有档案。审查时不需要执行训练命令。实际模型大数组使用持久备份中的 `r4_formal_native_v1.tar.gz` 和 `r4_pilot_native_v1.tar.gz`；代码/公共JSON见Git，SHA见回执。公开 `FILES_MANIFEST.json` 校验Git blob字节，Windows working copy换行可能不同；运行时源文件SHA以各训练执行身份及原生备份为准。
