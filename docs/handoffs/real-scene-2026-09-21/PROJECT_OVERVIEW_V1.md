# 理疗机器人真实场景 Mesh → 穴位项目总览 V1

## 1. 我们要解决什么问题

输入是真实场景中的 RGB 或 RGB-D 人体图像，人物可以处于站立、坐姿、躺姿、遮挡、截断和复杂姿态。系统需要：

1. 恢复可用的人体表面 Mesh；
2. 判断后背区域是否有足够几何证据；
3. 在 Mesh 表面得到可追溯的背部穴位三维位置；
4. 输出 face、barycentric、surface normal、坐标变换和质量状态，供机器人定位；
5. 最终用医生或独立真人标注验证医学准确性。

当前目标分两层：先完成可靠、可审计的工程系统，再用真实临床标注把它提升为可投稿的方法论文。没有医生标注的结果不能称为医学真值。

## 2. 现有数据和模型

### 数据

| 数据/资产 | 当前用途 | 状态 |
|---|---|---|
| **BEHAVE** 多视角真实 RGB-D | K0 RGB-D 作为输入；K1/K2/K3 传感器 Depth 作为 held-out 几何证据；有标定、mask 和 fitted reference | 当前主几何验证集；fitted mesh 只作辅助证据，不当绝对 GT |
| **BEHAVE V2.3** | 5 个 fresh subjects、45 帧、3 个 sequence、K0→K1/K2/K3 | 已完成 Cheap Txyz 泛化验证 |
| **PUBLIC_BACK_PILOT B1–B5** | 5 个已有真实背部场景的 MHR prediction，用于后背区域、拓扑传播和规则投影 sanity | 工程样本，不是医学标注集 |
| **DMD37 / DMD-BAK 相关资产** | Blender 点位、MHR bridge、工程候选标签和文献参考 | 未经医生核验，不能作为医学真值或正式监督标签 |
| **Synthetic DMD37** | 完美相机、可控姿态、可控噪声下的几何 QA | 只验证代码和坐标链，不能替代真人验证 |
| **医生标注的真实背部数据** | 最终穴位准确率、医生间一致性和临床可用性 | 尚未建立，属于后续阶段 |

### 模型与算法

- **SAM 3D Body + MHR LOD1**：当前人体 Mesh 主干；冻结资产为 18,439 vertices、36,874 faces，输出人体姿态、形状、相机和 Mesh。
- **Official SAM3D**：真实场景人体重建 baseline。
- **Cheap Txyz**：使用 K0 深度做全局平移校正的冻结测试时基线；只改 translation，不能解决局部姿态和形变。
- **T+Pose**：联合优化 translation、global rotation 和 body pose 的诊断基线；不是最终论文方法。
- **Topology transfer**：在同一 MHR 拓扑上把 canonical 点传播到预测 Mesh。
- **Rule engine**：根据参考水平、侧向 B-cun 和局部表面把规则目标投影到 Mesh；当前使用 proxy landmarks，只用于工程 sanity。
- **尚未实现的论文模型**：visibility-aware RGB-D adapter、cross-view evidence distillation 和结构约束的穴位下游模块。

## 3. 当前已经跑通的流程和结果

### Mesh 主流程

```text
BEHAVE K0 RGB-D + mask + calibration
→ SAM3D/MHR
→ Official Mesh
→ Cheap Txyz / T+Pose diagnostic correction
→ K1/K2/K3 held-out sensor-depth evaluation
→ camera → frame → sequence → subject aggregation
```

BEHAVE V2.3 的 45 帧正式验证已经完成：

| 指标 | Official SAM3D | + frozen Txyz |
|---|---:|---:|
| subject-equal median surface error | 31.17 mm | 17.80 mm |
| P90 | 76.73 mm | 54.90 mm |
| P95 | 94.58 mm | 71.26 mm |
| coverage ≤50 mm | 73.83% | 87.35% |

5 个 fresh subjects 全部改善，45 帧中 36 帧在三个 held-out camera 都改善；保留了 1 个三相机都退化的样本，没有筛掉。结论是：全局深度方向平移误差可以稳定改善，但这不等于局部姿态、形变或遮挡补全已经解决。

修正后的 FULL/UPPER/LOCAL_TORSO V3 结果为：

| 输入 | Official | Txyz | T+Pose |
|---|---:|---:|---:|
| FULL | 30.77 mm | 16.53 mm | 13.27 mm |
| UPPER | 35.21 mm | 16.52 mm | 13.93 mm |
| LOCAL_TORSO | 35.49 mm | 21.76 mm | 21.66 mm |

归因结果显示 FULL 主要由 translation 获益，LOCAL_TORSO 中 body pose 的作用更明显。这支持“局部可见条件下的结构化姿态/形变补全”作为下一步研究问题，而不是把论文写成更好的 T+Pose。

### Mesh → 穴位工程流程

```text
canonical MHR
→ POSTERIOR_TORSO_V1 candidate surface
→ topology seed / rule contract
→ proxy anatomical frame
→ B-cun rule computation
→ posterior surface projection
→ face + barycentric + normal + robot coordinate interface
```

当前已对 canonical MHR 和 B1–B5 共 6 个 Mesh 运行规则 sanity，每个样本输出 8 个工程点，共 48 个点；表面投影、重心坐标和输出字段 QA 通过。

这些点包括 `GV14`、`BL13`、`BL15`、`BL18` 和 `GV4` 的左右展开。当前参考水平和比例是几何 proxy，不是医生标志；所有输出都是 `medical_truth=false`。因此当前能证明的是规则链和表面接口可运行，不能证明穴位准确率。

