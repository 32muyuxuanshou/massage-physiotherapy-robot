# 身体位置参考＋局部曲面查询学习 V1

这是从工程对应接口走向可学习主方法的一次结构对照。不是再训练前轮小网络，也不是正式医学精度研究。冻结SAM与已有Mesh，先解决query在局部可见表面上的身份匹配；表面拟合与身份定位仍分别评价。

## 动机与三个模型

前轮成对PointNet在SCAPE失败；完整DiffusionNet参考较好，但同样局部输入下冻结模型失败。因此比较：

- BODY_QUERY：局部XYZ按自身5%/95%分位范围归一化＋法向，PointNet局部/全局上下文，表示身体位置参考。其方向来自既定身体粗框架，不是GT身份。
- INTRINSIC_QUERY：作者预训练DiffusionNet局部HKS编码器，针对partial correspondence微调，查询128维描述子。
- DUAL_QUERY：两路特征共同编码source/target，同一query匹配头。几何提供局部曲面信息，身体位置参考用于缓解局部相似/左右歧义。它是候选结构，不能把concat本身宣称顶会创新。

源模板query描述子与目标候选用单位描述子cosine×20＋配对MLP匹配。纯几何分支MLP不输入XYZ差；BODY/DUAL输入归一化query→目标XYZ差。输出候选索引，绑定真实扫描三角面；未来MHR接口再以候选投影到患者预测面。

身体参考只读取当前patch观测的坐标分位数，沿前轮已知上方向/后背方向；不输入注册编号或测试GT。仍沿旧完整身体归一化与oracle后背ROI，不能说真实相机方向已自动解决。训练source/target粗方向独立±10°增强；算子/HKS保留原旋转不变结构，BODY法向同步旋转。

## 数据和监督

只使用既有FAUST000–059训练、060–079开发，080–099及SCAPE052–071均为已消费机制对照，不称新泛化。SCAPE不参与训练、开发或checkpoint选择。作者初始化曾训练80 FAUST，含本轮开发来源，必须说明；三分支不是同一预训练资源的绝对架构排名。

目标每次来自旧FULL/PARTIAL_BAND/NOISY_PARTIAL冻结case；源随机完整FAUST后背，独立pose。注册canonical身份仅用于构造source query任务和监督目标soft correspondence，模型只输入source/target几何和source query索引。24query、全局部候选；真实可见性在训练标签生成/考试评分使用，不作推理输入。

共同损失：CE到registered identity距离sigma0.01的soft target。不额外加不确定性、医学标签、shape/pose修正或新临床先验。每分支3初始化，1200steps、batch1（变长谱算子）、Adam匹配/位置分支lr0.001、DiffusionNet编码器lr0.0001；每200step只按固定20开发来源PARTIAL seed0选择checkpoint。每次训练24query，全候选，与上轮batch8/256采样不同，明确不作训练预算公平声明。

算子仅来自当前局部点云，与上一局部冻结对照完全同一构建方式；XYZ重合去重仅用于算子，GT仅评分时映回原case。完整/partial边界重新构建谱结构，不能使用完整body谱算子偷看缺失区域。

## 评价/工程决定

同一360消费case、26/27query、3input seeds；所有query均推理，可见GT只用于评分。报告身份median/P95、可见率、初始化变化、完整逐来源图；model seeds平均→input seeds平均→每扫描→20来源中位。单位%各库sqrt-area，不是毫米或穴位误差。

先冻结代码/配置/输入/初始化hash，再训练，再考试，一次完整执行。若跨库不改善，不继续在SCAPE上调权重；若改善，只进入MHR离线接口，不批准临床定位。最终工程默认仍Topo，临床语义和机器人接触另行验证。

服务器 `/raid5/xuhd/datasets/registered_human_correspondence_20261005/body_intrinsic_query_v1`。原数据/算子/权重服务器存放，代码、全量指标、hash及图Git交付。该阶段实际实现几何/位置两路，不包含RGB特征融合；不能宣称完整RGB-D端到端网络已经完成。
