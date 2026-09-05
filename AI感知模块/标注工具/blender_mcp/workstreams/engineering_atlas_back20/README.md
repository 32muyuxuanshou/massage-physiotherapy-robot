# ENG_BACK_20_V1

本工作流一次性在 canonical SKEL 女性皮肤上构造 E01–E20 工程试验点，并以固定
`face_index + vertex_indices + barycentric` 冻结。它们不是医学穴位。

最终有效交付：`outputs/交付文件/2026-08-28_17-05-07/`。Atlas SHA-256：
`2f4b92697308bc66458c4d98ee8733a0f4c799390dba51c61abf15767ddd0b6f`。

左右约定来自 SKEL 官方 `loader/skel/kin_skel.py` 关节顺序与坐标：canonical object-local
`+X=SUBJECT_LEFT`、`-X=SUBJECT_RIGHT`。验收阶段不得重新选面。

`2026-08-28_16-57-42` 因验证阈值配置错误失败，`2026-08-28_16-58-31` 因左右语义写反废弃，
`2026-08-28_17-03-13` 被更清晰的 QC 图替代；三者均不得使用。
