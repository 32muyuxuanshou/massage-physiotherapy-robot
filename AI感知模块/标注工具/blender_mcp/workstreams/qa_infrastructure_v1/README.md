# QA_INFRASTRUCTURE_V1

本工作流为 A/B/C 提供独立验收门，不产生医学结论，也不修改冻结输入。

## 门禁

1. 三份冻结交付的 SHA-256 清单必须全部通过。
2. 当前 E01-E20 必须经真值信封归一化为 `ENGINEERING_REFERENCE`。
3. 新测量合同不得在运行期依赖疑似医学穴位编码。
4. A/B 的 evaluated SKEL 皮肤必须经过非邻接三角形重叠检查；完整网格存在冻结基线重叠，因此硬门限定为20工程点二环表面邻域不得出现重叠，全局数量必须诊断记录。
5. 每条线的最终文件必须有来源、配置和输出哈希。

`BVH_NONADJACENT_TRIANGLE_OVERLAP_V1` 是几何 QA 谓词，不是软组织、床垫接触或生理合理性判定。当前自然俯卧 baseline 全局记录293对非邻接重叠，工程点二环邻域为0；因此任何报告都不得称完整人体 Mesh 已证明无自交。

## 2026-08-31 收口状态

- `audit_parallel_deliveries.py` 对 A/B/C 的最终 SHA 清单、未入清单文件、真值标志和冻结集合做独立复核。
- `validate_engineering_truth_tree.py` 已覆盖对象型 `truth_status`；回归测试位于 `test_validate_engineering_truth_tree.py`。
- 权威审计结果写入统一交付的 `F_qa/parallel_abc_independent_audit.json`。任何失败或 superseded 运行只保留诊断价值，不得替代该最终审计。
