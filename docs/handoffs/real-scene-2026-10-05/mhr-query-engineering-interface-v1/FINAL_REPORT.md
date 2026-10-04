# MHR 模板查询工程接口 V1

已接通：8个固定工程query→同一患者MHR Mesh上的xyz/face/bary/normal。原拓扑传播仍为默认；成对学习匹配明确不采用。此阶段不增加训练、SAM推理或Mesh拟合。

## 输入与执行

原20位PressurePose受试者、既有4开发/16已消费测试角色、3个训练点空间划分，Rigid与RigidD缓存完全保留。实际打开原始p_select.p核查：20/20选中索引的pose_type均为`p_sel_prn`；p_select本身表示自选姿态集合，不等于俯卧标签。见POSE_SOURCE_CHECK。

canonical MHR原生cm×0.01→m，患者缓存原生m。固定2152后背面、1196源模板顶点。原始全Mesh面积中心/sqrt(area)归一化，利用同拓扑后背Kabsch作为整体姿态参考；这与训练扫描的顶点均值中心不同，作为显式迁移差异保留。

目标只使用各split训练点：后背筛选、12mm体素首次点、最多2048候选。没有留出点进入输入或优化。模板query描述子从面三个角点按原bary插值；学习/几何候选投影到实际患者后背三角面。8个点为工程点，不是医生穴位。

实际48.63秒，960绑定、7680点、120候选缓存；实际120原Mesh、960绑定检查4800项PASS，源资产217份不变。Git包含960绑定NPZ和120个用于重算的预测MHR面缓存；不包含原患者RGB-D或扫描训练数据。

## 结果与判断

16位已消费测试角色、RigidD，先固定模型初始化计算三个输入split最大位置跨度，再初始化平均，最后受试者中位：

| 方法 | 输入划分位置跨度 mm | 候选到表面投影距离 mm | 与拓扑点位置差 mm |
|---|---:|---:|---:|
| TOPOLOGY（默认） | 7.39 | 0.00 | 0.00 |
| BODY_NN | 18.11 | 2.89 | 88.12 |
| PAIR_GLOBAL | 22.03 | 2.13 | 193.70 |
| PAIR_LOCAL | 25.07 | 2.09 | 174.18 |

“离表面2mm”只说明投影候选接近当前预测Mesh；位置可能已经跑到别的身体部位。193.7mm是**与拓扑点的差**，不是已知医学真值误差；然而加上跨库身份误差及输入波动，足够拒绝把该学习模型升为工程默认。

原拓扑传播更稳定，但7.39mm同样不是医学定位准确率。我们没有真人解剖/穴位真值，当前相机仍是历史重建近似合同。不能用这个结果批准治疗或宣称“穴位定位7mm”。

## 可直接审查的接口

- [全部结果](RESULTS.json)、[逐人CSV](PER_SUBJECT_RESULTS.csv)、[实际缓存核查](CACHE_REPLAY.json)、[独立交付重算](DELIVERY_REPLAY.json)。
- [原始绑定索引及hash](TARGET_MANIFEST.json)、[960实际绑定缓存](targets)、[120预测MHR面缓存](mesh_reviews)、[面缓存对应表](MESH_REVIEW_MANIFEST.json)。
- [40个默认/实验输出JSON](exports)：每人TOPOLOGY与固定model0/input0的PAIR_GLOBAL，不按结果挑选。
- [20人全方法图](figures)是camera XY正交诊断，标题明确；真正RGB透视叠点在本地`output/mhr_query_engineering_interface_v1/private_rgb`与服务器，使用历史K，不冒充相机验证。
- 纯NumPy运行`code/replay_delivery.py`可从交付缓存重算face/bary/normal、投影距、拓扑位置差，无需重拟合。

运行服务器：`/raid5/xuhd/datasets/mhr_query_engineering_interface_v1_20261005`；源码run_interface/analyze_interface。姿态输入与SurfaceProject接口已完成，下一项切到曲面几何编码和正确身份匹配，不重复修单位或多训这两个失败模型。
