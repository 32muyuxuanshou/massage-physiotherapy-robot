# R5.2执行自审

实际完成：2706个固定起点×18方法=48708条方法评价；POST_INTEGRITY PASS，实际重读14181个文件。没有训练。

|核验|证据|状态|
|---|---|---|
|原Full Last三个内部Coarse与相同Body|原预测SHA、原Query重放、源Body逐数组核对|PASS|
|原历史Txyz算法/点集|直接调用原fit_txyz，全部真实帧raw/applied差<1e-6m且fallback一致|PASS|
|求解器数学|解析平移例、中位数路径与历史算子完全相同、点面秩亏最小范数例|PASS|
|旧独立指标复现|先导11帧、全量全部真实参考；新全量记录最大差0.00000000mm|PASS|
|A/B隔离|只用A生成全部平移，再独立评价；B未进拟合或选参数|PASS|
|限幅与fallback|新增几何方法每轴50mm、各自起点177.888mm总限；raw/applied均记录，原Fine不额外限幅|PASS|
|固定点集与完整帧数|Native400、HuMMan192/40、BEHAVE270；三个seed均保留18方法|PASS|
|未变更执行文件与输入|正式EXECUTION_FREEZE + POST实际SHA|PASS|
|失败/P95/逐人|完整RESULTS、CSV、原fallback子组、已知人物与最坏退化帧|PASS|

## 两次技术修复

准备最初用NumPy float64计算采样像素，半像素边界与原CUDA grid_sample不一致；已按原CUDA采样核对，未改源Depth或放宽容差。评价先导最初把Official+Txyz对比到旧triangle（未修正）字段；改为triangle_txyz后复现通过。两份失败日志保留。它们发生在正式对照前，不是模型或科学方案失败。

SCIENCE_FREEZE是准备时的历史快照；最终运行验证使用EXECUTION_FREEZE，包含实际修复后的求解/评价代码。报告工具在结果完成后开发，公开Git另有全部交付文件哈希。

## 解释边界

本轮不证明3mm的唯一来源，也不是全因子、最优解或性能上限。四个数据组的匹配一步控制显示3D NN并不自动优于投影。改变Anchor数也改变离散表面近似；对应方向会改变配对数量和覆盖。

Native的Camera参数GT与顶点/表面目标有取舍；真实域没有原生MHR参数真值。BEHAVE包含遮挡和异常深度，拟合SMPL不是绝对裸背GT。部位是工程proxy，不是医生标注后背。所有坏点与失败帧保留。

Native/HuMMan封存TEST未读；BEHAVE是已消费官方TEST子集。三seed是原父模型的不同起点，不是新增训练重复。Native的Official+Txyz使用本轮预冻结noisy格点新建诊断基线；历史复现指真实HuMMan/BEHAVE。

私有缓存的最终Mesh由共享Body和位姿恢复，图片不重新拟合。没有完整RGB→Mesh计时，缓存吞吐不能宣称毫秒级端到端。没有自动把最佳诊断设为新模型，没有追加训练或关闭服务器。备份以实际SHA回执为准。
