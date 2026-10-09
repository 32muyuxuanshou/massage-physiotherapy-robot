# 运行与独立审查入口

AutoDL 工作根目录：`/root/autodl-tmp/rgbd_sam3d`。Python：`envs/rgbd/bin/python`。不在这里保存登录密码、token 或数据下载凭证。

本轮计算：`runs/r31_diagnosis_pilot_v1`。训练快照：`project_snapshot/research/rgbd_sam3d_mhr`。机制消融独立快照：`r31_inference_code`。原生 mesh、checkpoint 和真实数据放在私有运行目录及备份，不入 Git；完整可读指标、索引、配置、源代码、图片进入本交付。

## 科学执行顺序

以下展示本轮实际入口。运行依赖已准备的 R3 frozen cache、HuMMan 配准数据、Official 权重和 MHR 资产；不是只有此文件夹就能重新下载所有授权权重。

```bash
ROOT=/root/autodl-tmp/rgbd_sam3d
PY=$ROOT/envs/rgbd/bin/python
CODE=$ROOT/project_snapshot/research/rgbd_sam3d_mhr
RUN=$ROOT/runs/r31_diagnosis_pilot_v1

$PY $CODE/diagnose_r31.py --root $ROOT --out $RUN/depth --config $CODE/R31_CONFIG_V1.json --task depth
$PY $CODE/diagnose_r31.py --root $ROOT --out $RUN/txyz --config $CODE/R31_CONFIG_V1.json --task txyz
$PY $CODE/visualize_r31_failures.py --root $ROOT --out $RUN/failure

$PY $CODE/train_r31_pilot.py --root $ROOT --out $RUN/qa/geometry_attention --config $CODE/R31_CONFIG_V1.json --mode geometry_attention --source-commit 16e161489fafbc041765c5ec0d80ced944fca8f1 --qa-only
$PY $CODE/train_r31_pilot.py --root $ROOT --out $RUN/qa/mhr_refinement --config $CODE/R31_CONFIG_V1.json --mode mhr_refinement --source-commit 16e161489fafbc041765c5ec0d80ced944fca8f1 --qa-only

$PY $CODE/run_r31_pilots.py --root $ROOT --out $RUN/pilots --config $CODE/R31_CONFIG_V1.json --source-commit 16e161489fafbc041765c5ec0d80ced944fca8f1
$PY $ROOT/r31_inference_code/run_r31_ablations.py --root $ROOT --pilot $RUN/pilots --out $RUN/ablations_fast
$PY $ROOT/r31_inference_code/visualize_r31_pilots.py --root $ROOT --run $RUN --out $RUN/pilot_visuals
```

各任务实际上有并发，不按上面的命令展示顺序串行等待。日志与 marker 保留在私有包；`code_training` 是训练 commit 的文件，`code_inference` 记录后续机制干预和展示脚本，默认训练 forward 未改变。

## 文件审查顺序

1. `EXPERIMENT_CONTRACT.md` + `manifests/R31_CONFIG_V1.json`：预算、划分、Camera A/B 权限、旧新诊断的差异。
2. `code_training/fusion_r31.py` + `train_r31_pilot.py` + `train_r3_multiseed.py` + `render_losses.py`：实际模型、冻结和训练；不要只读示意图。
3. `diagnostics/DEPTH_SOURCE_DIAGNOSTIC.json`：所有条件/每帧响应；`CHEAP_TXYZ_COMPARISON.json`：7个历史模型基底、1624次修正及所有B指标/trace/fallback。
4. `pilots/<mode>/run/RESULTS.json`、`real/HUMMAN_RESULTS.json` 与 `ablations/<mode>/CANDIDATE_ABLATIONS.json`：四组同预算完整数值。
5. `manifests/CAMERA_A_FIT_INDICES.json` 与 `CAMERA_B_POINTS_MANIFEST.json`：前者拟合，后者考试，禁止混用。
6. `failure_visuals`/`pilot_visuals`：全部预先选定失败与普通案例；图片只来自缓存 mesh。
7. `BACKUP_RECEIPT.json` 与 `DELIVERY_FILE_MANIFEST.json`：私有缓存/权重去向、交付文件 SHA256。

## 失败和修复记录

- 第一遍 Cheap Txyz 的计算和评价结束后，JSON 写出碰到 `numpy.bool_` 不能序列化；将 fallback 转为 Python `bool` 后完整重算，算法/点集不变，失败日志保留。
- 第一遍失败图使用全画幅，人体太小；按已有 bbox 放大展示后重画，不重新推理或拟合。
- 初始消融与两组训练竞争 CPU 线程；中止该部分消融，保留原输出，改为每个 inference 进程2 CPU threads，在独立 `ablations_fast` 重算。训练进程未中止，训练合同未改变。

最后通过 AutoDL 官方 `/usr/bin/shutdown` 关闭实例；应先完成备份与交付，再执行关机。平台关机文档：[AutoDL 节省费用](https://www.autodl.com/docs/save_money/)。
