# R5.2：同一Coarse起点的零训练求解器因子对照

本轮问题：原Full Last Fine与Official＋Txyz的差距，在同一Coarse起点上用显式几何求解能恢复多少？分别改变步数、候选点集合、对应方向和聚合算子时，实际发生什么？

**这是一轮诊断，不是新网络。** 不训练、不重构模型、不改变固定Body或旧评价点。不存在“数学保证不输Txyz”“终极上限”或接受率承诺。实际结果、完整完成状态与判断见以下报告。

实际已完成48708条评价，结束后的14181个文件SHA核验通过。主要结果如下，单位mm，三seed均值，全部是独立表面median / P95的层级均值：

|真实开发数据|原Full Fine|同Coarse＋历史6步|同Coarse＋点面LS6步|Official＋历史Txyz|
|---|---:|---:|---:|---:|
|HuMMan TRAIN|20.524 /76.648|19.987 /77.011|16.879 /70.677|24.645 /80.317|
|HuMMan VAL|14.359 /44.550|12.736 /45.322|10.646 /42.409|11.226 /41.604|
|BEHAVE|19.827 /83.583|21.246 /86.102|18.564 /82.194|16.524 /78.497|

**结论：直接将Fine换成完整历史Txyz，不是通用升级。** 它改善HuMMan，却使BEHAVE退化。点面LS在HuMMan VAL median略超旧基线，但P95和跨域结果尚未超过；BEHAVE seed37仍比原Fine差。它只是候选，不是事后选出的新模型。

同Depth、同可见Query、同一步中位数的控制中，3D NN在四个数据组、全部三个seed均比投影对应差。因此不能将差距解释成“只缺三维最近邻”。原11个HuMMan回退帧在Coarse＋历史6步下三个seed均不再回退，子组表面误差约12mm，证明Coarse仍有工程价值；不证明真实相机参数或穴位精度。

- [直观HTML：分数据集、每seed、18方法](reports/R52_零训练求解器对照.html)
- [完整结果表](reports/FINAL_REPORT.md)
- [解释与下一步判断](reports/ANALYSIS.md)
- [自审](reports/SELF_AUDIT.md)
- [复现步骤](code/REPRODUCE.md)

## 数据、起点与评价

|域|每seed帧数|输入/求解|评价|
|---|---:|---|---|
|Native VAL|400／50身份|原noisy缓存Depth/rays固定采样最多5000点|原GT对应顶点、Camera L2|
|HuMMan开发TRAIN|192／18身份|历史固定Camera A5000点|原Camera B2048点→预测三角面|
|HuMMan开发VAL|40／4身份|同上|同上|
|BEHAVE已消费子集|270／3人90序列|历史K0固定5000点|原K1/2/3各2048点→三角面；拟合SMPL PVE支持|

共3seed×902帧=2706个起点，18方法共48708条方法评价。Seeds11/23/37是原Full Last的三个内部Coarse，不是独立Coarse checkpoint，也不是本轮三次训练。没有把R5.1权重0.5模型换进来。

真实指标先每帧计算median/P95，再frame→sequence→identity各层等权；BEHAVE每帧先对三相机的统计等权。P95不是全体点合并后的P95。Native不同指标不能与真实表面混成一个总分。

HuMMan TRAIN/VAL、BEHAVE都已在历史分析中消费。Native/HuMMan封存TEST不读；BEHAVE是已消费官方TEST子集，明确保留该标签。

## 18种固定配置

|系列|配置|可回答的问题|
|---|---|---|
|固定参考|Official＋历史Txyz、内部Coarse、原Fine|旧系统分数与起点|
|主对照/步数|Coarse＋16384 Anchors，历史截断中位数1/2/3/6步|同起点的显式几何求解及迭代效果|
|点集|全部256／初始可见256子集，Obs→Mesh中位数6步|减少候选Anchor、再约束可见候选的影响|
|方向|初始可见256，Mesh→Obs中位数6步|固定点集下改变匹配方向|
|算子|相同密集Obs→Mesh对应，截断均值／点面LS／LS＋旧方向衰减6步|聚合目标和方向约束的整体迭代效果|
|对应方式|原Fine射线赋值投影／真实所采像素XYZ投影／同Depth格点3D NN，中位数1步|分开像素射线赋值与关联方式|
|局部算子|相同格点NN，均值／点面LS1步|相同初始对应下的聚合差异|

