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

截止前停止启动新训练，保留最佳/末轮；完整checkpoint/native缓存要先传至本地和持久服务器 `/raid5/xuhd/rgbd_sam3d_backups` 并核对SHA。最后再执行AutoDL官方 `/usr/bin/shutdown`，不会在R3.1结束时提前关机。
