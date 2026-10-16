# R5.2零训练诊断复现

服务器218用户xuhd，`/raid5/xuhd/rgbd_sam3d/r52_solver_factor_diagnostic_v1`。Python：`/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`。原数据、点集和固定Body来自`/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1/previous/geometry`，原Query来自其`query_replay_frozen_coarse`。不是从独立Coarse checkpoint取起点。

1. 将本目录科学代码放入计算根code，EXPERIMENT.json放计算根。已有输入准备完成时不要重复启动。
2. prepare.py --workers8使用原noisy Depth/rays与Query重放，冻结输入。小规模CUDA grid_sample只复现旧采样的float32像素取整，不运行Backbone、不训练。Native从noisy有效格点按样本hash固定最多5000；真实域原A5000不变。
3. run.py串接solver_qa、evaluator_qa、all_fits、all_evaluation。fit.py调用原历史fit_txyz；0/1/2/3/6状态由同一路径生成，既有步骤不存在额外优化。evaluate.py使用原历史精确三角面函数。
4. summarize.py汇总分域、每seed、逐人、P95、fallback和配对变化；integrity.py重读输入、原几何和所有输出，核对EXECUTION_FREEZE。
5. 本地fetch_local.py --review下载完整指标及三例缓存网格；visualize_local.py绘制实际点云/网格，report_local.py生成HTML/Markdown。
6. package218.py生成私有完整卷；Windows backup_local.py复用原R5.1已验证的8范围直接SFTP备份并对SHA。

示例（从计算根执行，已有实验无需重跑）：

```bash
PY=/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python
export LD_LIBRARY_PATH=/raid5/xuhd/rgbd_sam3d/runtime218/env/lib
CUDA_VISIBLE_DEVICES=0 "$PY" code/prepare.py --workers 8
"$PY" code/run.py
"$PY" code/summarize.py
"$PY" code/integrity.py
```

公开目录的code用于集中审查。Windows报告/备份工具从完整仓库research/rgbd_sam3d_mhr/r52_solver_diagnostic执行，backup_local依赖同仓库已提交的r51_fine_ablation/backup_windows.py。复现已有结果使用私有冻结输入与旧geometry包；不覆盖原计算目录冒充一次新实验。

所有新几何方法都保留177.8882018mm修正上限，相对于本方法初始化。Coarse方法超限回Coarse。报告同时保存raw/applied delta与相对Official总位移；总位移超过历史上限不等于本次修正违规，因为起点已经不同。

主对照hist_med6是诊断混合流程，不是新单前向网络。其他方法用于有限匹配因子对照，不是全面全因子设计，存在对应与迭代反馈。投影与格点NN使用同一缓存Depth的全部有效XYZ；原Fine射线赋值另列一行，避免混淆采样像素射线差异。

原Body固定且保留原始npz SHA，任意方法可用共享Body与缓存camera/delta重建最终顶点；图由缓存生成，不重拟合。真实B不参与求解，Native GT不参与拟合、只作评价；原pt缓存虽包含truth字段，准备代码不从中构造观测或修正。封存Native/HuMMan TEST不读，BEHAVE是已消费官方TEST子集。

最初准备时NumPy float64像素取整未匹配CUDA半像素边界，已修正为原CUDA采样路径；先导旧指标读取一度误用修正前triangle字段，修正为triangle_txyz后通过。两份原失败日志保留，未放宽数值容差或改算法/点集。
