# 服务器恢复后的执行说明

目标主机：`ssh -p 436 xuhd@172.18.18.151`。本轮服务器停机，**没有在该主机执行正式推理/优化**，没有新核实 GPU/环境/实际权重路径。

历史原始数据根：`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/raw`，预期 `Sxxx/p_select.p`。历史 SAM repo：`/raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body`。两处均需恢复后现场核实。

新代码推荐传至 `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery`；新输出建议为同级 `run_v2`。不要复用原 `inference_3method_v1` 或旧 L1 结果目录。

## 顺序

1. 将本交付完整传至 `delivery`，含 `FILES_MANIFEST.json`；大缓存和原数据留服务器。保持现有环境，不先重建环境或安装新 Torch。
2. 查看 `nvidia-smi`、当前 Python/Torch/CUDA，找到已授权 Official checkpoint、MHR `.pt` 和 16384-anchor `.npz`。下列三个路径必须填真实已有文件，不能把示例当已核实路径。
3. 运行只读 preflight；核对原 20 个 `p_select.p` 与资产 SHA256，import 官方包，但不推理。
4. `--stage dev`：先冻结 S104/S107/S165/S187 的点划分，做数据源相机 QA，再推理/训练点拟合/缓存/评价/可视化。要求参数 forward round-trip ≤0.1 mm，用于确认 O2 的初值表示正确；这不是人体测量精度阈值。结构通过不要求数值变漂亮。
5. 四个开发样本报告和图片复核后，再 `--stage full`。它强制要求开发结构 Gate 为 PASS，并复用已生成 Official 初值。不得依据测试结果重选样本、改 ROI 或 D 权重。
6. 结束后核对 300 条唯一记录、20 次新 Official 推理、300 张方法叠图/残差图及 60 张人物—种子对照页。所有失败保留，执行异常不吞掉。

## 命令模板

从已经核实的 GPU Python 环境运行，下列 `CHECKPOINT/MHR/ANCHORS` 为待现场填写的文件路径。

```bash
DELIVERY=/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery
RAW=/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/raw
SAM_REPO=/raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body
OUT=/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2
CHECKPOINT=/replace/with/verified/model.ckpt
MHR=/replace/with/verified/mhr_model.pt
ANCHORS=/replace/with/verified/16384_anchors.npz

python "$DELIVERY/code/preflight.py" --report /tmp/pressurepose_local_code_preflight.json
python "$DELIVERY/code/server_preflight.py" --raw "$RAW" --sam-repo "$SAM_REPO" \
  --checkpoint "$CHECKPOINT" --mhr "$MHR" --anchors "$ANCHORS" \
  --report /tmp/pressurepose_server_preflight.json
python "$DELIVERY/code/run_comparison.py" --stage dev --raw "$RAW" --sam-repo "$SAM_REPO" \
  --checkpoint "$CHECKPOINT" --mhr "$MHR" --anchors "$ANCHORS" --out "$OUT"
```

开发四人完成并核查后，用相同参数运行：

```bash
python "$DELIVERY/code/run_comparison.py" --stage full --raw "$RAW" --sam-repo "$SAM_REPO" \
  --checkpoint "$CHECKPOINT" --mhr "$MHR" --anchors "$ANCHORS" --out "$OUT"
```

缓存重算与复画各自独立，不加载模型、不重新拟合：

```bash
python "$DELIVERY/code/evaluate_cache.py" --out "$OUT"
python "$DELIVERY/code/make_visuals.py" --out "$OUT" --subjects S104 S107 S165 S187
python "$DELIVERY/code/aggregate_results.py" --out "$OUT" --subjects \
  S103 S104 S107 S114 S118 S121 S130 S134 S140 S141 S145 S151 S163 S165 S170 S179 S184 S187 S188 S196
```

输出包括 `RUN_FREEZE.json`、`ENVIRONMENT.json`、阶段执行 ledger、输入/划分、完整 Official prediction、每分支 Mesh NPZ/JSON、逐点评价、相机 QA、全量图及 seed→subject 聚合。启动与结束对交付/运行资产重验。若一次分支缓存中断，只恢复完整缓存或使用新运行目录；不将旧 CSV 当执行完成。

`prepare_delivery.py`、`prepare_roi.py` 是已经运行的本地制备工具。正式服务器不再运行它们，否则会覆盖冻结合同来源；直接使用交付文件。运行时也不调用原历史 `baseline_v1.py` CLI。
