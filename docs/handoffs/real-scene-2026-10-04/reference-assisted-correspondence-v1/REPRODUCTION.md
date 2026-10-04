# 运行和复查说明

服务器 `xuhd@172.18.18.151:436`。当前根目录：`/raid5/xuhd/datasets/back_reference_assisted_v1_20261004`。Python：`/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`。4个CPU人物进程；没有新Mesh求解、SAM推理、GPU模型加载或训练。环境见 `EXECUTION_ENVIRONMENT.json`。

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/back_reference_assisted_v1_20261004
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY "$ROOT/code/test_correspondence.py"
$PY "$ROOT/code/run_references.py" --phase prepare
$PY "$ROOT/code/run_references.py" --phase dev --workers 4
$PY "$ROOT/code/run_references.py" --phase validation --workers 4
$PY "$ROOT/code/analyze_results.py"
$PY "$ROOT/code/audit_inputs_and_noise.py"
$PY "$ROOT/code/export_delivery.py"
```

已完成目录不覆写。新复现应复制至独立ROOT并重新生成身份。原表面和参考位于 `/raid5/xuhd/datasets/back_controlled_reference_v1_20261004`：`runs/Sxxx/<case>/D_VECTOR.npz` 是固定表面，`reference/Sxxx/reference.npz` 是程序生成参考，K0/K1/K2均为精确虚拟相机。原交付绑定到 `08128e14f881805a316e642c1f120810c22c7772`，其review manifest SHA在runner常量中固定。

## 数据流

- `inputs/Sxxx/<case>.npz`只含4个输入身份与exact/noisy位置、实际噪声；不含4个考试点真值。
- `evaluation_truth/Sxxx/<case>.npz`保存8个工程点的已知参考及法向；runner在全部估计返回后才打开。QUERY索引固定[3,4,5,6]，INPUT固定[0,1,2,7]。
- `correspondence.estimate`只接收预测V/F、canonical绑定、4参考位置；图距离和RBF带宽都由预测几何计算，不使用真值查询点或K1/K2点云。
- `runs/Sxxx/<case>/*.npz`保存所有8个输出的xyz、法向、face/bary、投影前位置、偏移、实际输入/考试索引；两个参考辅助方法另存图距离。输出属于固定表面上的新对应，不能当改进后的Mesh顶点。
- `results.json`报告4个未输入点的主指标与8点展开；输入点分数仅支持。`PER_PROBE_RESULTS.csv`共1440行，其中720行是未输入考试。
- `FIXED_SURFACE_METRICS.json`仅继承原D_VECTOR的K1/K2指标。几何SHA逐case一致，不能从这里宣称本轮降低了surface误差。

## 冻结与核验

407项源/输入/真值/合同/库文件在估计前冻结，开发、验证及结束都实算SHA；原60固定表面全部未改变。原拓扑8点与60个FIXED缓存完全一致；180个点位缓存的全部数值从缓存复算。

新7个脚本在准备前上传并冻结；`audit_inputs_and_noise.py`在正式结果后仅做只读审计，SHA单独记录在审计JSON；没有重选点或改变算法。审查包再由 `FILES_MANIFEST.json`与Git提交绑定。该审计验证5 mm输入长度、跨case共用噪声、参考/考试身份分离，并独立复算线性噪声传递。没有医学正确性签发。

交付后的独立数值核验脚本为 `code/verify_delivery.py`，只需Python与NumPy，在本地运行：

```bash
python code/verify_delivery.py
```

它不调用求解器，实读180个点缓存、60个输入和60个评价参考，重算全部逐点/主要指标、18组汇总及120配对，核对60张图片SHA和132项已导出的本轮冻结文件。结果见 `DELIVERY_NUMERICAL_VERIFICATION.json`。完整网格重建检查在服务器原runner内完成，本地包没有完整Mesh，不能声称这一步在本地重做。该核验脚本为结果后的只读检查，不属于估计前7脚本冻结。

## 图与文件边界

每页K0/K1/K2三视图、FIXED/EXACT/NOISY5三方法；背景都是同一预测表面。蓝点为已知考试点，红点为输出，橙叉为给定参考；FIXED里的橙叉只显示作对照，未参与计算。ROI来自参考/固定点投影加45px边距，仅用于图片，三方法相同且等比缩放。没有原患者照片或传感器拍摄的reference。

Git交付所有派生输入、评价参考、180个点位缓存、完整结果和60页图；不含原RGB、原sensor depth、权重或完整人体网格。完整网格沿用服务器父实验不复制；固定表面SHA见 `CASE_MANIFEST.json`。这些参考和输出是合成几何上的工程点，不能自动解释为临床穴位或自动检测标签。
