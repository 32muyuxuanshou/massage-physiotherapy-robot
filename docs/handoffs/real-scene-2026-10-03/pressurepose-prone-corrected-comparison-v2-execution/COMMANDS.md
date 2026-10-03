# 实际执行命令

正式科学代码保持准备提交 `bfbdf095b89b0142b0e6fbe6fdf5ee3da842e76d` 的文件原字节，不在看到结果后改方法、权重、ROI 或阈值。下面是在服务器执行的命令；输出目录为独立新目录，没有覆盖历史实验。

```bash
base=/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2
py=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
sam=/raid5/xuhd/sam3d_s01_pilot_20260906

CUDA_VISIBLE_DEVICES=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 "$py" -u \
  "$base/delivery/code/run_comparison.py" --stage dev \
  --raw /raid5/xuhd/datasets/pressurepose_pselect_real_20260928/raw \
  --sam-repo "$sam/sam-3d-body" --checkpoint "$sam/weights/model.ckpt" \
  --mhr "$sam/weights/assets/mhr_model.pt" \
  --anchors /raid5/xuhd/datasets/pressurepose_pselect_real_20260928/run_assets/anchors.npz \
  --out "$base/run_v2" > "$base/dev.log" 2>&1

CUDA_VISIBLE_DEVICES=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 "$py" -u \
  "$base/delivery/code/run_comparison.py" --stage full \
  --raw /raid5/xuhd/datasets/pressurepose_pselect_real_20260928/raw \
  --sam-repo "$sam/sam-3d-body" --checkpoint "$sam/weights/model.ckpt" \
  --mhr "$sam/weights/assets/mhr_model.pt" \
  --anchors /raid5/xuhd/datasets/pressurepose_pselect_real_20260928/run_assets/anchors.npz \
  --out "$base/run_v2" > "$base/full.log" 2>&1
```

Full 阶段复用已验证的开发初值和网格，并重新评价/绘图。每人仍只有一次新的 Official 推理，不能把 60 条 Official 种子评价算作 60 次模型推理。

正式结束后的独立重算命令：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 "$py" -u \
  "$base/postrun_tools/audit_cached_execution.py" \
  --delivery "$base/delivery" --out "$base/run_v2" \
  --history /raid5/xuhd/datasets/pressurepose_pselect_real_20260928/inference_3method_v1
```

该脚本读取所有缓存 Mesh，在临时目录重算 300 条结果和逐点残差，再逐字段/逐数组精确比较；没有推理或优化调用，原 Mesh/原评价文件不改。脚本及输出纳入本次执行交付，而不混入原冻结科学代码。

本机网页展示导出命令：

```powershell
python code/export_delivery.py `
  --source E:/项目-按摩理疗机器人/output/pressurepose_prone_corrected_v2_server_run/full_verified_snapshot `
  --out E:/项目-按摩理疗机器人/docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2-execution `
  --history-csv E:/项目-按摩理疗机器人/output/pressurepose_prone_review/l1_fit/results/l1_eval_rows.csv
```

导出器复制全部数值/索引/元数据和全部图片；PNG 仅转换成相同分辨率的 JPEG 展示版，不重算、不拟合、不按结果筛图。服务器保留原图，逐图原始与展示 SHA256 在导出 manifest 中。
