# CANDIDATE_SHAPE_COMBINATION_VALIDATION_V1

仅验证固定自然俯卧 Pose、Camera、Bed、Light 与20点 engineering-reference Atlas 下的真正多 beta 组合。

- 输入只读：`2026-08-28_20-21-54`、`2026-08-29_16-21-55`、`2026-08-30_19-24-33`。
- 使用 F 线 `body_measurement_contract_v2.json` 和 anchor 2-ring 自交门。
- 复用 `training_export_core` 和现有俯卧 RGB-D 导出脚本，不复制投影/深度核心。
- 只允许形成 `QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1`，不声称全局人体安全或医学有效。
