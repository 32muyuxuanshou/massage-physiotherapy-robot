# 俯卧背部 Mesh 与体表对应：论文学习记录

2026-10-04。目标仍是 **RGB-D 相机观察床上俯卧者，得到可靠后背表面，再定位工程点/穴位，最终服务按摩机器人**。本轮检索、下载并阅读方法、数据、实验及实际图页；没有启动新训练。

## 本轮得到的判断

**SAM3D 可以保留为全身先验；后背贴合与体表对应需要分别解决、共同验证。** 目前的证据支持研究这个问题，但还没有证明我们提出了新方法。

- VoteHMR 已有局部深度点云、关节投票、遮挡补全与结构回归；此前“可见性＋结构补全”idea 的通用架构重叠明显。
- 3D-CODED 的 Fig.8 直接展示了点云重建合理、模板 Mesh 却严重畸变的情况。Point2SSM 也分别评价表面采样与对应统计；贴面距离不能替代点位身份评价。
- BodyMap 和 DenseMatcher 已有图像语义与体表对应学习。仅添加 RGB/Depth 分支、Transformer 或 Mesh 特征采样，不能单独构成我们的贡献。
- 目前准备的小 U-Net 是学习作者画的背部线的工程对照。它尚未训练，也不能把这条线自动升级为椎体编号或穴位真值。

以上是本轮阅读后的分析，依据与限制见[逐篇笔记](PAPER_NOTES.md)和[路线修订](RESEARCH_DIRECTION_UPDATE.md)。

## 读了哪些，建议你先读哪些

优先级按当前工程问题排序，不是按会议名气排序。页码均为本地 PDF 页码；未声明通读所有参考文献及附录。

| 顺序 | 论文 / 发表 | 学习用途 | 已核对的关键内容 |
|---|---|---|---|
| 1 | [3D-CODED，ECCV 2018](https://openaccess.thecvf.com/content_ECCV_2018/papers/Thibault_Groueix_Shape_correspondences_from_ECCV_2018_paper.pdf) | 理解贴合与对应为何会分离 | pp.5–6、13–14；Fig.8、Table3 |
| 2 | [Point2SSM，ICLR 2024](https://arxiv.org/abs/2305.14486) | 从真实 XYZ 学稳定表面对应 | pp.4–6、8–9；Fig.2、4–6 |
| 3 | [BodyMap，CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/papers/Ianina_BodyMap_Learning_Full-Body_Dense_Correspondence_Map_CVPR_2022_paper.pdf) | 图像 → canonical 体表身份 | pp.3–5、7；Fig.2–3、Table6 |
| 4 | [DenseMatcher，ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/7ba6b5b03ae07151a9a353b51f943290-Paper-Conference.pdf) | 冻结图像骨干、学习三维对应、转移机器人目标 | pp.5–9、21–22；Fig.6–7、Tables1/3；补充 partial matching |
| 5 | [DiSRT-In-Bed，CVPR 2025](https://arxiv.org/abs/2504.03006) | 床上深度模型与真实数据适配 | pp.3–7；Fig.2–4、Tables1/2 |
| 6 | [VoteHMR，ACM MM 2021](https://arxiv.org/abs/2110.08729) | 单帧局部点云的人体先验 | pp.3–7；Fig.2、4–8、Tables1–3 |
| 7 | [BodyMAP，CVPR 2024](https://arxiv.org/abs/2404.03183) | Mesh 顶点采样图像特征、床上多模态对照 | pp.3–8；Fig.3–4、Table1 |
| 8 | [Markerless spinal assessment，IJIDeM 2026](https://link.springer.com/article/10.1007/s12008-026-02603-8) | 从真实背部微几何找参考候选及验证边界 | pp.4–8、10–12；Fig.3、Table1 |

另外审计两篇：**Bodies at Rest / CVPR 2020** 的真实20人数据与评价口径（pp.3、6–7，Fig.7）；**JOTR / ICCV 2023** 的真实输入模态（pp.3–4，Fig.2）。重新核对了用户已有 **SAM 3D Body / CVPR 2026** 的架构、标注与 fitting（pp.3–5，Fig.2、Table1）。共涉及 **11 篇不同论文**。

**BodyMap（2022，RGB 体表对应）与 BodyMAP（2024，床上深度/压力）不是同一篇。JOTR 的 3D 特征由 RGB 推断，不是深度相机测量。**

## 资料库与阅读范围

本地目录：`E:/项目-按摩理疗机器人/downloads/literature-learning-20261004/`。

- 新下载10篇不同论文的全文 PDF；DenseMatcher 另保存会议正式版，合计11个新 PDF 文件。SAM3D 使用用户已有文件。
- [PAPERS.json](PAPERS.json)记录原文来源、实际 PDF 路径、SHA256、页数、阅读页码、检查过的图页，以及官方代码入口的核查程度。
- 提取文本、35张渲染页保存在上述本地目录；其中**24张图页实际打开检查**。渲染完成不等于已经阅读。
- Point2SSM 的 OpenReview 正式 PDF 请求返回403，本轮阅读 arXiv v2；其 ICLR2024 Spotlight 信息由作者的 arXiv 记录确认。DenseMatcher 方法以下载成功的 ICLR2025 正式版为准。
- SAM3D的公开PDF请求也返回403，本轮复读的是已存在的用户本地文件；目录中明确记录两者，未把网页请求成功当作阅读证据。
- 本轮不是系统综述，也没有复现这些论文的模型。论文、代码链接存在，不等于权重/数据已可运行。

Git 交付只包含自己的笔记、出处和目录生成脚本；原文 PDF 与原论文截图留在本地资料库。

## 下一步如何用这些学习

先把既有“几何曲线”和准备好的“曲线学习”作为小基线，回答真实 XYZ 在缺失/噪声下能否稳定提供参考。接着用共同表面、共同输入比较固定拓扑、几何配准与学习对应，独立报告点位变化，避免同时更改表面和对应而无法归因。

最终模型候选是 **SAM3D 全身先验＋后背 RGB-D 几何特征＋canonical 表面对应**。这只是设计方向；Point2SSM、BodyMap、DenseMatcher 已覆盖许多组件，具体新机制及真实解剖验证仍需证明。不要现在把当前曲线结果、受控 ENG 真值或衣物表面距离写成穴位精度。
