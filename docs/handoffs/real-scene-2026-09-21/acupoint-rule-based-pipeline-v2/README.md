# Acupoint Rule-Based Pipeline V2

本目录重新整理了“人体 Mesh 是否足以直接得到穴位”的证据与流程。

- [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)：论文、标准和工程含义；
- [PIPELINE_CONTRACT_V2.md](PIPELINE_CONTRACT_V2.md)：从真实图像到 Mesh、解剖标志、B-cun、表面投影和可选学习校正的合同。

裁决：**规则优先，学习校正；不是 Mesh 后直接黑盒预测穴位。**

## 本轮已执行的工程闭环

本目录现在包含一个最小可复现的 `RULE_ENGINE_CONFIG_V1.json`、`rule_engine.py`、`make_proxy_landmarks.py` 和 `run_rule_engine_sanity.py`。它在 canonical MHR 与现有 B1–B5 prediction mesh 上运行同一套规则，并输出规则目标、surface projection、face index、barycentric、surface normal 和未校准的 confidence 状态。`rule_sanity_v1/` 中的所有结果都标记为 `ENGINEERING_PROXY_ONLY` 与 `medical_truth=false`。

这一步的完成标准是：输入合同清楚、规则计算可重复、表面投影字段完整、工程代理不会被包装成医学结论。医生验证被有意放在工程链闭环之后。
