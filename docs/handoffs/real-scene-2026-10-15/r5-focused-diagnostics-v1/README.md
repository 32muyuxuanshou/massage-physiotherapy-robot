# R5 同模型粗细诊断与旋转对照

状态：离线部分已完成；完整 RGB-D→Mesh GPU 计时按用户选择暂缓。没有新训练，没有启动付费 GPU，没有关闭服务器。

先看 [结论](FINAL_REPORT.md)，或下载本目录后打开 [完整 HTML](REPORT.html)。GitHub 显示 HTML 源码；本地 HTML 可直接阅读全部图表。

## 实际完成

- 同一个 R5 Full Last 的内部 Coarse 与最终 Fine：Native VAL 400、HuMMan TRAIN/VAL 232、BEHAVE 270，共 902 个输入 × seeds 11/23/37 = 2,706 条。不是把独立训练的 Coarse 当内部 Coarse。
- HuMMan 232 帧 Camera A-only 匹配平移/刚体对照；使用原 Official 缓存，逐文件 SHA 校验，232/232 历史 Txyz 平移复现。
- Native VAL 400 帧真实整体旋转/平移参数替换；只加载原 MHR CPU 资产重新解码，没有运行 SAM3D Backbone。400/400 物理旋转和刚体关系核验通过。
- 全部帧 CDF、每 seed/身份结果、两例实际 B 点云几何图和全部负收益索引。

## 结论

Fine 总体有效，但有负收益，不能只归因为步长不足。HuMMan VAL 上 19.19→14.36 mm，历史 Official+Txyz 为 11.23 mm。BEHAVE PVE 77.33→61.06 mm，历史 Official+Txyz 为 56.24 mm；这两个数据集、两种误差不能混算。

A-only 匹配刚体相对匹配平移在 HuMMan VAL 上 11.12→10.32 mm，40 帧中 14 帧变差；收益存在但不普遍。Native 真值旋转替换反而恶化，说明在其余人体参数预测错误时，参数替换不是表面误差最优上限；补偿机制仍是解释，未作因果证明。

建议保留硬解耦和 Fine，集中研究 Fine 负收益与 Camera/表面监督目标差异，不自动增加旋转、多步或新训练。完整效率比较尚未测，不能宣称加速。

## 数据与指标

- Native：50 VAL 身份 /400 图，Camera 向量与对应顶点真值分别报告。
- HuMMan：TRAIN 18 人/192 帧、VAL 4 人/40 帧分开，固定 B 的 2,048 点到精确三角面。A 拟合、B 评价。
- BEHAVE：既有已消费身份的官方 TEST 子集，3 人/90 序列/270 帧。PVE 对拟合 SMPL-H 参考；K1/K2/K3 点集另报，保留物体与异常深度限制。
- 封存 Native/HuMMan TEST 不读；没有 B 调参、B 拟合或坏帧删除。不同 seed 不是新增独立人物。
- HuMMan Official+Txyz 是一个共享历史缓存；BEHAVE Official 为原三 seed 缓存。确定性拟合不伪装成三次独立训练。

## 审查文件

- `SUMMARY.json`：每 seed、每身份、每序列聚合，以及 Native 参数替换全记录。
- `Q1_RECORDS.json`、`PER_FRAME.csv`：2,706 条原始对照。
- `RIGID_RECORDS.json`：232 帧两种拟合的完整轨迹及区域结果。
- `ALL_FRAME_CHANGE_INDEX.csv`：所有正负收益，包含 P95 变坏的帧。
- `FEATURE_ASSOCIATIONS.json`：描述性相关，不作遮挡因果结论。
- `GEOMETRY_FIGURE_INDEX.json`：例图选择原因、点数及颜色饱和说明。
- `RUN_ASSETS.json`、`SOURCE_SHA256.json`、`POST_INTEGRITY.json`、`REMOTE_POST_INTEGRITY.json`：资产和实际源文件核验。
- `code/`：本轮完整代码；`frozen_historical_code/`：实际使用的原评价与 Txyz 函数来源，未改实现。
- `SELF_AUDIT.md`：已完成核验及未测项目。

## 复现

原项目代码位于 `research/rgbd_sam3d_mhr/r5_diagnostics`。使用 Python、NumPy、SciPy、Matplotlib；只有服务器 MHR 参数替换需要原环境的 PyTorch。

1. 在原 AutoDL 运行 `export_geometry.py --out /root/autodl-tmp/rgbd_sam3d/evaluations/r5_focused_diagnostics_v1`；它只读取既有 Last 预测和固定点集，实际 SHA 不匹配会停。
2. 下载 `R5_FOCUSED_GEOMETRY.tar`，按 `EXPORT_RECEIPT.json` 校验 SHA，再解压到独立本地目录。
3. 先运行 `analyze_cached.py --geometry <root>/geometry --out <root>/q1 --pilot`，通过后同命令去掉 `--pilot`。
4. 使用原 232 个 Official NPZ，运行 `rigid_diagnostic.py --geometry <root>/geometry --official <historical_original_assets/official> --out <root>/rigid`。新增均值平移不是历史中位数 Txyz，详见固定 JSON 合同。
5. 原服务器运行 `native_root_substitution.py`，下载并核对 `NATIVE_ROOT_SUBSTITUTION.tar`，解压到同一 `<root>`。
6. `summarize.py --root <root> --out <root>/reports`；`visualize_geometry.py --root <root> --official <historical_original_assets/official>`；`build_report.py --root <root>`。
7. `post_integrity.py --root <root> --official <historical_original_assets/official>` 复核结果覆盖、源文件及变换。

私有几何缓存、源点集及大型 NPZ 不入 Git；保存于 Windows `E:/项目-按摩理疗机器人/output/r5_focused_diagnostics_v1`、原 AutoDL 独立诊断目录和 218 备份目录。最终实际 SHA 备份回执随目录交付。GPU 全流程计时仍待用户之后恢复 GPU；当前离线结果不依赖它。
