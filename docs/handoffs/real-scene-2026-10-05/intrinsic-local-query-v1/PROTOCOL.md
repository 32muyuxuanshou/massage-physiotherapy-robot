# 局部曲面几何编码对照 V1

目标：把可换模板的query接口接到成熟的曲面编码器，避免把小型PointNet失败误解为全部学习方法无效。本阶段是方法选择实验，不训练新模型，不改SAM/MHR，不改医学穴位定义。

使用上一阶段冻结的FAUST/SCAPE共360个考试case，20+20个扫描姿态，各FULL/PARTIAL_BAND/NOISY_PARTIAL×输入seed0/1/2。FAUST和SCAPE均已被上一阶段消费，不能再称fresh；SCAPE实际mesh052–071，详见上一阶段cohort clarification。FAUST模板26query，SCAPE27query；两库vts不跨库对应。

**主分支只能读取既有case中的可见XYZ/法向和本库模板后背XYZ/法向。** 不读取未观测身体表面，不读取GT对应/GT可见性，不能使用完整曲面的谱算子。现有全曲面DiffusionNet支持参考独立列出。

使用作者DiffusionNet commit `b1019b049597711d10259ce28250f7dfc4335a2b`、原FAUST-HKS权重；其作者训练使用80扫描（含我们开发集），本轮不训练、不挑checkpoint。主结果不声称新架构，也不与60扫描训练的小网络作完全同资源对照。

三个冻结分支：

1. HKS_NN：局部点云Laplacian，128谱基，16维autoscale HKS，单位描述子最近邻。
2. DIFFNET_DESCRIPTOR_NN：原作者4block/128width编码局部HKS，单位128维描述子最近邻。
3. DIFFNET_LOCAL_FMAP：同一编码器+原作者30基/λ0.001 functional-map，再target→template谱检索，反检索模板query。

算子输入为点云，不人为补回完整网格；坐标沿旧full-area归一化，明确仍利用完整身体的中心/尺度预处理与oracle后背ROI。vts可能对应重复物理顶点；仅算子构建按实际XYZ去重，再用first index映射回原case。噪声后非重合点不去重。此操作不使用GT编号，不过滤误差大的点，不改变评分query。

模板query对应其实际源点描述子；三个方法对所有query推理。GT可见性仅评分后使用，不作部署可靠性输出。保存全部query/检索索引、原case hash、算子和权重hash。误差为registered identity Euclidean distance / respective sqrt-area×100；不是毫米、测地距离、穴位准确率。

统计顺序：输入seed平均→每扫描/条件→20扫描中位；同时P95与可见率。保留全部失败、全部40扫描图。不依据考试数据加阈值、改损失或重训；若冻结全身编码器不适应局部边界，只能据此设计下一阶段局部训练，不能宣称架构无效。

输出路径 `/raid5/xuhd/datasets/registered_human_correspondence_20261005/intrinsic_local_query_v1`。原扫描、点云算子、权重、预测几何缓存留服务器；Git包含代码、协议、hash、完整逐case表、缓存重算记录和全量结果图。
