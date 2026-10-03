# 运行与缓存位置

服务器：`ssh -p 436 xuhd@172.18.18.151`。本轮使用 GPU 0，RTX 2080 Ti。

| 资产 | 绝对路径 |
|---|---|
| 新实验基目录 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2` |
| 冻结代码与配置 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery` |
| 正式输出 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2` |
| 原始真人数据 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/raw/Sxxx/p_select.p` |
| Python 环境 | `/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python` |
| SAM3D 源码 | `/raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body` |
| 官方权重 | `/raid5/xuhd/sam3d_s01_pilot_20260906/weights/model.ckpt` |
| MHR 资产 | `/raid5/xuhd/sam3d_s01_pilot_20260906/weights/assets/mhr_model.pt` |
| 16384 anchors | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/run_assets/anchors.npz` |
| 历史三方法输出，保留不覆盖 | `/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/inference_3method_v1` |

以 S107、seed 0 为例，以下均相对于 `run_v2`：

- `initial/S107/official_prediction.npz`：一次新的 RGB 推理，完整 MHR 初值。
- `inputs/S107/input.npz`：原始 RGB、原始 depth、相机点云、K、bbox、后背 ROI。
- `inputs/S107/split_0.npz`：训练、留出、后背评价及 torso 评价的实际点索引。
- `meshes/S107/seed_0/Official_Rigid_D.npz`：最终顶点、面、完整 MHR prior、外部 R/t/D、有效 camera translation、实际优化点索引。其它方法在同目录。
- `evaluation/S107/seed_0/Official_Rigid_D_metrics.npz`：逐点评价值、射线命中和共同命中标记。
- `visualizations/S107/seed_0/comparison.jpg`：原始 RGB 与全部五组方法。
- `visualizations/S107/seed_0/*_render.npz`：同一缓存 Mesh 的透视渲染 depth。

大网格、原始 RGB/点云和授权权重留在服务器。Git 交付包含完整配置与代码链接、结果、逐点残差、划分索引、缓存身份、全部展示图；没有把这些公开结果误称为原始数据全集。

Rigid/D 结果必须按其显式外部变换解释，不能只把 MHR pose 参数重新 forward 后当作最终结果。所有几何单位为米，报告距离换算为毫米。
