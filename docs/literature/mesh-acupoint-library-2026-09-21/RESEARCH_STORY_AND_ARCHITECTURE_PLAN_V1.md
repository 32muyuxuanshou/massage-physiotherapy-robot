# 真实场景 Mesh → 穴位路线：论文故事与架构计划 V1

日期：2026-09-21  
状态：研究设计，不代表正式实验结论。

## 1. 研究问题

当前工程结果已经显示：完整输入时，SAM 3D Body 加 Txyz/T+Pose 可以达到较低的 held-out 表面误差；当输入裁成局部躯干时，Txyz 和 T+Pose 的提升变小，部分远端或不可见区域反而恶化。这说明问题不是“再调一个平移量”，而是：

> 在自然场景和局部可见条件下，怎样把可靠的 RGB-D 表面证据、身体部位关系和人体运动学先验组合起来，恢复完整且跨视角一致的 Mesh？

穴位问题放在第二个问题中：

> 在恢复的身体表面上，怎样把体表标志、骨度分寸规则和图像穴位证据转换为可审计的三维穴位位置？

这两个问题有因果关系，但不应在第一版训练中互相污染：Mesh 是主任务，穴位是几何下游验证和最终机器人接口。

## 2. 论文故事

### 2.1 现有方法的缺口

现有强 HMR 工作已经分别解决了姿态 token、遮挡表征、部分点云、RGB-D 融合和部件解码。但它们通常缺少以下组合：

- 度量深度与 RGB 的显式可见表面证据；
- 局部输入下的身体部位级可见性建模；
- 由可见部位向缺失部位传播的运动学/结构补全；
- 以 held-out 相机传感器点到预测 Mesh 的几何证据作为主评价；
- 面向机器人定位的 Mesh 到穴位的可复核坐标接口。

### 2.2 我们的中心假设

如果网络知道“哪里有可信的表面观测、哪里没有”，并且先形成部位级几何 token，再通过运动学关系恢复缺失部位，那么它应当比整图黑盒回归在局部输入、遮挡和跨视角评价上更稳定。

这个假设可以被直接证伪：如果 visibility/structure 分支没有带来一致的 held-out 改善，或者改善只出现在 K0 而不出现在 K1/K2/K3，就不能把方法写成成功。

## 3. 推荐架构

```text
RGB + metric Depth + mask + bbox/prompt
              │
       ┌──────┴──────┐
       │             │
   RGB encoder   Depth encoder
       │             │
       └── cross-modal visible-surface fusion ──┐
                                                │
       visibility map + body-part tokens        │
                                                ▼
                    kinematic / part graph transformer
                                                │
                     global MHR head + part residual heads
                                                │
                         MHR parameters → mesh
                                                │
             cross-view surface check / acupoint geometry interface
```

### 3.1 输入

- RGB 原图；
- K0 的度量 Depth 和有效深度 mask；
- dataset-mask-derived 人体 mask；
- 历史 bbox 或明确的分割 prompt；
- 可选稀疏解剖标志 prompt。

FULL、UPPER、LOCAL_TORSO 必须使用同一套 mask-derived prompt 合同。这样实验隔离的是视觉上下文减少，而不是 detector 成败。

### 3.2 结构模块

1. **双流编码器**：RGB 提取纹理和轮廓，Depth 提取表面几何。Depth 分支应保留有效深度标志，不能把无效深度当成零距离。
2. **可见表面 token**：从有效 K0 深度点/anchor 聚合局部表面证据，并记录其身体部位归属。
3. **部位可见性编码器**：至少包含躯干、双上肢、双下肢、头部、手足等部位级可见率。它是确定性的观测统计，不是额外的不确定性预测。
4. **运动学图 Transformer**：让可见部位向缺失部位传播结构信息，输出 joint/part tokens。
5. **MHR 解码器**：global rotation、translation、body pose 为主输出；shape/scale 先冻结，避免把局部证据不足转化为体型漂移。
6. **可选局部残差头**：只对高误差部位输出残差，必须通过 held-out 相机验证后才保留。

## 4. 训练目标

第一版可用以下可解释的组合：

```text
L = L_mhr
  + λsurf L_visible_surface
  + λsil L_mask
  + λmv L_cross_view
  + λkin L_kinematic
  + λpart L_part_completion
  + λrank L_depth_rank
```

- `L_mhr`：MHR 参数和可见/全身关键点监督；
- `L_visible_surface`：K0 可见深度点到预测 Mesh 的 point-to-surface 距离；
- `L_mask`：可见轮廓和投影 mask；
- `L_cross_view`：不同相机的预测 Mesh 在统一 world 坐标中的一致性；
- `L_kinematic`：骨长、关节拓扑和姿态合法性；
- `L_part_completion`：可见部位与缺失部位的部位级恢复损失；
- `L_depth_rank`：仅在绝对深度不完整时保留相对深度顺序约束。

