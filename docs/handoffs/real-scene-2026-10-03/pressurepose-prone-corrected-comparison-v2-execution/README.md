# 俯卧背部 Mesh 修正版：正式执行交付

**2026-10-03 已完成：20 人 × 5 方法 × 3 种子 = 300 条评价，全部缓存重算精确一致。**

Rigid+D 在同源空间留出点上确有稳定增益；但仍存在明显图像轮廓错位，且相机合同尚未获得物理标定验证。当前不能把约 3.66 mm 的残差称为患者背部或穴位的真实定位精度。

| 先读什么 | 内容 |
|---|---|
| [最终报告](FINAL_REPORT.md) | 三个问题的回答、五组结果、失败与下一步 |
| [全部可视化](VISUAL_INDEX.md) | 60 页五组对照，全部 800 张运行展示图；无好坏筛选 |
| [人工视觉复核](VISUAL_REVIEW.md) | 实际查看 28/60 对照页及额外切片图，明确检查范围 |
| [聚合结果](results/AGGREGATED_RESULTS.json) | 开发/测试/全体、逐人、配对变化 |
| [300 条逐种子记录](results/per_method_subject_seed.csv) | 后背/torso、射线覆盖与共同命中、质量、轮廓 |
| [逐人种子均值](results/subject_seed_mean.csv) | 100 条逐人—方法记录，种子不当作新人 |
| [配对描述审计](DESCRIPTIVE_PAIRED_AUDIT.json) | D 增益、轮廓代价、Txyz raw/applied/fallback |
| [旧新对账](OLD_NEW_PAIRED_AUDIT.json) | 180 条相同旧 torso 口径的三方法对账；不混用 P90/P95 |
| [缓存重算审计](results/CACHE_RECOMPUTE_AUDIT.json) | 300 条逐字段、逐点数组精确一致，未重新拟合 |
| [输出完整性](results/OUTPUT_COMPLETENESS_AUDIT.json) | 300 Mesh/300 叠图/300 残差图/60 页对照及 SHA256 |
| [执行前后完整性](results/INTEGRITY_full.json)、[重算后完整性](results/POST_AUDIT_INTEGRITY.json) | 冻结交付、checkpoint/MHR/anchors/SAM 源码及 Mesh 身份 |
| [运行资产](results/RUN_FREEZE.json)、[环境](results/ENVIRONMENT.json) | 实际文件 SHA256 与 CUDA/Python 环境 |
| [开发账本](results/EXECUTION_LEDGER_dev.json)、[正式账本](results/EXECUTION_LEDGER_full.json) | 每人执行条数及耗时 |
| [服务器位置](SERVER_PATHS.md)、[实际命令](COMMANDS.md) | 完整 Mesh、参数、渲染数组和原始数据位置 |

科学代码与全部输入配置保持准备提交 [`bfbdf095b89b0142b0e6fbe6fdf5ee3da842e76d`](https://github.com/32muyuxuanshou/massage-physiotherapy-robot/tree/bfbdf095b89b0142b0e6fbe6fdf5ee3da842e76d/docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2) 原字节。该准备目录的“尚未运行”是当时的历史状态；**正式完成状态以本目录为准**。本目录 `code/` 仅增加缓存重算、全量导出和描述图表工具，不改科学方法。

`results/inputs/Sxxx/split_0/1/2.npz` 保存实际训练/留出/评价索引；`results/evaluation/` 保存全部逐点残差及命中标记；`results/meshes/` 保存全部网格元数据与优化记录。完整顶点、面、MHR 参数、R/t/D 与优化索引数组留在服务器，逐条身份可核对。原始数据和授权权重不入 Git。

800 张运行展示图中，原 PNG 被导出为同分辨率 JPEG，原图仍在服务器。原图/展示图的路径、尺寸与 SHA256 对应在 [展示导出清单](VISUALIZATION_EXPORT_MANIFEST.json)。另有两张直接从冻结数值生成的汇总图，位于 [figures](figures)。本目录文件整体身份见 `FILES_MANIFEST.json`。
