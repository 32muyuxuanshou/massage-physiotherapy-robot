# R3.1：文献如何改变这轮实现

本轮下载 9 篇原始论文，重点核对 DFormerv2、UniSH、MoGe/MoGe-2 的方法、公式和方法图，补读床上重建 DiSRT-In-Bed、单视角 RGB-D 人体重建 M³。逐篇版本、PDF SHA256、页数和阅读范围见 [LITERATURE_READ_SCOPE.json](LITERATURE_READ_SCOPE.json)。下载、读论文不等于复现作者模型。本轮实现是两个独立的 SAM3D/MHR 候选。

## 具体问题 → 技术启发 → 本轮实现

| 当前具体问题 | 原始论文与技术 | 对 SAM3D/MHR 的适用性 | 本轮落实与验证 |
|---|---|---|---|
| 普通 Cross-Attention 没有强制关注几何邻近关系 | [DFormerv2，CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Yin_DFormerv2_Geometry_Self-Attention_for_RGBD_Semantic_Segmentation_CVPR_2025_paper.html)：深度差与二维距离构成 attention 几何先验 | 已有配准 Z 和真实相机 rays，可以使用 XYZ，而不只把 Depth 当纹理编码 | A：3D 距离 + ray 距离的 attention bias、XYZ value embedding。删除 3D bias 时保留二维 ray bias，单独测试公制全局 context |
| 深度特征改变了 Mesh，却不能稳定约束人体在相机中的位置 | [UniSH，CVPR 2026 作者项目](https://murphylmf.github.io/UniSH/)：AlignNet 将 scene 几何与人体 token 对齐，分解全局尺度和人体平移 | 本项目有测量深度，可以跳过单目 scene 重建；保留 SAM3D 的人体先验，显式提供预测表面与观测表面的几何关系 | B：24 个原生人体 query，预测表面 anchor 对 Camera A XYZ 的软对应，输出原生 Camera/MHR 参数增量；对照取消局部对应及 translation-only |
| 全局位置与局部形状可能互相掩盖 | [MoGe，CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Wang_MoGe_Unlocking_Accurate_Monocular_Geometry_Estimation_for_Open-Domain_Images_with_CVPR_2025_paper.html)：affine-invariant pointmap 与全局/局部几何监督；[MoGe-2，NeurIPS 2025](https://openreview.net/pdf?id=16mDq7m2OK)：相对几何与公制尺度分开处理 | 需要分开检查 Camera、去平移 Mesh 和局部 Depth，而不是只看一个总误差。本项目的真实 Depth 已有米制尺度，不应被单目伪深度替代 | 固定 Mask/rays 的绝对 Z、相对 Z、平坦/平滑局部形状、数值偏移干预；A 显式全局 XYZ context。保留各指标，不把 MoGe 分数移植为本项目精度 |
| 观测点与人体部位的对应不可靠 | [M³，2025 arXiv](https://arxiv.org/abs/2508.08178)：RGB DensePose UV + 测量 Depth 形成部分 SMPL 顶点，再 masked completion | “先建立语义对应，再补全”贴近当前任务；直接使用作者自由顶点输出会违反原生 MHR 限制，SMPL UV 也不能直接套到 MHR | B 暂用原生 mhr70 query + 射线附近预测表面，不宣称已得到 DensePose 级对应。它是候选的主要风险；后续若升级需独立验证 MHR 语义对应 |
| 合成训练转移到真实床上人体不稳定 | [DiSRT-In-Bed，CVPR 2025](https://arxiv.org/abs/2504.03006)：俯视 Depth 条件 SMPL 参数 diffusion，合成预训练与有限真实微调分阶段 | 与最终床上任务比通用 scene segmentation 更接近；可借鉴床/姿态/遮盖分布及分阶段训练。但本轮 HuMMan 不是床上临床证据 | 本轮不新增 diffusion、不训练真实数据；报告合成姿态只有 2 种的局限，先用固定小规模对照判断几何结构是否有价值 |

## 看完方法图后，明确没有照搬的部分

**DFormerv2：**作者采用几何先验对 self-attention 权重加权，并有轴分解。本轮 A 是 RGB query 对 Depth key/value 的 cross-attention，在 softmax 前加入高斯距离 bias，继续保留已有 Depth CNN。因此这是受启发的改造，不能叫 DFormerv2 复现，也不能把作者的分割收益当人体重建收益。

**UniSH：**scene/human 两路、AlignNet 与专家局部几何蒸馏的职责不同；局部 scene pointmap 更精细不等于人体参数 mesh 已有同样细节。本轮 B 不重建场景、不新增专家模型，而以测量点几何更新原生 MHR。此举保持拓扑，便于后续工程点传播，是否准确仍须独立相机评价。

**MoGe 系列：**单目相对几何、公制尺度推断与实测 RGB-D 是不同信息来源。论文提供分离全局/局部问题的思路，不能成为丢弃实测 Depth 或自动换相机内参的理由。

**M³：**完整方法是 DensePose → UV 与 Depth 联合提升 → 部分 mesh → transformer completion。RGB 在对应建立阶段有明确职责。它的顶点 PVE 与本项目 Camera B 点到三角面距离不同，禁止数值横比。当前仅核实 arXiv 版本，不给它未经核查的顶会标签。

**DiSRT-In-Bed：**输出 SMPL 参数，在参数空间 denoise；不是将 noisy depth 直接生成一份高精度皮肤扫描。RGB 是该工作展示参考，主输入是 overhead Depth。床上任务适配需要真实床上评价，不能用 HuMMan 结果替代。

## 补充论文的边界

- [Human3R，ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/467c017e2639255e9c5d91a2e582f95a-Abstract-Conference.html)：冻结 CUT3R 场景先验，加入人体 prompt/readout；说明有价值的几何表征不必靠全面解冻才能读出。本轮不引入视频记忆或替换 SAM3D。
- [CameraHMR，3DV 2025](https://camerahmr.is.tue.mpg.de/)：透视、bbox、内参 token 与相机监督。HuMMan 有公开 K/R/T，本轮不训练 FoV 估计器，也不用人体拟合倒调标定。
- [LiDAR-HMR，IEEE TMM 2025](https://arxiv.org/abs/2311.11971)：点云人体结构、局部 mesh 特征和后续参数化。可借鉴人体 query 的组织，但 LiDAR 稀疏扫描及自由 mesh 阶段不等于 RGB-D MHR。本轮不复制其完整网络。

## 研究判断

将现成 attention 加一个距离项，或加一个小 refinement head，本身还不足以构成强论文贡献。更值得验证的问题是：**部分可见的公制表面观测，能否在保持人体参数结构和拓扑的前提下，改善未用于输入或拟合的表面，而不破坏姿态？**

这轮用 Cheap Txyz、独立 Camera B、输出参数响应和机制消融判断候选是否值得继续。结果不支持时保留负结果，不靠解冻、更大训练或新模块掩盖问题。最终俯卧后背、工程点对应与真实机器人定位仍是后续验证范围。