这套损失不需要额外输出不确定性。可见性由 mask、Depth 有效性和部位覆盖率直接计算，便于审计。

## 5. 数据方案

### 阶段 A：大规模合成预训练

以有 MHR 真值的合成身体和自然场景合成数据为主，随机生成：

- 身体截断、物体遮挡、视角和姿态变化；
- Depth 空洞、噪声、错位和局部缺失；
- FULL/UPPER/LOCAL_TORSO 三种可见上下文；
- mask/bbox 的小幅扰动。

输出全身 MHR、可见表面、部位可见率和跨视角对应关系。

### 阶段 B：公开真实 RGB-D / 多视角适配

使用 subject-disjoint 划分，优先利用 RGB、Depth、mask 和多视角几何监督。BEHAVE 当前路线可作为真实多视角评测与适配来源，但不能把同一 subject 的多视角拆到 train/test 两边。

### 阶段 C：穴位小规模标注

穴位数据不要求一开始达到大规模。先做 5–8 个规则清楚、体表可见、能被医生复核的背部点，建立高质量验证集；等 Mesh 主干稳定后再扩展到 DMD37。

## 6. Stage C：解剖标志到穴位

### 6.1 图像是否可以直接用？

可以，但图像应作为“体表证据”和“标志检测”来源，不能单独承担三维穴位真值。最终点位应落在预测 Mesh 表面并保留映射关系。

### 6.2 双路径计算

**路径 A：骨度分寸法**

1. 在 Mesh/图像中定位脊柱、肩胛、肩峰、骶部等标准解剖标志；
2. 建立个体局部坐标系和局部寸比例；
3. 根据标准公式计算穴位的局部坐标；
4. 将该坐标投影到 Mesh 表面，保存三角面索引和重心坐标。

**路径 B：体表标志法**

1. 从 RGB 或人工 prompt 检测同一组体表标志；
2. 根据体表相对位置计算候选穴位；
3. 反投影/贴合到 Mesh 表面；
4. 保存图像证据、Mesh 面和重投影位置。

两条路径只在规则明确且标志可见时交叉核验。差异应作为审计量和人工复核依据，不能简单平均成所谓真值。

### 6.3 评价

- RGB 中的 2D 重投影误差；
- Mesh 表面上的 3D 点到点/点到曲面距离；
- 骨度法与体表法的差异；
- 医生重复标注和多医生一致性；
- 不同姿态、体型和局部遮挡下的稳定性。

没有医生标注时，只能报告几何一致性和工程可用性，不能声称临床准确。

### 6.4 DMD37 的分级

- **Level 1**：有明确标准公式和稳定体表标志，可双路径验证；
- **Level 2**：只有可靠体表标志，暂用单路径并标注限制；
- **Level 3**：依赖触诊或当前图像不可见，暂不自动放行。

Dazhui、Fengmen、Feishu、Xinshu、Geshu、Ganshu、Dachangshu、Shenshu 等点可以作为候选，但每个点的精确公式必须从正式标准和医生复核表中逐项确认，不能凭名称推导坐标。

## 7. 论文贡献应如何写

只有完成相应实验后，才可以声称以下贡献：

1. 一个面向自然场景局部可见条件的 RGB-D Mesh completion 架构；
2. 一个把可见表面证据、部位可见性和运动学补全联合起来的训练方案；
3. 一个以 held-out sensor depth 为主证据、跨视角和跨 subject 的评价协议；
4. 一个从 Mesh 到穴位的双路径、可复核几何接口和小规模高质量标注协议。

如果只完成 SAM3D 后处理、少量数据微调和穴位贴图，论文贡献应诚实地写成工程系统或应用研究，不能包装成新的 Mesh 架构。

## 8. 必须做的消融与停止条件

至少比较：

1. SAM3D baseline；
2. RGB-only；
3. RGB-D 无 visibility/graph；
4. 加 visibility tokens；
5. 加 kinematic graph；
6. 加 cross-view surface loss；
7. 完整模型。

在 FULL、UPPER、LOCAL_TORSO 和 held-out K1/K2/K3 上分别报告全身、躯干、远端部位和跨主体结果。若完整模型只改善 K0、不能改善 held-out sensor evidence，或只对单一 subject 有效，就停止扩展网络，回到数据和输入合同检查。

## 9. 论文定位建议

MICCAI 更看重临床/工程可行性、数据与标签质量、严谨的患者/主体划分和有意义的下游任务；CVPR/3DV 更看重方法创新和通用视觉证据。当前最稳妥的路线是先做一个方法论文主线，再把穴位作为可量化的机器人定位下游任务，而不是把医学叙事写在没有医生标签的结果之上。

MICCAI 2026 审稿要求可参考：[Reviewer Guidelines](https://conferences.miccai.org/2026/en/REVIEWER-GUIDELINES.html) 与 [Paper Submission Guidelines](https://conferences.miccai.org/2026/en/PAPER-SUBMISSION-GUIDELINES.html)。
