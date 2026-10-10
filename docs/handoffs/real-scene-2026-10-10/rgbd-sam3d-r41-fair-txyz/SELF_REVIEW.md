# R4.1 自审

- 原始 Official 与历史输入逐文件 SHA 匹配；六模型为 R4 best 对应缓存，原 checkpoint 实际 SHA 对应 HUMMAN_RESULTS，1392预测实际 SHA 核对。
- Anchor face/bary数组 SHA 精确匹配；232 A compact源文件 SHA、原索引和值保留，232 B实际样本 SHA及整体manifest与R3.1一致。
- 几何 metre，A→B变换重算与已存B顶点精确一致。4固定帧和232帧Official+Txyz全量trace/vertices/指标与历史差值均0。
- 六R4 raw表从原始网格重新评价，与旧R4记录一致；没有换baseline或复用已拟合body。
- fit_txyz仅接收A观测与A mesh anchors；B只用于精确评价、固定区域的评价归类和显示。机械交换及中心归一化均由A保存输出决定，无B对齐。
- 1624最终文件重开：camera和顶点只平移一次，global_rot/body_pose/shape/scale不变；fallback、6次迭代、步长上限检查通过。
- 配置中冻结的科学执行入口及历史数值核源码前后SHA不变，固定A/B输入SHA不变；8最终Mesh案例不调用fit而重算距离，逐点数组一致。
- 正常解析平移案例通过；未增加与本任务无关的负测套件。
- 样本232全部保留；三seed、每身份、每帧、P95恶化及原有16帧×3seed图全部交付。距离与区域/原生参数均先sequence后identity等权；fallback分层另列为逐帧诊断均值。
- 可视化是缓存顶点原K透视投影，不是新推理。绿色仅预测轮廓，紫色是预测覆盖；热图固定0–150mm，最大值没有被删除。
- 没有真实MHR对应GT，没有穴位/医学/裸背精度结论。HuMMan站姿衣物开发诊断不替代最终俯卧任务验证。

结论：代码实现、缓存执行与本合同表面比较均已实际验证；G1的人体/解剖精度优势未被验证。本轮结束暂停。