密集历史算法调用原fit_txyz：观测→Anchor最近邻，剔除欧氏距离最大的20%，逐轴中位数，每步每轴±50mm，6次。均值不等同中位数，点面LS也不是XYZ均值。

所有新增几何更新的总修正超过177.88820176363325mm时fallback至**本方法起点**。因此Coarse方法回到Coarse，Official方法回到Official。记录raw、applied以及相对Official的最终总位移，不把不同起点误说成放宽上限。原Fine参考不额外加历史限幅。

可见Query子集固定在最初Coarse，不在NN迭代中重筛。点面LS使用SVD最小范数解、rcond1e-6；lambda/(lambda+.01)的旧方向衰减单独一组。没有新置信度、学习权重或残差阈值调参。

## 对应方式比较的两个重要限定

投影与格点NN必须使用相同Depth信息。格点系列使用原缓存noisy Depth及其真实像素射线反投影XYZ，不把历史raw5000点与另一份Depth混称同输入。

原Fine把采到的Z赋给Query自己的亚像素射线；这与实际被采像素的射线存在量化差异。因此投影额外分两组，再用真实像素XYZ投影与相同XYZ候选的NN比较。准备阶段用原CUDA grid_sample复现float32取整，未放宽容差。

256点作为NN目标会同时改变离散表面的近似质量，不能全部解读成Fine看到的有效点数。多步的对应关系也随先前更新改变，因此本轮是有限匹配对照，不是完整全因子设计，不能宣称唯一原因或信息上限。投影直接取残差中位数也不代表最优投影求解器。

## 审计索引

- [配置](code/EXPERIMENT.json)、[输入冻结及实际源SHA](evidence/INPUT_FREEZE.json)、[正式求解代码冻结](evidence/EXECUTION_FREEZE.json)。
- [求解先导](evidence/SOLVER_PREFLIGHT.json)、[评价先导](evidence/EVALUATOR_PREFLIGHT.json)、[求解完成](evidence/FITS_COMPLETE.json)、[评价完成](evidence/EVALUATION_COMPLETE.json)、[执行结束实际SHA](evidence/POST_INTEGRITY.json)。
- [分域/逐人/每seed汇总](reports/RESULTS.json)、[全部逐帧CSV](reports/ALL_FRAMES.csv)、[预定义配对对照](reports/PAIRED_CONTRASTS.json)、[逐帧负收益变化](reports/NEGATIVE_UPDATE_TRANSFERS.csv)。
- [原Txyz fallback及已知失败身份](reports/KNOWN_FAILURES.json)、[部位proxy记录](reports/REGION_RESULTS.json)、[旧精确评价器](historical_code)。

先导先验证解析平移、平面退化的最小范数解，再核对历史Txyz的raw/applied/fallback与旧独立指标。全量平移只用A生成，之后独立评价；B不会进入求解或选超参数。Native GT不参与观测构造或拟合。

一个BEHAVE seed23的旧严格Query重放边界不一致，全部指标保留并标记；密集主对照不依赖这个可见mask。已知失败例与最坏退化例会展示，不只展示好看的案例。

准备阶段有两次明确技术修复：NumPy取整与CUDA半像素边界不同；旧指标核对最初误读triangle而不是triangle_txyz。失败日志保留，修正后再启动正式对照。INPUT/代码以正式EXECUTION_FREEZE为准，SCIENCE_FREEZE是准备阶段历史快照，不冒称其旧版本已通过最终代码核验。

## 运行与备份

218计算根：`/raid5/xuhd/rgbd_sam3d/r52_solver_factor_diagnostic_v1`。本地结果与备份：`E:/项目-按摩理疗机器人/output/r52_solver_factor_diagnostic_v1`。

私有完整卷R52_SOLVER_DIAGNOSTIC.tar.gz包含本轮A输入、共享Body、各方法相机/平移/迭代轨迹、独立距离与代码/报告。最终顶点由冻结Body和缓存变换恢复，不重新拟合。旧G几何包含原B点集/标定/GT，已有R5_FOCUSED_GEOMETRY.tar备份，SHA为`8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36`。

原始数据、点云NPZ和模型权重不入Git。本轮私有卷在218与Windows实际SHA一致后写备份回执。不关闭服务器，不追加训练，不将诊断最佳分支自动设为新的主模型。
