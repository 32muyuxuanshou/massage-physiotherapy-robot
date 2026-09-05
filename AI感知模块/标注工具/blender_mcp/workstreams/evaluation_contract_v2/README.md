# EVALUATION_CONTRACT_V2

该 workstream 只复算现有 360 样本 Pilot 的三个 grouped holdout，不训练模型、不生成新图像，也不修改
正式插件、模型、Atlas、Blend 或发布包。

1. `build_evaluation_exchange.py` 把当前 GT、预测、可见性、相机和 Depth 引用导出为稳定 CSV；
2. `evaluate_exchange_independent.py` 只读取 CSV、原标签和 Depth，不 import 原训练或评估代码；
3. 输出原图坐标系 P90/P95/P99、3D 尾部失败率、按基础几何聚合的统计和 A/B/C 三路 3D 误差分解；
4. 新结果必须精确复现原 independent evaluator 的 2D/3D count、mean 和 max。

E01–E20 仍是非医学工程点。A/B/C 误差分解是诊断量，不能相加，也不能作为机器人安全证明。
