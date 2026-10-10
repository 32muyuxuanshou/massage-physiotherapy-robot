# 论文证据：取什么、不照搬什么

只使用原论文、作者项目/源码和渲染器官方文档。阅读范围为架构、损失、相关实验及选定图；没有把下载或文本提取等同于逐页全文阅读。PDF 页码从 1 开始，版本与 SHA 见 PAPER_READ_RECEIPT.json。论文 PDF 和页图保存在本地 `output/r5_training_evidence_review_v1/` 及已有资料目录，不重复上传全文。

|工作|作者 / 年份 / 来源|本轮核对位置|对当前问题的作用|
|---|---|---|---|
|[SAM 3D Body](https://arxiv.org/abs/2602.15989)|Xitong Yang 等，2026，CVPR / 作者 arXiv|CVF p3–4、Fig.2；arXiv p5 §4|核对官方任务、MHR 与 Camera 关系、实际损失类别|
|[BLADE](https://arxiv.org/abs/2412.08640)|Shengze Wang 等，2025，CVPR|p4–6、Fig.4–5；supp p11–12|公制距离、透视和人体预测之间的关系|
|[MoGe-2](https://arxiv.org/abs/2507.02546)|Ruicheng Wang 等，2025，作者 arXiv|p4–5、8–9，Fig.2–3、Table4|全局公制量与相对几何分别监督的证据|
|[UniDepth](https://arxiv.org/abs/2403.18913)|Luigi Piccinelli 等，2024，CVPR|p3–5、Fig.2、§3.3–3.4|相机射线、梯度隔离与坐标表示的依据|
|[DoubleFusion](https://arxiv.org/abs/1804.06023)|Tao Yu 等，2018，CVPR|p3–5、Fig.2–3、§4 Eq.3–4|真实 Depth 的几何数据项，以及衣物外表面与身体的区别|
|[BEDLAM](https://arxiv.org/abs/2306.16940)|Michael J. Black 等，2023，CVPR|p3、6–7、18–19；supp Table7|合成标签、衣物和损失消融，而非越多损失越好|
|[DFormerv2](https://arxiv.org/abs/2504.04701)|Bo-Wen Yin 等，2025，CVPR|p3、Fig.3、§3.1|Depth 几何先验；其任务是语义分割|
|[nvdiffrast](https://nvlabs.github.io/nvdiffrast/)|NVIDIA，官方 API 与原理文档|Rasterization / Antialiasing / 多 GPU 章节|可见性梯度、透视渲染和实际实现边界|

## 1. SAM3D 的训练目标不等于我们的十项损失

CVF 主文 §4 把细节转到补充材料；本轮下载的作者 arXiv 版 p5 直接列出：2D/3D 关键点 L1、MHR 参数 L2、关节范围约束、手框 GIoU/L1，并描述关键点归一化和部分损失 warm-up。没有提供可逐项复现的全部数值权重。**我没有据此推定官方也用了我们当前的十项损失或权重。**[作者论文](https://arxiv.org/html/2602.15989v1#S4)

Fig.2 与 §3.2 的文字需要一起读：图上画了 MHR / Camera token，但正文把初始化编码为 MHR+Camera token。是否会回馈人体输出，必须看实际代码；不能由图中两个方框推断硬解耦。我们的 G1 有前置 Depth fusion 和中间 Camera hook，R4.2 已证明冻结官方权重仍可能改变人体输出。

论文里的不确定性设计是对作者方法的描述，本方案不因此新增不确定性头。

## 2. BLADE：定位不能与透视割裂，但不是现成的 RGB-D Camera-only 解法

BLADE 从 RGB 估计 pelvis Tz，以逆真实距离加权的 L1 监督；再用 Tz 条件化 Pose，并通过可微轮廓对齐解相机。其 Body 监督包括 Shape、旋转、关节和顶点。近距离透视改变人的外观，所以它并不主张 Body 永久完全独立于距离。[原论文](https://arxiv.org/abs/2412.08640)、[作者代码](https://github.com/NVlabs/blade)

因此我们采用其“显式检查公制位置、近远距离分别报告、同时看 2D 与 3D”的启发；不照搬它的 RGB 深度估计器、不重新估计已知 K，也不照搬近距优先的误差加权。我们的目标首先是绝对毫米定位，4 m 与 0.8 m 应分别报告。

冻结 Official Body 是当前受控实验：若极近距下 Body 本身明显错误，仅平移不能补救。这个限制应由数据结果决定，而非提前宣称被解决。

## 3. MoGe-2：最贴近“保留几何、另学公制量”的证据

MoGe-2 保留相对点图分支，另设全局尺度分支，以 stop-gradient 后的尺度目标监督；Fig.3 / Table4 对比耦合与不同解耦头。其有效设计使用全局 CLS 信息，并非仅添加一个小卷积输出头。它给出“分开优化物理量和相对几何”的经验依据。[原论文 §3.2 / §4.3](https://arxiv.org/html/2507.02546v1#S3.SS2)

但它预测的是单目场景点图及 scale，我们预测的是已知 K、已测 Depth 条件下的 MHR 平移；二者标签和参数不相同。不能把它的 scale loss、全套 alignment 或结果直接挪作我们的证据。

## 4. UniDepth：借相机射线和梯度隔离，不删掉我们要学习的绝对误差

Fig.2 展示相机与 Depth 表示分开处理、相机分支对编码特征的梯度隔离；一致性施加在相机条件化之后。其优化包含角度和 log-depth 的均值/方差项，仍保留绝对信息，并非简单“所有任务都减中位数”。[原论文 §3.1–3.4](https://arxiv.org/abs/2403.18913)

本项目已有准确 K，应保留 `XYZ=Z·K⁻¹[u,v,1]`。可同时使用中心化局部形状，但必须保留公制质心和原始 Z。纯尺度/平移不变损失不能作为绝对定位主损失；这条是针对我们任务的推导，不是说 UniDepth 不具备公制预测。

## 5. DoubleFusion：Depth 对表面有价值，外层衣物不等于内层人体

Fig.2 明确区分外部观测表面和内部参数身体；§4 的数据项使用鲁棒点到平面残差，并伴随绑定、正则和人体先验。该工作还依赖连续融合、初始化和优化。[原论文](https://arxiv.org/abs/1804.06023)

因此可以借鉴“可见观测与人体先验分开、几何残差采用鲁棒项”，但不能说单张扫描与 MHR 完全相同，也不能把其迭代系统当作我们的单前向网络。衣物和皮肤间的差别仍会给 Camera-only 表面监督带来偏差。

## 6. BEDLAM：数据标签正确，和损失数量同样重要

BEDLAM 保留参数身体标签，同时生成衣物、RGB、Depth 等可见外层信息。主文 §4.1 与补充 Table7 检验多种监督组合；额外 2D 顶点项并未一律改善，L1/MSE 在不同任务上也有取舍。[原论文](https://arxiv.org/abs/2306.16940)

本项目应该分别记录“参数身体标签”和“扫描可见表面标签”，做逐项消融。多渲染相机有用，但不能让 12 个身份变成上千个身份。BEDLAM 的 SMPL-X 标签也不是我们的 MHR GT。

## 7. DFormerv2 与渲染器：适用边界

DFormerv2 用 Depth 差异和空间位置形成 attention 几何先验。它证明这类几何关系可帮助 RGB-D 表征，但优化的是分割，不能替我们证明绝对平移准确或选出定位损失权重。[原论文](https://arxiv.org/abs/2504.04701)

nvdiffrast 的点采样覆盖本身没有连续的可见性梯度；轮廓边界梯度来自 antialias。深度损失在无面命中的像素处未必能把 Mesh 拉回。先验证粗定位、再验证细残差是实现要求，不能据“loss 非零”认定可训练。[官方说明](https://nvlabs.github.io/nvdiffrast/)

## 8. 本轮独立判断

文献支持：准确几何合同、按标签分配监督、公制量单独处理、保留原人体先验、逐项消融。文献**没有**替我们证明某组四项损失的固定权重、Camera-only 必胜、自动达到机器人接触精度、或论文足够强接受。

研究价值应由结果回答：在 Body 保持的条件下，位置恢复是否在距离/视角变化及独立传感器评价中比 Official＋Txyz 更稳定或更高效。损失列表本身不是贡献。
