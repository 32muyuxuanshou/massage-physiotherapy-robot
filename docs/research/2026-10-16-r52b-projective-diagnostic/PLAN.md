# R5.2b：投影点面求解，有限零训练验证

## 对 Gemini 建议的判断

采纳“先用现有缓存做投影点面求解，不立即训练”。不采纳以下过强解释：

- 投影胜过NN只适用于R5.2已测试的相同点源、可见Query、一步中位数配置；不能推广为所有对应算法。
- 原Fine在HuMMan VAL落后于直接中位数，不足以证明MLP不会算几何；训练目标、泛化和更新约束均不同。HuMMan TRAIN和BEHAVE均值并非同样胜出。
- 点面LS在配对算子对照中有价值，但不是跨域绝对赢家。R5.2密集LS已去除20%最大欧氏对应残差，B端P95较高不能直接归因为未抑制离群点。
- 表格关联不能证明具体错误来自箱子、衣物或相邻肢体；需要真实对应可视化。法向投影也不保证对应正确，平坦区域仍有秩退化。
- 这不是“精确上限”，也不是“几分钟必跑完”。传统投影点面ICP有明确先例；单独采用该算子不构成新贡献。

## 冻结设计

沿用Native400、HuMMan TRAIN192/VAL40、BEHAVE270，3个父模型seed11/23/37，共2706状态。18方法，48708条方法评价；4项旧参考复用，14项新结果来自8条预设路径，不做全因子搜索。

主配对：256候选、相同可见性与重投影、截断20%、3步，中位数→点面LS。步数1/2/3/6；方向衰减、Huber、去掉截断、采样预算均为单独次级对照。Huber固定20mm、3次IRLS重加权，不用B校准，不与角度权重混用。保留trim+Huber和plain+Huber，分别对照其无Huber版本。

256为原linspace子集；1024包含该256，4096包含该1024，其余从原16384固定face/barycentric的补集按索引均匀添加。预算在可见性筛选之前，绝不声称有1024/4096个可见点。

每步重新投影、采样原始缓存A深度/有效mask、按原nvdiffrast合同计算Mesh自遮挡。20mm阈值用于自可见性，不用于选择B表现好的点。只改translation；每轴50mm单步上限；端点总量177.88820176363325mm以上回Coarse。Body/姿态/尺度不动。

首步CUDA采样必须复现旧Query和一步中位数；解析平移及平面秩退化QA。保留已知BEHAVE seed23可见性边界帧，不剔除。三卡各负责一个seed，先小批测时。全量A-only求解结束后执行固定B点的原精确点到三角面评价；Native GT仅用于评价。

逐帧→序列→身份等权，BEHAVE先K1/K2/K3等权。各数据集单列每seed、均值/样本SD、P95、coverage、fallback、可见数与法线谱、负收益转移和失败图；不合成跨域总分，不按B结果选权重或追加实验。

缓存网格由固定Body+保存的camera/delta重建；保存A输入、配置、轨迹和SHA。218与Windows私有备份，原始数据/权重/大NPZ不入Git。服务器保持开启。本轮结束不自动改可学习Fine或启动训练。

## 文献边界

[KinectFusion, Newcombe et al., ISMAR2011](https://www.microsoft.com/en-us/research/publication/kinectfusion-real-time-dense-surface-mapping-tracking/?lang=fr-ca)采用投影数据关联和点面ICP。本轮借用经典求解思想，限制为translation，不声称发明了该算子或等价于完整6DoF KinectFusion。

本轮使用已消费开发数据，属于机制探索，不是封存TEST确认试验。10.6mm median/41.6mm P95只是旧分数参考，不是成功承诺。只有实际结果支持后，另行评估是否需要学习权重及其监督来源。
