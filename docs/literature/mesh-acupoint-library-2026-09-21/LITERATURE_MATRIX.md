# Mesh 与穴位路线文献矩阵

日期：2026-09-21  
用途：为真实场景 RGB-D 人体 Mesh 重建、局部可见条件下的鲁棒性设计，以及后续穴位定位建立可审计资料库。

## 1. 结论先行

目前的 SAM 3D Body + Txyz/T+Pose 结果适合作为强基线和失败分析工具，不足以单独构成强方法论文。它能证明三个工程事实：

1. 全身图像上的 Mesh 可以达到可用精度；
2. 仅做全局平移修正能明显降低一部分深度误差；
3. 进入局部躯干输入后，优化容易把可见区域拟合好而牺牲不可见或远端部位。

真正值得做的研究问题，是把“哪些身体证据可见、哪些证据缺失、哪些结构约束可以补全”显式放进 RGB-D Mesh 网络，而不是继续堆后处理参数。

## 2. 模型架构的可迁移经验

| 文献 | 它解决的核心问题 | 值得吸收的组件 | 不直接照搬的部分 | 对本项目的启示 |
|---|---|---|---|---|
| [PostoMETRO](https://arxiv.org/abs/2403.12473) | 2D 姿态受遮挡时，直接回归 Mesh 不稳定 | 把姿态压缩为可组合的 pose tokens；用 joint/vertex tokens 解码 | 不复制它的 VQ-VAE 和不必要的不确定性输出 | 采用“可见证据 tokens + 身体部位 tokens”，让缺失区域通过结构解码补全 |
| [JOTR](https://arxiv.org/abs/2307.16377) | 遮挡下 2D/3D 表征容易混淆 | 2D 与 3D 表征融合；关节级语义对比约束；coarse-to-fine | 不把通用 contrastive loss 当成创新本身 | 对相同身体部位的 RGB、Depth、Mesh 特征做结构对齐，并区分可见/不可见部位 |
| [VoteHMR](https://arxiv.org/abs/2110.08729) | 只有部分点云时恢复完整人体 | 从可见点产生 joint-level votes，再沿运动学树补全；可见/全局双分支 | 不把点云 voting 原样搬到 RGB-D | K0 深度点和 mask 不应只作为优化输入，而应生成可审计的局部几何证据 |
| [Towards Robust RGB-D HMR](https://arxiv.org/abs/1911.07383) | RGB、RGB-D 数据的监督不统一 | 动态 RGB/RGB-D 融合；深度相对排序；由关键点生成 SMPL 约束 | 旧式双 ResNet 与对抗训练不适合当前工程主线 | 用深度排序和可见表面损失利用没有完整 Mesh 标注的数据 |
| [OSX / UBody](https://arxiv.org/abs/2303.16160) | 全身、手、脸的部件差异很大 | 全局身体编码器 + 局部部件解码器；部件感知注意力；真实生活数据 | 不复制“整套 whole-body”范围，先聚焦背部/躯干 | 采用全局姿态与局部躯干解码的分层结构，保留工程可控性 |
| [EgoHMR](https://openaccess.thecvf.com/content/ICCV2023/html/Luo_EgoHMR_Probabilistic_Human_Mesh_Recovery_in_3D_Scenes_from_Egocentric_Views_ICCV_2023_paper.html) | 大量身体不可见时需要合理补全 | 可见性驱动的图结构传播 | 第一版不引入扩散或概率生成，避免把不确定性变成无证据的卖点 | 可见性图和运动学图可以先做确定性版本，后续再考虑多假设输出 |
| [Deformable Mesh Transformer](https://openaccess.thecvf.com/content/CVPR2023/html/Wang_Deformable_Mesh_Transformer_for_3D_Human_Mesh_Recovery_CVPR_2023_paper.html) | 固定注意力难以处理姿态变化 | 以关节/网格位置引导的可变形采样 | 不直接复制其 attention 结构 | 让深度可见点引导局部采样，减少背景和遮挡干扰 |

### 吸收后的共同模式

这些工作虽然形式不同，但共同指向四件事：

1. **不是把整张图平均编码**，而是引入关节、部位或顶点级 token；
2. **不是假设人体全可见**，而是把可见性或可用证据显式建模；
3. **不是只回归最终顶点**，而是利用姿态、深度、运动学和表面几何的中间监督；
4. **不是只在单一图像指标上报告结果**，而是要做遮挡、局部输入、跨视角和部位级评价。

## 3. 穴位定位的已核实方法论

### 3.1 可靠的三条证据

- [CT 三维穴位定位研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC3929431/) 用骨骼与皮肤 CT 重建三维虚拟人体，并结合解剖标志、骨度分寸和手指同身寸，为大量穴位建立可计算的三维定位规则。这是“影像 → 骨/体表标志 → 公式 → 三维表面”的直接方法论先例。
- [Fengshi 标准化研究](https://pubmed.ncbi.nlm.nih.gov/29797916/) 比较了骨度比例法与体表标志法，说明两种方法可能产生系统差异，不能假设其中一方天然是真值。
- [Structure-guided back acupoint localization](https://pmc.ncbi.nlm.nih.gov/articles/PMC12417426/) 把解剖标志、个体化像素/寸比例和结构约束损失放进深度模型，和本项目的“先定位结构，再计算穴位”路线高度相近。

另一个基础依据是穴位定位的准确度并非只由网络误差决定。[相关系统综述](https://opus.lib.uts.edu.au/bitstream/20.500.118832/134832/1/Accuracy_and_Precision_in_Acupuncture_Point_Location_A_Critical_Systematic_Review.pdf) 讨论了体表标志、骨度分寸和手指同身寸三类方法的变异。因此，穴位模块必须报告方法间差异和医生复核一致性。

### 3.2 关于“2018 八髎穴论文”的证据边界

目前检索到的线索支持“八髎穴可能有类似影像/骨度/公式的研究”，但还没有核对到足以直接写入论文参考文献的题名、作者、期刊和 DOI。它在核实前只能作为待查线索，不能在论文中写成已确认依据。当前可以安全引用上面的 CT 三维研究、Fengshi 研究和结构引导背部穴位研究。

## 4. 不采用的方向

1. 第一版不把不确定性估计写成主贡献。没有可靠标注和校准实验时，它只会增加叙事风险。
2. 第一版不把扩散模型作为必须组件。它适合多假设不可见身体补全，但工程链更长、评价更难，不能解决当前最直接的“局部输入为何退化”。
3. 不把 DMD37 现有标注直接当成医学真值。它可以作为工程点候选集，仍需要标准、几何规则和医生复核三者的证据链。

## 5. 文献学习后的方法选择

建议的主方法是：

> **Visibility- and Structure-Guided RGB-D Human Mesh Completion**：使用 RGB、度量 Depth、人体 mask 和输入提示，提取可见表面证据；再由身体部位 token 和运动学图补全不可见区域，输出 MHR 参数和 Mesh，并通过跨视角表面一致性约束保持几何稳定。

穴位定位作为下游 Stage C：在 Mesh 和图像上分别计算位置，双方法交叉核验，不把它和第一版 Mesh 主干强耦合。
