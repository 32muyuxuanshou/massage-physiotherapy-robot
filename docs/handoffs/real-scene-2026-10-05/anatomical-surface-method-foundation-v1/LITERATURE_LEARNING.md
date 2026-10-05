# 直接相关论文：读图、读代码后的取舍

| 工作 | 已实际检查 | 可借鉴 | 不能据此声称 |
|---|---|---|---|
| [From Surface to Viscera](https://proceedings.mlr.press/v315/atici26a.html)，MIDL2026 | 16页PDF、双编码器图、作者Point Transformer源码，commit `1eae62535f6ff7101449117a450b0b1a96d4a529` | 观测点无序，器官模板有序；身体编码融合到模板解码，skip只来自模板 | “体表＋人体先验→解剖”是我们的首次提出；MRI模拟表面成绩等于真实俯卧精度 |
| [Surface-Conditioned Implicit Reconstruction](https://papers.miccai.org/miccai-2026-sat/Off_Grid_029.html)，MICCAI2026 **Off-Grid workshop** | 12页PDF、Point Transformer→调制SIREN图、encoder/decoder源，commit `4063b8cff75ef5e7b52c9cd14ef1bde537c91c8f` | 任意空间查询、整体身体条件、近结构/背景查询采样；数千份MRI训练 | 是MICCAI主会论文；10个真实depth展示具有独立内部解剖真值；双头隐式场本身新颖 |
| [Point Transformer](https://openaccess.thecvf.com/content/ICCV2021/html/Zhao_Point_Transformer_ICCV_2021_paper.html)，ICCV2021 | 10页PDF、局部位置注意力/层级采样图 | 相对位置同时进入注意力权重和值；局部查询适合稀疏不规则点 | 我们原创了此注意力结构 |
| [Multi-Modal Data Correspondence for the 4D Analysis of the Spine](https://pmc.ncbi.nlm.nih.gov/articles/PMC10376049/)，2023 | 作者全文XML、数据/方法/限制 | 同步内部/外部来源；皮肤face+bary与骨骼关节模型结合；分开评价外部贴合与内部位置 | 表面markers贴合就证明骨骼正确；8个AIS儿童、2个侧弯动作验证代表成年俯卧 |
| [SurgPointTransformer](https://arxiv.org/abs/2410.01443) | 作者摘要/任务定义，尚未完成全文读图 | 已有RGB-D稀疏表面→椎骨补全技术路线，应进一步读源码与限制 | 暴露椎骨的离体手术表面等于完整皮肤背部；摘要指标能与我们直接比较 |

前三篇PDF均已本地下载，并查看方法图；不是只看摘要。作者源码仅用于阅读，未安装其自定义CUDA扩展，没有声称复现他们的NAKO结果。

From Surface to Viscera正文写的总例数与列出的4780训练＋1454测试存在不一致；本项目引用明确列出的划分，不据其总数替代数据核验。NAKO MRI因隐私未取得，不能承诺下载该源。

2023多模态论文先用患者X-ray/皮肤创建数值模型，再用外部markers驱动姿态；弯曲验证仍约厘米位置误差。这进一步说明：既要看到外表面，也要有独立解剖证据。它与“完全无影像、只靠未知皮肤自动定位”不是同一任务。

### 对当前设计的约束

已有工作覆盖了全局条件、模板解码、隐式解剖、位置注意力、稀疏marker驱动人体模型。我们不能把这些模块堆叠当作创新。要证明的增量应落在**俯卧/局部观测下，参考约束的个体解剖坐标是否可靠，并且改善最终表面目标**。大规模CT是必要基础，真实俯卧的独立终点仍需补齐。

后续主线应优先完成这个证据链，不继续在51例CT玩具任务上调head，不把新网络随机初始化到80步的loss下降包装成重建进步。
