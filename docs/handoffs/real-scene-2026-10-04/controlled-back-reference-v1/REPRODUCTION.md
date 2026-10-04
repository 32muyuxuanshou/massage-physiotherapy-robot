# 实际运行与审查路径

服务器：`xuhd@172.18.18.151:436`。本轮使用4个CPU人物进程，无模型加载、SAM推理或训练。Python与包版本见 `EXECUTION_ENVIRONMENT.json`。

| 内容 | 实际位置 |
|---|---|
| 本轮根目录 | `/raid5/xuhd/datasets/back_controlled_reference_v1_20261004` |
| 20份参考与60个虚拟相机观测 | 根目录下 `reference/Sxxx/reference.npz`、`K0.npz`、`K1.npz`、`K2.npz` |
| 240份最终网格、480逐点结果、240探针坐标 | 根目录下 `runs/Sxxx/{RIGID_ONLY,NORMAL_BUMP,TANGENTIAL_SHIFT}` |
| 固定输入模型缓存 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2/meshes/Sxxx/seed_0/Official.npz` |
| 实际沿用的Rigid/向量D/评价代码 | 上述 `corrected_comparison_v2/delivery/code` |
| 实际沿用的法向D | `/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003/code/normal_d.py` |
| Python | `/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python` |

## 命令顺序

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/back_controlled_reference_v1_20261004
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY "$ROOT/code/test_geometry.py"
$PY "$ROOT/code/run_controlled.py" --phase prepare
$PY "$ROOT/code/run_controlled.py" --phase dev --workers 4
$PY "$ROOT/code/run_controlled.py" --phase validation --workers 4
$PY "$ROOT/code/analyze_cached.py"
$PY "$ROOT/code/audit_correspondence.py"
$PY "$ROOT/code/audit_quality.py"
$PY "$ROOT/code/check_planar_observed_binding.py"
$PY "$ROOT/code/export_delivery.py"
```

`prepare`与拟合分支已执行的目录不能覆写。新复现应先复制至独立目录，显式修改 `common.py` 的ROOT，再重新生成冻结身份。解析检查也写文件，应在副本执行。只重算已有缓存时，无须重新拟合。

## 从数字追到文件

1. `PROTOCOL.md`、`CONTRACT.json`固定误差注入、相机、方法和评价；`SOURCE_FREEZE.json`冻结52项实际代码、合同与来源缓存，开发/验证入口逐文件实算SHA。
2. `REFERENCE_MANIFEST.json`冻结20个参考和60个相机观测文件。`reference.npz`保存原始缓存的重定位量、完整面、法向/切向注入场；相机观测保存第一层透视交点、face/bary、像素索引及相机。
3. 拟合函数只收到 `K0.points_world_m[K0.optimization_idx]`。K1/K2交点在拟合前生成，仅由评价器读取。这是同一合成几何的虚拟机位留出，**不是独立物理传感器或新真人留出**。
4. 最终方法网格 `vertices_m`已经在world米坐标中完成变换，不能再乘一次 `rigid_R/t`。INITIAL保留注入误差；其文件也保存共享Rigid求解元数据，但不表示INITIAL已应用Rigid。D另外保存位移，法向D保存标量u与固定Rigid法向。
5. 每方法的 `*_K1_metrics.npz`/`*_K2_metrics.npz`保存完全相同的评价索引、逐点表面距离、连续射线Z残差、hit与四方法common-hit。`*_probes.npz`保存已知参考与预测的8点坐标、法向。
6. `results.json`为逐case结果；汇总先双相机中位数，再同一注入类型按人物取中位数，开发4与已消费验证16分开。不同注入类型不混成一个准确率。
7. `POST_EXECUTION_INTEGRITY.json`检查冻结源、观测与240个缓存；4个开发case另从缓存精确复算K1逐点指标。

`analyze_cached.py`在准备冻结后上传，其SHA在分析前由 `ANALYSIS_CODE_IDENTITY.json`单独记录；只读取缓存、汇总和制图，不改求解。两份 `audit_*.py`逐点展开及计数，SHA保存在对应审计JSON。`check_planar_observed_binding.py`在视觉复核发现原探针位于观察区外后补充，直接读取保留的已拟合平面，检查观察区内的探针，未重新拟合；原记录/图未删除。`export_delivery.py`是后处理打包工具。后处理与所有审查文件由最终 `FILES_MANIFEST.json`及Git提交再次绑定，不冒称已包含在最初52项拟合源冻结中。最初两次打包差别仅为观测索引缩至实际优化/评价点子集、补入计数脚本；最终补充图和文档另汇总至服务器交付副本，没有重新拟合。

## Git与大文件边界

Git包含实际新代码、21份冻结基线源码、冻结法向源码、合同、完整逐case结果、60套观测索引、480份逐点指标、240份工程点坐标及全部60页对照图。观测索引中 `optimization_idx/posterior_eval_idx`保留原ordinal；`source_point_idx`是导出行对应的原ordinal，pixel/face/bary按该数组排列，不是完整稠密点云。程序生成的平面解析fixture可公开；它不含人体资产。

人体参考、完整虚拟点云和最终240份完整网格留在服务器； `SERVER_OUTPUT_MANIFEST.json`记录实际路径、大小和SHA， `FINAL_MESH_MANIFEST.json`列出全部最终网格。没有原始患者RGB、sensor depth、授权权重或原生MHR资产进入Git。

图中灰色为参考投影、紫色为预测投影、绿色为预测轮廓、蓝点为已知ENG参考点、红点为预测ENG点。对照图采用半分辨率三角形投影并集，仅用于观察；指标使用完整透视连续射线与三角面距离，不能从图片替代计算。投影点未做遮挡剔除，ENG点不是穴位。