一个需要单独修正的单位问题已经确认：raw MHR 坐标是厘米，现有部分 canonical 报告曾误标成毫米。该问题只影响 canonical 的单位换算和报告，不需要重跑 SAM3D/Mesh 推理；B1–B5 的 meter→millimetre 逻辑保持不变。

## 4. 最终准备采用的整体流程

```text
真实 RGB/RGB-D
→ 人体 mask / prompt
→ SAM3D/MHR 初始化
→ RGB-D visibility / depth adapter（论文方法）
→ full Mesh + per-region support map
→ posterior torso quality gate
→ C7、肩胛、骨盆等解剖参考标志
→ subject-specific B-cun coordinate
→ 规则计算穴位候选
→ Mesh surface projection
→ optional landmark / visibility / tangent-residual module
→ 3D acupoint + confidence + robot transform
→ safety check and execution
```

穴位阶段按复杂度逐级开放：

1. topology transfer 足够准，就直接使用；
2. 不足时使用 Mesh + 解剖标志 + B-cun 规则；
3. 规则仍不足时，只训练 landmark、visibility 和小范围 tangent residual，不直接训练黑盒穴位 XYZ。

医生验证放在工程流程稳定之后，用来替换 proxy landmarks、测量医生间一致性、建立真实表面误差和机器人定位误差。

## 5. 三个论文 Idea

### Idea 1：Observability-Gated RGB-D Mesh Completion

**张力**：局部 RGB-D 只观测到部分身体，普通 Mesh 模型却对全身使用同一种置信度；Txyz 只能整体平移，不能区分观测区域和补全区域。

**贡献**：在 SAM3D/MHR 初始化上加入 depth-conditioned visibility tokens、部位级 support map 和结构路由，让观测区域受真实深度约束，缺失区域由人体结构先验补全；一次前向输出 Mesh 和 support map。

**关键实验**：Official、Txyz/T+Pose、RGB-only adapter、RGB-D adapter、visibility ablation；BEHAVE 跨主体、跨 camera、FULL/UPPER/LOCAL_TORSO 和局部/补全区域分开评价。

**主要风险**：如果 held-out camera 没有改善，说明只是输入拟合；必须证明 visibility routing 本身解决了非平移误差。

### Idea 2：Cross-View Evidence Distillation

**张力**：训练时有多视角 RGB-D 和标定，部署时通常只有一个视角；fitted SMPL 不是绝对真值，完全不用多视角又浪费真实传感器证据。

**贡献**：训练阶段用多相机 sensor depth 形成 cross-view surface teacher，学生只输入 K0 RGB-D，蒸馏可见表面、部位关系和 support map，而不是复制 fitted mesh 顶点。

**关键实验**：fitted-only、K0-only、cross-view teacher、联合监督；训练使用不同 camera 数，测试始终只看 K0，并做独立相机留出。

**主要风险**：标定或同步错误会污染 teacher；必须证明测试阶段没有访问 held-out camera。

### Idea 3：Anatomy-Constrained Mesh-to-Acupoint Surface Coordinates

**张力**：Mesh 视觉合理不代表穴位位置正确；二维点不能直接给机器人三维目标，固定 canonical 点也不能代表个体解剖。

**贡献**：采用 landmark-first、formula-second、surface-third 的分层接口；用解剖标志和个体化 B-cun 计算规则点，再保存 face、barycentric、normal 和机器人坐标，而不是直接回归黑盒 XYZ。

**关键实验**：2D detector、atlas-only、rule-only、双路径和 residual；报告表面距离、跨姿态稳定性、双路径分歧、医生间一致性和机器人坐标误差。

**主要风险**：没有医生标注时不能声称医学准确率；DMD37 或 synthetic atlas 只能作为工程候选，不能替代真人验证。

## 6. 当前主线判断

建议论文采用：

```text
主方法：Idea 1
训练/监督策略：吸收 Idea 2
医学/机器人下游：Idea 3
```

这样主故事是：

> 局部可见 RGB-D 证据如何通过显式可观测性和结构补全恢复可靠人体 Mesh，并进一步支持可审计的三维穴位定位。

当前项目已经完成强工程 baseline 和穴位几何接口，但还没有完成新的 RGB-D 模型训练，也没有医生确认的医学穴位真值。MICCAI 需要后续补齐真实标注、患者/主体独立划分、跨场景泛化和临床相关终点；若方法在 held-out depth 与穴位表面误差上都稳定改善，再考虑 3DV/CVPR/ICCV 等更偏视觉方法的投稿。

## 7. 主要交付入口

- [BEHAVE V2.3 结果](../real-scene-2026-09-11/behave-cheap-txyz-generalization-v2/results-v2.3/RESULTS.md)
- [正式 FULL/UPPER/LOCAL_TORSO V3](../real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/FINAL_REPORT_V3.md)
- [Mesh 归因分析](../real-scene-2026-09-20/ATTRIBUTION_ANALYSIS_V1.md)
- [穴位规则执行报告](acupoint-rule-based-pipeline-v2/EXECUTION_REPORT_V1.md)
- [Mesh→穴位流程合同](rgbd-mhr-acupoint-pipeline-v1/PIPELINE_CONTRACT_V1.md)
- [三个论文 Idea 详细版](rgbd-mhr-acupoint-pipeline-v1/ORAL_IDEA_SET_V1.md)
- [文献和证据矩阵](acupoint-rule-based-pipeline-v2/EVIDENCE_MATRIX.md)
