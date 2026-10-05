# 作者观测点云 → 冻结场 → 患者 Mesh／规则

详见 [实际结果与边界](FINAL_REPORT.md)。本包是工程接口验证，只有 S107 一个已消费样本，不是新泛化实验。

代码复用同一仓库已有三个冻结包：

1. `real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2` 的输入、相机和划分生成器；与其 `-execution/results/inputs` 的历史数组／split 身份对账。
2. `reference-anchored-surface-field-v2` 的模型和患者解码接口。
3. `prone-reference-rule-workbench-v1/site/cases` 的既有 Mesh，以及 V2 的冻结规则投影器。

## 本地实际运行

Python 3.11、CPU PyTorch 2.4.1、NumPy 1.26.4；四线程。隔离依赖路径如下，没有替换系统 PyTorch。运行从项目根目录执行：

```powershell
$env:PYTHONPATH='E:/项目-按摩理疗机器人/output/anatomical_surface_method_foundation_v1/cpu_deps_241;E:/项目-按摩理疗机器人/output/anatomical_surface_method_foundation_v1/cpu_deps'
$env:PYTHONIOENCODING='utf-8'
python docs/handoffs/real-scene-2026-10-05/observed-prone-surface-interface-v1/code/run_observed.py --raw output/pressurepose_prone_review/S107_p_select.p --checkpoint output/reference_anchored_surface_field_v2/STRUCTURE_ONLY_HARD_JOINT.pt --private-output output/observed_prone_surface_interface_v1
python docs/handoffs/real-scene-2026-10-05/observed-prone-surface-interface-v1/code/replay_cache.py --private-output output/observed_prone_surface_interface_v1
```

服务器恢复后同一命令可指向已有原始文件和冻结 checkpoint。模型不需 CUDA；不得因此把该结构权重升级为正式模型。`--subject` 为对应患者编号，当前缓存 Mesh 固定 seed0。

## 网页审查者可独立复查

克隆完整项目并安装兼容 CPU PyTorch/NumPy/SciPy/OpenCV/Matplotlib，即可运行：

```text
python docs/handoffs/real-scene-2026-10-05/observed-prone-surface-interface-v1/code/replay_cache.py
```

这条命令只读取公开缓存、历史 split 和预测 Mesh；不读原始 RGB/点云，不载入 checkpoint、不运行模型。它重解码建议坐标、重生成规则面绑定、核查 train/held-out 索引及对照数值，再从缓存画图。模块 import 包含 PyTorch，但没有模型前向。

添加 `--private-output` 才读取本地原始输入缓存并画 RGB 叠图。该图在 `E:/项目-按摩理疗机器人/output/observed_prone_surface_interface_v1/S107_ACTUAL_INPUT_OVERLAY.png`，不进入 Git。

公开 NPZ 只有预测 Mesh、场输出、修正量和索引；原始患者 RGB、深度、作者点云、权重不入库。结果逐患者保存，不能覆盖历史方法交付。
