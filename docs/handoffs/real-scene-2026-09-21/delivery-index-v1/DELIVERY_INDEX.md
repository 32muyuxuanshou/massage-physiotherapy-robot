# 真实场景 Mesh 路线总交付索引

日期：2026-09-21  
交付范围：BEHAVE V3、归因分析、36 张 Mesh 叠图、逐帧/空间/部位误差审计、文献资料库、论文方案与遗漏可视化。

## 先读这四份

1. [误差审计总说明](../../real-scene-2026-09-20/error-audit-v1/README.md)
2. [空间残差审计](../../real-scene-2026-09-20/error-audit-v1/SPATIAL_RESIDUAL_AUDIT.md)
3. [部位—可见性审计](../../real-scene-2026-09-20/error-audit-v1/BODY_PART_VISIBILITY_AUDIT.md)
4. [V3 完整报告](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/FINAL_REPORT_V3.md)

## 一、这次交付实际证明了什么

### 1. SAM3D/Txyz/T+Pose 的工程结果

正式 V3 使用 3 个 subject、9 个 sequence、18 个 timestamp、FULL/UPPER/LOCAL_TORSO 三种输入，K0 只用于输入和优化，K1/K2/K3 只用于 held-out 评价。

修正后的正式聚合结果如下，单位 mm：

| 输入 | Official | Txyz | T+Pose |
|---|---:|---:|---:|
| FULL | 30.77 | 16.53 | 13.72 |
| UPPER | 35.21 | 16.52 | 14.06 |
| LOCAL_TORSO | 35.49 | 21.76 | 21.66 |

Txyz 54/54 条件没有 fallback。这个结果支持：

- 全局平移修正是目前最稳定的工程增益；
- T+Pose 在 FULL/UPPER 有一定增益；
- LOCAL_TORSO 下 T+Pose 没有稳定超过 Txyz，存在局部输入过拟合迹象。

它不证明 Mesh 已经达到医学穴位精度，也不证明所有远端身体区域都正确。

### 2. 归因分析的正确解释

原始 [ATTRIBUTION_ANALYSIS_V1.md](../../real-scene-2026-09-20/ATTRIBUTION_ANALYSIS_V1.md) 保留作为历史记录，但不能继续作为最终数字依据。后续审计发现旧聚合跳过了 sequence 层，已恢复为：

```text
K1/K2/K3 → frame → sequence → subject → overall
```

当前应引用 [ATTRIBUTION_AGGREGATED.json](../../real-scene-2026-09-20/error-audit-v1/ATTRIBUTION_AGGREGATED.json) 和 [误差审计 README](../../real-scene-2026-09-20/error-audit-v1/README.md)。

正确归因重算为：

| 输入 | Official | Txyz | T only | T+global rot | T+body pose | T+Pose |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 30.77 | 16.53 | 14.84 | 14.34 | 13.54 | 13.27 |
| UPPER | 35.21 | 16.52 | 17.06 | 16.36 | 14.57 | 14.07 |
| LOCAL_TORSO | 35.49 | 21.76 | 22.71 | 23.42 | 21.58 | 21.66 |

这说明当前研究重点应是 visibility-conditioned body-pose completion，而不是继续把论文写成“更强的 T+Pose”。

### 3. 空间残差和部位证据

严格三角面距离的空间审计位于 [SPATIAL_RESIDUAL_AUDIT.md](../../real-scene-2026-09-20/error-audit-v1/SPATIAL_RESIDUAL_AUDIT.md)，完整数据位于 [SPATIAL_RESIDUAL_AUDIT.json](../../real-scene-2026-09-20/error-audit-v1/SPATIAL_RESIDUAL_AUDIT.json)。

主要 ROI 中位数如下：

| 输入 | ROI | Official | Txyz | T+Pose |
|---|---|---:|---:|---:|
| FULL | ROI | 34.12 | 14.82 | 13.90 |
| UPPER | ROI | 25.11 | 15.15 | 13.36 |
| LOCAL_TORSO | ROI | 31.34 | 21.73 | 15.74 |

部位可见性关联显示 LOCAL_TORSO 中：

- torso ROI fraction 约 66.6%；
- arms 约 56.0%；
- legs 约 57.9%；
- head 约 8.3%；
- hands/feet 约 35.6%。

LOCAL_TORSO 的 hands/feet 和 head 误差最高，支持“局部输入后远端部位补全更难”的工程假设。但部位标签来自拓扑绑定的工程部位图，不能当成医生解剖标注。

### 4. 视觉证据的边界

已有正式 V3 36 张四机位/三输入 PNG，另外本次补入 6 张按 subject 汇总图和 2 张最小闭环 montage。叠图只能显示投影形状，不能替代 sensor-depth 指标，也不能从颜色面积推断 IoU 或穴位误差。

## 二、历史 V3 的完整文件

- [修正版最终报告](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/FINAL_REPORT_V3.md)
- [完整聚合结果](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/FORMAL_RESULTS_V3_COMPLETE.json)
- [三层聚合结果](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/aggregated_v3_complete/)
- [完整 raw 输出和 Mesh 参数](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/formal_eval_v3_complete/)
- [执行记录](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/EXECUTION_RECORD.json)
- [V3 执行审计](../../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/EXECUTION_AUDIT.md)

