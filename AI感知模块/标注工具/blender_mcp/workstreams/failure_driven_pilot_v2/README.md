# FAILURE_DRIVEN_PILOT_V2

保持 V1 的 `TinyHeatmapNet`、seed、输入/heatmap 分辨率、训练入口、val/test 和 C4 challenge 不变，
只向每条 split 的原训练 case 增加 `TRUNCATION_GATE_V2` 已通过的左右轻/中度真实 Camera 截断图。

- 训练外观：A00–A03。
- 截断 holdout 外观：A04。
- V1 val/test ID 必须逐字不变。
- 每条 split 的新增训练图只能来自其原有 `train_case_ids`。
- 严禁把 holdout 图或 test case 加入训练。
- E01–E20 是非医学工程点。

第一轮继续使用同一 TinyHeatmapNet 做数据 A/B，不更换 RTMPose/HRNet，不处理 C4，不加入随机遮挡。
