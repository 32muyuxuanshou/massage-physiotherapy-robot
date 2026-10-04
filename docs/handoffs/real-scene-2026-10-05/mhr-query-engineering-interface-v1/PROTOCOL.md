# 回到俯卧工程：模板query→观测→预测Mesh接口

这是离线联调/对照，不是新医学精度实验。成对模型跨SCAPE已退化，不能替换现役拓扑基线。保留原20人、4/16历史角色、3个train-only划分；不训练、不重新推理SAM、不拟合Mesh、不读取留出点作输入。

查询固定为既有ENGINEERING_BACK_ATLAS_V2八个ENG探针（face/bary），不使用语义HOLD的穴位名。源MHR raw cm×0.01得到m，缓存患者Mesh原生m不变。

沿用Rigid / RigidD两种最终缓存。每分支用MHR同拓扑后背顶点的Kabsch粗刚体框架，把观测点还原到canonical方向；全Mesh面积/面积加权中心归一化。这是新的MHR数据适配合同，区别于前面均匀remeshing的vertex-centroid，全部显式保存。框架来自既有预测Mesh，不是医生或真实患者姿态GT。

原训练点里的后背点按12mm voxel首点、最多2048点固定采样；模型法向只从这些点的12邻域估计。所有方法共享候选点，留出交集0。

对照：TOPOLOGY（原face/bary直传）、BODY_NN（源query几何近邻）、PAIR_GLOBAL/PAIR_LOCAL（三冻结初始化）。源query描述子按source face三顶点bary插值，匹配观测候选后精确投影到当前预测后背三角面，导出xyz_m/face_id/barycentric/normal/source_point_idx、框架和权重hash。

不需要FAUST↔MHR顶点映射；query来自当前给定模板几何，模型不读取医学标签。**这也不证明两模板间的人体语义已正确泛化。**全8query均输出实验结果；没有真实身份/可见性GT，不能用几何贴面距离或稳定性当准确率。medical_label=false、robot_release=false，默认仍为拓扑工程基线。

记录：绑定输入跨度、模型初始化跨度、相对Topology的位移（不是误差）、观测→预测面投影距离（不是穴位精度）、全部20人图和失败。图从缓存产生；原始RGB仅本地/服务器。模型训练数据仅限非商业研究，当前接口也只作研究用途。

本轮成功标准是端到端路径与可复查数据流完成，不能据此批准新模型/穴位治疗。若图或点偏移严重，明确不采用；不在这些人上调整坐标/训练权重。