## 三、归因、可视化和逐帧审计

- [归因历史说明](../../real-scene-2026-09-20/ATTRIBUTION_ANALYSIS_V1.md)（历史表，数字以修正版为准）
- [归因完整 JSON](../../real-scene-2026-09-20/error-audit-v1/ATTRIBUTION_AGGREGATED.json)
- [归因原始结果](../../real-scene-2026-09-20/attribution_v1/)
- [36 张正式 V3 叠图](../../real-scene-2026-09-20/visual_v3/)
- [可视化脚本](../../real-scene-2026-09-20/code/make_visual_v3.py)
- [逐帧索引](../../real-scene-2026-09-20/error-audit-v1/FRAME_INDEX.md)
- [逐帧误差 JSON](../../real-scene-2026-09-20/error-audit-v1/ERROR_AUDIT.json)
- [视觉复核说明](../../real-scene-2026-09-20/error-audit-v1/VISUAL_REVIEW.md)
- [空间残差 JSON](../../real-scene-2026-09-20/error-audit-v1/SPATIAL_RESIDUAL_AUDIT.json)
- [部位—可见性 JSON](../../real-scene-2026-09-20/error-audit-v1/BODY_PART_VISIBILITY_AUDIT.json)
- [误差审计源文件哈希](../../real-scene-2026-09-20/error-audit-v1/SOURCE_SHA256.json)

### 本次补入的遗漏可视化

- [Sub03 四机位汇总](visualizations/Sub03_FULL_K0K1K2K3.jpg)
- [Sub03 K1 三条件汇总](visualizations/Sub03_K1_conditions.jpg)
- [Sub04 四机位汇总](visualizations/Sub04_FULL_K0K1K2K3.jpg)
- [Sub04 K1 三条件汇总](visualizations/Sub04_K1_conditions.jpg)
- [Sub05 四机位汇总](visualizations/Sub05_FULL_K0K1K2K3.jpg)
- [Sub05 K1 三条件汇总](visualizations/Sub05_K1_conditions.jpg)
- [最小闭环推理 montage](visualizations/inference_montage.png)
- [最小闭环独立考试 montage](visualizations/evaluation_montage.png)

## 四、研究方向和文献资料库

- [MICCAI/3DV 研究方向](../../real-scene-2026-09-20/RESEARCH_DIRECTION_MICCai_V1.md)
- [强接收证据门](../../real-scene-2026-09-20/VENUE_ACCEPTANCE_GATES_V1.md)
- [文献矩阵](../../../literature/mesh-acupoint-library-2026-09-21/LITERATURE_MATRIX.md)
- [研究故事与架构计划](../../../literature/mesh-acupoint-library-2026-09-21/RESEARCH_STORY_AND_ARCHITECTURE_PLAN_V1.md)
- [资料库索引](../../../literature/mesh-acupoint-library-2026-09-21/INDEX.json)
- [RGB-D Mesh→穴位流程合同](../rgbd-mhr-acupoint-pipeline-v1/PIPELINE_CONTRACT_V1.md)
- [三个 Oral 论文 Idea](../rgbd-mhr-acupoint-pipeline-v1/ORAL_IDEA_SET_V1.md)

## 五、最小闭环历史交付

- [BEHAVE 最小闭环报告](../../real-scene-2026-09-11/behave-minimal-rgbd-mesh-closed-loop-v1/README.md)
- [服务器视觉文件清单](../../real-scene-2026-09-11/behave-minimal-rgbd-mesh-closed-loop-v1/review/)

该数据受 BEHAVE 非商业科研许可限制；公开展示图像必须模糊人脸，原始数据和完整服务器数组不进入 Git。许可条款见 [BEHAVE 官方许可](https://virtualhumans.mpi-inf.mpg.de/behave/license.html)。

## 六、当前状态

| 事实面 | 状态 | 说明 |
|---|---|---|
| V3 工程实验 | verified-current | 3 subjects、18 frames、54 条条件，已完成纠正聚合 |
| 归因/空间/部位审计 | verified-current | 只读已有结果，没有改算法和样本 |
| 36 张正式叠图 | verified-current | 来自 formal V3 |
| 6 张 subject 汇总图 | changed-and-verified | 本次从现有输出补入交付目录 |
| 2 张最小闭环 montage | changed-and-verified | 本次从历史 review 输出补入交付目录 |
| 新 Mesh 网络训练 | pending | 只有研究设计，尚未执行 |
| 医学穴位真值 | pending | 目前没有医生确认的 DMD37 真值 |
| 本机工作区 | pending | 保留用户未提交的汇报稿、downloads 和 mesh_error_review 残留，未擅自删除 |

## 七、对应 Git 提交

- `75e8c06`：逐帧误差审计
- `8a4bfbe`：空间残差初版
- `20de7a1`：正式三角面距离
- `14f00e0`：工程部位误差归因
- `b908628`：部位与可见性关联
- `2b8544d`：文献资料库
- `475cbf3`：RGB-D Mesh→穴位流程合同
- `4d8bd70`：三个 Oral 论文 Idea
- 本次索引提交：见 GitHub 页面顶部最新 commit
