# SKEL 原生自然俯卧 Pose 工程门

本工作流在固定 canonical SKEL、冻结工程锚点、相机、床面与刚体俯卧矩阵的前提下，只改变 SKEL
原生 46 维 Pose。正式冻结姿态见 `natural_prone_pose_profile.json`，构建入口为上两级目录中的
`build_natural_prone_pose_delivery.py`。

当前有效交付：`outputs/交付文件/2026-08-28_15-11-01/`。Pose 专项 15/15、RGB-D 独立验收
17/17 通过；A/P/R 拓扑与刚体变换一致，A→R 完整恢复，P 不穿入固定床面。

`2026-08-28_14-54-06` 是已标记 `SUPERSEDED_DO_NOT_USE` 的失败尝试：它按每个姿态的全局最低点
重新调平，掩盖了手臂穿床与躯干悬空，禁止用于训练。

所有 `ENG_*` 只是工程锚点。本门不证明医生认可的穴位传播、真实床垫/软组织接触、Shape 变化、
真实 RGB-D 相机或批量数据生产。
