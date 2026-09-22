# 穴位定位证据矩阵与路线裁决

检索日期：2026-09-21。检索范围包括 WHO/中国国家标准、CT/三维数字人体、穴位定位一致性研究、计算机视觉与机器人辅助定位。

## 证据摘要

| 来源 | 直接支持的事实 | 对本项目的含义 |
|---|---|---|
| [GB/T 12346-2021](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=397548AE7248D3D87DD15E0AB8107185) | 现行国家标准，定义经穴名称与定位；B-cun 是按人体分段和骨性标志折量，不是固定毫米坐标。 | 规则引擎必须保存定位依据和个体化比例，不能把 canonical MHR 的绝对 XYZ 当穴位标签。 |
| [WHO Standard Acupuncture Point Locations](https://iris.who.int/bitstream/handle/10665/353407/9789290613831-eng.pdf?sequence=1) | 采用体表解剖标志、比例骨度 B-cun、手指同身寸 F-cun；在规则不清时优先解剖标志。 | 先找标志，再计算比例；模型预测应服务于标志/残差，而不是绕过规则。 |
| [Kang et al., 2014, 3D CT whole-body atlas](https://pmc.ncbi.nlm.nih.gov/articles/PMC3929431/) | 用 CT 骨骼、皮肤和 361 个标准穴位构建 3D 人体；37% 可自动链接参考点，11% 是参考点，约 52% 仍需逐点定位。 | Mesh+规则可形成可解释基线，但不能假设所有穴位都能由少量关节直接推出。 |
| [Accuracy and Precision systematic review](https://link.springer.com/article/10.1016/j.jams.2018.10.009) | 归纳出体表标志、B-cun、F-cun 三类基本方法；比例法仍受操作者技能影响，证据总体有限且存在偏倚。 | 需要报告规则基线的误差和一致性，不能把标准公式当绝对 GT。 |
| [Bäuml­er et al., 2012](https://pubmed.ncbi.nlm.nih.gov/22398924/) | 有经验针灸师定位同一点仍存在较大差异，LI10/TH5 的 95% 定位区域和最大点间距都很大。 | 穴位应视为带容差的表面目标/区域；评价不能只用单点硬阈值。 |
| [Groenemeyer et al., 2009 CT localization](https://pubmed.ncbi.nlm.nih.gov/20001835/) | BL25/BL26 的 CT 位置与椎旁距离、软组织厚度和 BMI 有关；作者认为比例方法与成功定位相关。 | 个体体型和软组织会改变表面点与内部结构的关系，MHR 只能提供表面载体。 |
| [Kang et al., 2018 Baliao CT 3D](https://xb.njucm.edu.cn/en/article/id/ZR2018_0209) | 将体表标志、骨度比例和 CT 三维重建结合，形成“影像→骨度→穴位公式”的定位流程。 | 支持我们的规则优先 pipeline，但前提是有真实标志/影像或可解释 proxy。 |
| [FaceAtlasAR, 2021](https://arxiv.org/abs/2111.14755) | 使用人脸对齐/密集参考点，再按 B-cun 进行个体化可视化，并指出人工定位存在技能误差。 | 视觉系统的合理角色是找参考点和做映射，不一定直接回归穴位。 |
| [Real-time location via landmarks vs pose estimation, 2024](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2024.1484038/full) | 直接比较 landmark+比例映射与 fine-tuned pose；受控数据上两者都可行，但作者指出 landmark 误差和复杂真实场景泛化是限制。 | 应把规则基线、直接回归和 hybrid correction 分开实验，不能只报告训练模型。 |
| [Structure-guided back acupoint localization, 2025](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2025.1662104/full) | 430 张背部图、19 个点；以肩胛/脊柱稳定标志构造 subject-specific cun 空间，再加入结构约束损失；报告 NME 0.6%。 | 这支持“结构坐标 + 学习残差/约束”的升级路线，而不是支持固定 canonical 点直接传播到真人。 |
| [Human back acupoints with RGB-D for massage robots](https://peer-review.actapress.com/Abstract.aspx?paperId=55301) | RGB-D、姿态和 3D 坐标用于按摩机器人，摘要报告平均点位误差 10.57 mm。 | 机器人评价应使用 3D 表面误差和坐标系审计，不只看 2D pixel error。 |

## 证据裁决

证据支持：

1. Mesh 可以作为个体化表面载体；
2. 解剖标志和 B-cun 应优先作为定位逻辑；
3. 学习模型可以识别标志、补全遮挡或学习规则残差；
4. 规则基线、直接回归和 hybrid 方法必须分开比较。

证据不支持：

1. 仅凭 SAM3D 的皮肤 Mesh 就能直接得到医学穴位真值；
2. 将 canonical MHR 的固定 XYZ 直接传播到每个真人；
3. 没有真人/医生标注时宣称毫米级医学精度；
4. 用穴位模型输出替代安全深度、针刺路径或临床判断。

