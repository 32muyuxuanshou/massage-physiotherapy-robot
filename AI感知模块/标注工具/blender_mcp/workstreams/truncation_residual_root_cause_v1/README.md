# Truncation Residual Root Cause V1

本工作流只读复用冻结的 FAILURE_DRIVEN_PILOT_V2 数据、模型和测试集，不生成新数据、不重训模型。

- `audit_perfect_heatmap.py`：按训练时真实 Gaussian target 合同做边界自解码。
- `compare_frozen_decoders.py`：在新截断 holdout 上导出四种 decoder 结果。
- `export_main_test_decoders.py`：在冻结 V1 主测试上导出同一 decoder 结果。
- `evaluate_frozen_decoders.py` / `evaluate_main_test_decoders.py`：独立 2D、Depth→3D 和分 Camera 评分。
- `independent_audit.py`：不 import 上述评分模块的最终复核。

`BOUNDARY_HYBRID_V1` 规则：当 heatmap argmax 落入最外 4 个单元时使用 log-marginal 三点二次拟合，
否则保持原空间期望。四单元边界来自完美标签在约 128 px 后偏差降至亚像素的解析审计，不得继续在
既有 test 上调参。

当前候选状态是 `DIAGNOSTIC_VALIDATED_ON_EXISTING_FROZEN_TESTS`，不是正式推理合同。下一门需新建
validation 与 untouched test；E01–E20 仍为非医学工程点。
