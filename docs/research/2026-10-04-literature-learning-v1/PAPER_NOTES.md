# 逐篇学习：机制、证据和适用条件

“原文”描述作者做了什么；“对我们的启发”是本项目的推断。定位依据为[PAPERS.json](PAPERS.json)中的实际下载版本，不把摘要阅读写成全文通读。

## 1. 3D-CODED：模板保持连接，不保证对应正确

[原文：ECCV2018](https://openaccess.thecvf.com/content_ECCV_2018/papers/Thibault_Groueix_Shape_correspondences_from_ECCV_2018_paper.pdf)。方法 pp.5–6；对应消融 pp.13–14。

**原文机制。** PointNet式编码器把输入点云编码为全局向量；解码器同时接收该向量和模板点坐标，预测模板点的形变位置。推理可继续优化潜向量来降低 Chamfer 距离，再经模板建立两个表面的对应。无对应标签时，加入 Laplacian 和边长正则。

**核对图表。** Fig.8 的未正则化输出点云覆盖人体，但连接后的 Mesh 出现严重拉扯；加正则后形状与对应更合理。Table3 的 FAUST对应误差分别为8.727、4.835、2.878 cm（Chamfer、Chamfer＋正则、有监督对应）。这是对应误差，不是我们的传感器→三角面中位距离。

**对我们的启发。** Rigid+D 的低贴面距离必须配合 canonical身份、翻面和局部伸缩检查；保留 face_id 只是保留索引，不证明这个面仍是正确解剖部位。边长/Laplacian 是已有基线，而且背部受床面压迫并非严格等距形变，不能把强等距约束当万能解。

## 2. Point2SSM：表面采样与对应质量同时评价

[原文与发表信息](https://arxiv.org/abs/2305.14486)；本轮读取 arXiv v2。方法 pp.4–6，缺失实验 pp.8–9。

**原文机制。** DGCNN 提取点特征；自注意力模块输出权重，Softmax 后与输入 XYZ 相乘，生成有固定顺序的对应点。训练用重建 Chamfer 和批内样本间的邻域 mapping error，不需要预先优化好的对应标签。

**核对图表。** Fig.2 确认输出来自输入点的加权组合；Fig.4–5 分开展示贴面和群体对应，Fig.6 对噪声、稀疏、5/10/20% 连续缺失及训练量做对照。数据是脾、胰腺、左心房的已粗配准表面；缺失实验训练/测试按同一方式破坏。

**对我们的启发。** 注意力加权和非负归一化权重已有先例，当前 Convex4 不应包装成新理论。输入点的凸组合位于凸包内，**不保证在非凸皮肤表面上**，也不能任意补出缺失凸起。群体统计对应不自动具有椎体编号或穴位身份；同分布模拟缺失也不能替代真实俯卧遮挡验证。

**复现注意。** [官方README](https://github.com/jadie1/Point2SSM)明确说明，`test.py`输出的Chamfer基于缩放数据，论文使用未缩放数据。后续引入这一基线时必须恢复物理单位，并用共同评价器重新计算，不能直接把脚本输出当毫米距离。

## 3. BodyMap：学的是“图像像素对应哪块模板表面”

[原文：CVPR2022](https://openaccess.thecvf.com/content/CVPR2022/papers/Ianina_BodyMap_Learning_Full-Body_Dense_Correspondence_Map_CVPR_2022_paper.pdf)。方法 pp.3–5；Fig.2–3、Table6。

**原文机制。** RGB/foreground与已有 CSE 粗对应送入独立编码分支；Transformer 特征融合后解码稠密对应。论文用连续表面着色方案，并以三个RGB通道的分类实现预测；损失含像素分类、轮廓、表面测地距离和一致性。不能把“颜色相似”当作“解剖位置相近”。

**数据与核对。** 主训练来自注册、动画化的 RenderPeople 扫描；DensePose-COCO 的真实适配用稀疏标注加 CSE 扩展伪标签。Fig.3 处理衣服/头发轮廓，Table6 区分不同损失。这种覆盖衣物的语义对应不意味着恢复衣物下真实皮肤。

**对我们的启发。** 为背部点学习 canonical坐标，比仅输出三维位置更直接地处理点位身份。但稠密伪标签来自已有模型时会继承其偏差，必须用未参与伪标签生成的参考评价。SMPL对应也不能未经验证直接复制为MHR顶点编号。

## 4. DenseMatcher：学习三维对应可以服务机器人，但标签定义很重要

[原文：ICLR2025正式版](https://proceedings.iclr.cc/paper_files/paper/2025/file/7ba6b5b03ae07151a9a353b51f943290-Paper-Conference.pdf)。方法 pp.5–6；实验 pp.7–9；partial matching pp.21–22。

**原文机制。** 多视图渲染提取冻结的 SD-DINO/FeatUp 特征，投到 Mesh 顶点后结合几何描述和位置编码；训练 DiffusionNet 细化特征，再用 functional map 建立对应。训练同时约束语义组距离与原特征保留；部分表面另引入 partial functional correspondence。

**核对图表。** Fig.6 为架构，Table1 区分三维细化、特征保留、mapping约束；Fig.7 将示教接触点转到目标物体再调用抓取模块。其语义组指标允许匹配到组内最近点，并非精确逐点解剖误差。机器人结果来自六个物体任务，每任务五次测试。

**对我们的启发。** “冻结大骨干＋学习表面模块”可以是合理工程选择，但这一组合已有工作。背部少纹理、只有部分观测、会发生软组织形变，必须单独验证；水果/物体语义组不能作为医学身份标签。正式版与作者网页的数据规模表述不同，未实际核对发布清单，不把网页数量当成已下载的训练资产。

## 5. DiSRT-In-Bed：扩散的是人体参数，不是生成训练图片

[原文：CVPR2025](https://arxiv.org/abs/2504.03006) · [作者项目](https://jing-g2.github.io/DiSRT-In-Bed/)。方法 pp.3–5；Tables1/2、Fig.4在pp.6–7。

**原文机制。** 输入是床上方深度图。对SMPL参数加噪并以深度特征条件去噪，用残差/注意力与自适应归一化预测参数；先合成预训练，再按真实数据量调整微调学习率。监督含人体参数与顶点位置。

**核对图表。** Fig.2 明确合成训练→真实微调；Fig.3 连接深度、噪声参数和时间条件；Table1 列出真实样本比例。仅合成时该模型并非所有比较中最优，加入真实监督后改善。SLP人体标签来自既有SMPL拟合；医院七人无Mesh标签，只提供定性比较。

**对我们的启发。** 合成可提供已知canonical对应与姿态覆盖，真实数据负责验证/适配。这里的成功不证明俯卧裸背毫米级表面精度；我们的目标也不要求生成多个可能人体。因此优先借鉴分阶段数据策略，不因论文用了扩散就立即加入扩散模型。

## 6. VoteHMR：局部点云的结构补全已是明确先例

[原文：ACM MM2021](https://arxiv.org/abs/2110.08729) · [官方代码](https://github.com/hanabi7/VoteHMR)。方法 pp.3–5；实验 pp.6–7。

**原文机制。** PointNet++ 点特征预测身体分区、到关节的投票偏移和特征；聚合成关节后补齐不可见节点，分别回归全局shape/rotation与图卷积的局部pose。训练结合关节、SMPL参数、顶点和单向点云距离。

**核对图表。** Fig.2 展示完整链；Table3 分别去掉投票、补全与全局回归。合成基准有对应顶点参考，真实Berkeley MHAD无人体Mesh真值，用输入点云距离评价。Table2 的51.76→24.44 mm包括真实数据弱监督适配，不能当成独立传感器留出改善。

**对我们的启发。** 旧Idea1通用描述与这篇高度重叠。我们需要解决的是局部后背的度量表面和身份，而非再次证明关节补全可行。官方旧环境不等于已在本项目复现；参考骨干与模块后应先核查代码/权重适配。

## 7. BodyMAP：Mesh 上的下游量可学习，压力不是穴位

[原文：CVPR2024](https://arxiv.org/abs/2404.03183)。方法 pp.3–5；Fig.3–4、Table1（pp.4、7–8）。

**原文机制。** 深度/压力图由ResNet18编码并回归SMPL；FIM按Mesh顶点投影采样图像/特征，PointNet预测顶点压力与接触。WS分支冻结已监督训练的Mesh模型，以二维压力投影训练三维压力；**不是整个人体模型无监督训练**。

**核对数据。** BodyPressureSD＋SLP，主要仰卧和左右侧卧。Table1也有depth-only版本，其PVE约72.47 mm，深度加压力约61.66 mm；参考是SLP拟合SMPL。两项均不等于背部传感器距离，也不等于穴位误差。

**对我们的启发。** FIM适合学习“在表面上读取RGB/深度证据”，但不能把压力接触head改名成穴位head就获得医学监督。RGB-D-only系统应比较其depth-only变体，不能用压力垫结果解释相机系统性能。

## 8. Markerless spinal assessment：真实微几何能提供候选，验证范围有限

[原文：IJIDeM2026](https://link.springer.com/article/10.1007/s12008-026-02603-8)。几何方法 pp.5–8；采集/验证pp.10–12。

**原文机制。** 局部四次Bézier片估计主曲率/shape index，在背部对称线上采样，以平滑后的导数极值和拐点提取候选。其输入是高分辨率结构光表面；并非普通RGB模型生成的光滑模板。

**核对图表。** Fig.3 把3D表面、原始/滤波曲线与标记水平对齐。21名年轻健康志愿者、单专家触诊标记参考；Table1及正文报告约3.7 mm一致性。作者明确没有影像骨骼金标准，额外候选的真实身份仍不确定；98.6%是匹配标记比例，不是网络置信度。

**对我们的启发。** 可以增加曲率/shape-index作为几何基线，不能据此称自动恢复了T3/L2编号。0.5 mm扫描采样分辨率不是测量精度承诺；原流程也不能直接移植到衣物褶皱、消费级深度或平滑MHR表面上。

## 两项数据/输入审计和SAM复读

- **[Bodies at Rest / CVPR2020](https://openaccess.thecvf.com/content_CVPR_2020/papers/Clever_Bodies_at_Rest_3D_Human_Pose_and_Shape_Estimation_From_CVPR_2020_paper.pdf)，pp.6–7、Fig.7：**206K合成数据有SMPL标签；真实20人采集了RGB、点云和压力，含俯卧。真实3DVPE是点云/可见Mesh顶点最近距离，并处理可见性与采样密度。论文的合成Mesh标签不能借给真人充当精确真值；这也是我们当前数据可信但用途有限的原因。
- **[JOTR / ICCV2023](https://openaccess.thecvf.com/content/ICCV2023/papers/Li_JOTR_3D_Joint_Contrastive_Learning_with_Transformers_for_Occluded_Human_ICCV_2023_paper.pdf)，pp.3–4、Fig.2：**只有图像输入；从2D特征提升3D体素/关节特征。“2D＋3D表征融合”不等于RGB＋传感器深度融合。本轮只核对这部分，未完整重审其实验。
- **[SAM 3D Body / CVPR2026](https://openaccess.thecvf.com/content/CVPR2026/papers/Yang_SAM_3D_Body_Robust_Full-Body_Human_Mesh_Recovery_CVPR_2026_paper.pdf)，用户已有PDF pp.3–5：**RGB编码器、body/hand解码器和mask/2D关节prompt，输出MHR；训练标注使用人工稀疏关键点、595稠密关键点与单/多视图fitting，混合真实/合成数据。它没有在这里定义RGB-D背部微几何/穴位身份监督。新增解剖标志需要明确新标签与接口，不能默认已有prompt已经认识穴位。

## 从论文怎样组织证据中学到的三件事

1. **先定义不同输出。** Point2SSM明确分开表面采样与对应统计；我们也应分开距离、点位身份与医学参考一致性。
2. **每个模块回答一个实验问题。** VoteHMR与DenseMatcher有各自机制的消融；我们的“加深度”“加对应”“加参考线”也应逐项比较，共同输入/初值/测试证据保持清楚。
3. **下游使用要真的验证。** DenseMatcher分别报告matching和机器人任务；我们的Mesh图、ENG点导出、真人穴位与机器人接触不能混成一个已完成贡献。

这些是读具体图表后的写作/实验建议，不是Oral录用规律，也不表示照此组织就会被录用。
