# 大规模解剖来源与联合表面/坐标场基础 V1

[事实报告](FINAL_REPORT.md) · [方法设计](METHOD_DESIGN.md) · [论文学习](LITERATURE_LEARNING.md) · [训练合同](TRAINING_SPEC.json) · [来源角色](SOURCE_ROLE_FREEZE.json)

这轮把研究向更大数据和可训练方法推进：实际读取完整V3档案目录、下载到服务器、建立18等级代理构造器与三种模型/两种先验的训练评价路径。GPU四例训练路径和真实四例来源处理已完成，CPU三种模型的前向/反向/候选解码已完成。**完整V3尚未核实下载结束，大规模训练没有运行，尚无新方法准确率。**

## 阅读顺序

1. `FINAL_REPORT.md`：已运行的事实和未完成项。
2. `METHOD_DESIGN.md`：它与现役SAM/MHR、规则流程的连接及目前缺口。
3. `MODEL_PATH_CHECK.json`、`prototype_check/CACHE_REPLAY.json`、`structure_check/CACHE_REPLAY.json`：实际可复查结果。
4. `code/`、`TRAINING_SPEC.json`：后续完整训练、评价和汇总如何执行。

## 运行位置

服务器：`xuhd@172.18.18.151:436`，根目录：
`/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005`

Python：`/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`。来源抽取额外设置：

```bash
export TMPDIR=/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005/tmp
export MPLCONFIGDIR=/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005/mpl_cache
export PYTHONPATH=/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005/deps
```

下载原进程已改用残余512MiB范围并发完成；启动PID `40253`，下载后来源准备PID `50621`。记录在`DOWNLOAD_PROGRESS.json`。服务器后来出现磁盘等待与SSH失败，PID只表示启动事实，不代表目前仍存活。

恢复后先核对`DOWNLOAD_RESULT.json`的作者MD5，未完成则用`complete_full_v3.py`续传；再执行`build_field_dataset.py --all-adult --workers 8 --resume`。不要重复启动仍在正常运行的进程。训练/评价代码在SSH中断后仍有本地正常路径修改，**必须先把本次Git交付的最新code同步到服务器**。完成成人来源资格后再运行`run_field_grid.py`；其最低资格数量条件在`TRAINING_SPEC.json`。

## 本地可重算

以下命令从本交付目录运行：

```powershell
python code/replay_prototype.py
python code/review_structure_check.py
```

`check_model_paths.py`使用PyTorch。本轮Windows官方2.4.0 CPU轮子DLL加载失败，按[官方对应问题](https://github.com/pytorch/pytorch/issues/131662)改用任务独立目录中的2.4.1+cpu、NumPy1.26.4，三条正常路径通过；没有修改服务器2.4.0+cu121，也没有修改本机基础Python。

原始CT/骨骼标签ZIP、完整权重和安装依赖均不进Git。本包只含代码、协议、公开元数据、四例派生皮肤/代理缓存和可展示图片。
