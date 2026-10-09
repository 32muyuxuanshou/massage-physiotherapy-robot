# R3 多 seed 结果复核（2026-10-10）

九次正式训练已完成：500 个合成 MHR 参数身份、4,000 张图，三模型 × seeds 11/23/37 × 30 轮，Batch 16，共同学习率 3e-4。学习率和最佳 checkpoint 只按合成 VAL 选择。TEST 未评价；真实数据未参与训练。

## 事实结果

数值为三个 seed 的均值 ± 样本标准差。两列误差口径不同，不能互相比较。

| 方法 | 合成 VAL 全身对应顶点距离（mm） | HuMMan 真实 VAL 独立 Camera B 表面距离（mm） |
|---|---:|---:|
| Official | — | 30.59（固定起点） |
| RGB-only adapter | 79.29 ± 0.68 | 29.63 ± 1.62 |
| Spatial Residual RGB-D | 90.08 ± 0.20 | 73.05 ± 14.98 |
| Cross-Attention RGB-D | 86.57 ± 1.93 | 24.84 ± 2.80 |

合成列为 50 个 VAL 身份、400 张图的对应顶点平均欧氏距离；身份等权，再跨 seed 汇总。真实列为 4 个 VAL 身份、40 时间点的独立观测点到三角面距离：frame median → sequence mean → identity mean，再跨 seed 汇总。它不是穴位误差或真实裸露皮肤的绝对精度。

Cross-Attention 在真实 VAL 的三个 seed 都优于各自 RGB-only 和 Official。平均比 Official 降低约 18.8%，比 RGB-only 降低约 16.2%；真实 VAL 的 P95 为 64.10 mm，Official 为 69.84 mm；50 mm coverage 为 82.51%，Official 为 74.43%。真实 VAL 中这三个指标方向一致。

合成结果则相反：RGB-only 最好，Cross-Attention 在三个 seed 都比 RGB-only 差，成对平均差 +7.29 mm；Residual 平均差 +10.79 mm。差异不能简单归因于一个随机 seed。

## 不能省略的反面证据

真实 TRAIN 角色的 18 个身份、192 帧同样只用于迁移评价，没有参与训练。Cross-Attention 的身份等权 frame-median 均值为 52.62 mm，Official 为 53.97 mm，改善很小；但 P95 从 119.74 升至 128.63 mm。RGB-only 为 59.79 mm，Residual 为 78.17 mm。不能只引用真实 VAL 的改善，声称真实迁移已经全面解决。

已生成 172 张合成预测对照，覆盖每个 seed 的全部 50 个 VAL 身份的固定 camera-2 view，并另加每 seed 最差 8 张；没有用这些图替代完整逐帧结果。camera-2 是预设机位，并不保证每种扭转姿态都严格后背朝向。

本次人工查看了一个固定 view 和一个最差案例，仍可见严重姿态/对齐失败；没有声称已逐张人工审完 172 张。最差案例中 RGB-only 的对应顶点误差约 944 mm，两个 RGB-D 分支约 487/493 mm。少数极端案例有改善，但 Cross 的合成逐帧 P95 仍高于 RGB-only。2D 覆盖看起来接近，仍可能有较大的三维和对应关系误差。

## Depth 是否真正起作用

Cross-Attention 的合成 VAL：

| Depth 输入 | 对应顶点误差（mm，三个 seed 平均） |
|---|---:|
| 正确 | 86.57 |
| 跨身份错配 | 95.29 |
| 同身份另一姿态 | 92.27 |
| 局部 depth/mask patch 扰乱 | 87.05 |
| 缺失 | 157.12 |
| 整体 +200 mm | 86.58 |

错配会使结果变差，说明模型会受 Depth 输入影响。但是错配同时改变有效区域 mask，尚不能把全部改善归因于公制深度值。

整体 Depth 加 200 mm 后，Cross 的预测 Mesh 平均只变化 3.55 mm，camera Z 的有符号平均变化约 +2.40 mm。该反应很弱；可能更依赖 RGB/相对形状，也可能抑制不一致的输入偏移，不能直接证明具备正确的绝对深度推理。

缺失 Depth 时结构会回退 Official，因此缺失结果大幅退化不能单独作为 Depth 几何价值的证据。

## 我的判断和下一项

保留 RGB-only 为强基线，保留 Cross-Attention 为优先研究候选；Spatial Residual 暂不作为主路线。Cross 的真实开发集改善值得继续，但当前数据未验证俯卧后背专用表面或穴位，不能据此放行按摩定位。

下一项优先做小范围机制检查：固定 valid mask/rays，仅替换 Depth 数值；核对真实迁移失败图与共同命中情况；区分相对形状信息和公制距离信息。再据这些事实决定是否改融合位置或解冻少量 Decoder，不直接开始又一轮大训练。本轮停在审查交付。

## 完整交付

- `completed_results/RESULTS.md`、`MULTISEED_SUMMARY`、`PAIRED_SEED_COMPARISONS`：合成完整结果。
- `completed_results/formal/cells/*/run`：每 seed 的 best/last 指标、曲线、全部 VAL 逐帧数值、Depth 消融与压缩训练日志。
- `completed_results/formal/cells/*/real` 和 `completed_results/real/official`：真实逐帧、逐 sequence、逐身份结果。
- `completed_results/visualizations`：172 张合成对照和训练曲线，均从保存的预测生成。
- `completed_results/EXECUTION_LEDGER.json`、执行身份、环境和 collection receipt：复现记录。
- `completed_results/BACKUP_RECEIPTS.json`：123 次经过 SHA256 核对的 checkpoint 备份，覆盖全部九个 cell 的末轮 checkpoint，另有 best 历史快照。本地 E 盘与 172.18.6.218 均有备份。

计算根目录仍为 `/root/autodl-tmp/rgbd_sam3d`，完整缓存网格/参数与 checkpoint 在 `runs/r3_multiseed_v1/formal/cells`。原始数据、模型权重和 checkpoint 不入 Git。

本轮执行源码版本 `521b42ba`；完整原始审查包提交 `ae1c454aa7e5d5cdd4de94646b02217ba5778622`。本复核补充提交只更新结果说明，不改变实验。
