# R5.1实际执行与复现

计算根：`/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1`，服务器`172.18.6.218:436`，用户`xuhd`。未启动新的付费实例，服务器保持开启。

Python：`/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`。Python3.10、PyTorch2.5.1+cu118、NumPy1.26.4、SciPy1.14、nvdiffrast0.4.0；实际环境另见EXECUTION_ENVIRONMENT.txt。所有命令从计算根运行；`CUDA_VISIBLE_DEVICES`只选空闲卡，不改变种子。

## 私有资产

- 原Full Last三seed：`/raid5/xuhd/rgbd_sam3d/r5_complete_comparison_v1/checkpoints/full_s{11,23,37}_e50_last.pt`。代码load_parent强制核对SHA。
- 原始评价几何：`/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1/previous/geometry`；点集、标定、面、MHR→SMPL映射与旧评价器保持原SHA。
- 原始TRAIN特征：本轮`cache/native`、`cache/scan`；原诊断缓存负责real/behave。不是只用VAL缓存训练。
- 本轮8850份已准备Fine上下文：`prepared/s{11,23,37}/{native,scan,real,behave}`，其中每seed2950张、包括TRAIN/VAL和已消费真实开发输入。
- 三个私有备份卷：TRAINING_CHECKPOINTS.tar.gz、PREPARED_FINE_INPUTS.tar、R51_FINAL_RESULTS.tar.gz；不入Git。

上述是授权数据的私有资产，公开仓库不含数据和权重。准备后Fine训练可以直接复用prepared；若需独立重建prepared，还需要原Body/Backbone特征和原父checkpoint。prepared不代表重跑了完整RGB骨干。

## 实际执行顺序

1. restore_data218.py恢复Native；发现Scan不在历史包，transfer_scan218.py从AutoDL补齐1536份（直接SFTP、不经过FlClash）。DATA_READY与原MISSING回执同时保留。
2. 按seed运行prepare_queries218.py，生成固定Coarse、Body、Query和raw RGB Query。三个seed的Coarse允许不同，同seed四组完全相同。
3. preflight218.py：原前向/梯度等价、E0损失等价、一次更新、Coarse无梯度；只由TRAIN标定L2。
4. baseline218.py运行原Full Last Native/Scan VAL，随后SCIENCE_FREEZE冻结11个训练相关文件。
5. run_queue218.py依EXPERIMENT执行12单元；每组6轮、每轮存权重，0/2/4/6轮评价；SELECTION_FREEZE在新真实评价前冻结。bootstrap218.py是本轮首次执行的阶段串接入口，已完成，不要再启动第二份。
6. reinsert_qa218.py将各组末轮Fine装回原完整Coarse+Fine模型，48个固定缓存案例确认Body/Coarse未变。
7. evaluate_real218.py先infer每seed所有唯一选中权重，再evaluate --pilot，确认旧父结果可复现后evaluate全部502帧×21唯一状态。
8. summarize218.py生成全量表；post_integrity218.py逐个重读并核验27503文件，84权重及10542预测/指标记录。
9. 本地analyze_results.py、plot_failures.py、build_report.py生成解释、图与HTML。plot_failures需要fetch_reports.py下载的三例私有网格和旧geometry缓存。
10. pack_backup218.py --scope training/inputs/final；Windows端backup_windows.py --scope对应卷，实际SHA一致才写完成回执。

## 关键命令示例（已有结果无需重跑）

```bash
cd /raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1
export LD_LIBRARY_PATH=/raid5/xuhd/rgbd_sam3d/runtime218/env/lib
PY=/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python
CUDA_VISIBLE_DEVICES=0 "$PY" code/evaluate_real218.py --stage infer --seed 11
"$PY" code/evaluate_real218.py --stage evaluate --workers 16 --pilot
"$PY" code/evaluate_real218.py --stage evaluate --workers 16
"$PY" code/summarize218.py
"$PY" code/post_integrity218.py
```

原训练入口及参数以run_queue218.py和EXPERIMENT.json为准。原运行已完成，复现应另建计算根并显式修改路径，不能覆盖旧缓存冒充一次新运行。

## 评价口径

Native：已知同拓扑对应顶点L2、Camera平移L2。Scan：480×640透视渲染，对全目标mask的轴向Z绝对差，未命中渲染Z=0，不隐藏漏覆盖；同时保存共同命中、命中率、IoU。Native同样报告表面Z。

HuMMan：Camera A输入，原固定2048个Camera B实测点→预测三角面精确距离；每帧median/P95/≤50mm，然后frame→sequence→identity等权。

BEHAVE：K0输入，K1/2/3各自精确点→面，先相机均值，再frame→sequence→identity等权。MHR映射到拟合SMPL的PVE仅为支持证据。旧61.06mm为帧均值，本轮59.64mm为层级等权，逐帧值相同；详见AGGREGATION_RECONCILIATION.json。

真实数据不含原生MHR人体参数GT。不要把Camera B表面距离写成真Camera参数误差、解剖对应或穴位定位误差。
