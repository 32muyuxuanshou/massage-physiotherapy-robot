# Back → DMD37 Bridge / Posterior V2

## 结论

本轮没有继续训练 SAM 3D Body，也没有放行 DMD37 Atlas。现有证据把主要瓶颈定位到两个上游定义：真实 RGB-D 中的后背躯干语义区域尚无独立合格标注；DMD37 从既有 Atlas 到 MHR 表面的两种桥接候选存在 20–30 mm 量级的表面切向分歧。两项都未解决前，合成 DMD37 标签、工程伪标签和 RTMPose 训练都会把不确定性固化为监督信号。

最终 Gate：

- `posterior_gate = POSTERIOR_GEOMETRY_NOT_READY`
- `bridge_gate = BRIDGE_REVIEW_INCONCLUSIVE`
- `synthetic_gate = SYNTHETIC_DMD37_NOT_READY`
- `final_gate = MESH_TEACHER_NOT_READY`
- `ready_for_dmd37_engineering_pseudolabel = false`
- `rtmpose_readiness = NOT_READY`

这些结论只涉及工程几何与数据准备，不构成穴位医学准确性结论。

## Track A：独立后背躯干标注审计

在查看像素前冻结了盲标协议。审计只使用此前已消耗的 Camera-B `kinect_009` 的 36 帧 RGB、Depth 与数据集 person mask，未向标注者展示 O/A/C/G Mesh、DMD37 点、误差图或模型输出；Final Deep Reserve 未动。

盲筛结果为 24 帧 `POSTERIOR_TORSO_VISIBLE`、9 帧 `NON_POSTERIOR_BODY`、3 帧 `UNCERTAIN`，覆盖 4 个受试者、10 个动作。24 个首轮多边形全部被独立 QA 驳回：它们是宽松 ROI，会包含手臂、髋臀或腿；斜视角下仅靠 RGB 不能稳定分开后背、胸腹和侧躯干；与 person mask 相交也不能提供躯干与四肢的语义分割。

因此没有运行 O/A/C/G posterior benchmark，也没有 posterior Chamfer、point-to-surface、normal、coverage 或排序结果。相关字段保持 `null`，避免把无效 ROI 当真值。

## Track B：DMD37 → MHR 桥接审计

验收规则在 V2 候选计算与视觉审查前冻结，SHA256 为 `9dab4850794feb2c2b8a24ff68d4fe6c1dbce234123bc13b58cf30ecd006d36d`。

目标资产为 MHR LOD1：18,439 顶点、36,874 三角面；资产 SHA256 为 `352e271a6c42729c68554ceaea0c955e866970160c31e35506d782dc0f7377bc`，面拓扑 SHA256 为 `f6748e290ef37fbb6877c4cc5bd7287105db9e98252b0ba170ae9ac3c45eacd6`。

审计结果：

- 拓扑与映射完整性：PASS。
- 官方 MHR↔SMPL roundtrip：PASS；P95 1.0905 mm，最大 1.2635 mm。
- direct support locality：FAIL；支撑直径均值 27.0465 mm、P95 33.2865 mm、最大 34.7155 mm，共 14 点超过冻结的 30 mm 上限。组合点到表面的 P95 仅 0.6231 mm，说明“落在表面附近”并不能证明支撑足够局部。
- DIRECT_SMPL 与 HISTORICAL_SMPLX 候选分歧：FAIL；欧氏距离均值 19.9169 mm、P95 29.0296 mm、最大 29.9431 mm。分歧主要是表面切向量（P95 28.9254 mm），不是法向离面误差。
- side、midline、posterior cross-section、LBS coarse region 与 bilateral symmetry：PASS。
- 冻结顺序规则：FAIL。协议将 BL43 错误规定为 BL15 后立即尾侧，属于合同语义缺陷；结果揭示后没有改门槛来制造通过。

随机 Q/R canonical 图显示两套候选都位于后背外表面，视觉上没有可靠偏好。该审查只能记为 `PARTIALLY_BLINDED_CANONICAL_ONLY_NONDECISIVE`，不能推翻数值失败。

没有生成 Atlas Release，`selected_bridge` 保持 `null`。

## V1 sensitivity 范围更正

V1 不能被描述为完整姿态/体型敏感性测试：shape 只扰动 identity PC 0–4（5/45）；scale 只扰动 expanded MHR 参数 139–150（12/68），网络原始 28 个 scale coefficient 未被直接扰动；原 `HIP_PELVIS_POSE` 实际是双侧上腿局部旋转子集，不是 pelvis/root orientation；shoulder 30–45 未覆盖左 elbow/lowarm/wrist 46–49；spine 仅为参数 6–23。normal/tangent 数值应称为相对 baseline MHR 表面法向的分量。完整清单见 `DMD37_SENSITIVITY_SCOPE_CORRECTION_V1.json`。

## Track C：合成 DMD37 readiness

相机、camera-Z depth、RGB/depth/mask 对齐、可见性、O/A/C/G 同源输入和评估指标合同已冻结并通过结构校验。但 Atlas Release 不存在，因此没有生成正式合成样本或 DMD37 GT。当前 sample、pose family、shape、camera 数量均为 0；没有 clean/smoke 指标，也没有最差 pose family。这是 `PASS_CONTRACTS_ONLY_ATLAS_BLOCKED`，不是合成精度验证。

## 对工程路线的影响

当前不能指定 Mesh teacher：O/A/C/G 仍只是历史候选，缺少独立 posterior GT 排名；DMD37 Atlas 也未通过桥接审核。因此不生成 DMD37 工程伪标签，不启动 RTMPose 微调。

即使以上 Gate 后续通过，仍需补齐与最终产品的域差异：治疗床上的裸背/局部遮挡、真实临床点位复核、机器人接触造成的软组织形变与遮挡，以及最终相机/深度传感器标定。

唯一下一步建议：先冻结 V3 correspondence adjudication 协议，修正解剖行组与顺序定义，并对高分歧 DIRECT_SMPL / HISTORICAL_SMPLX 点做独立裁决。桥接放行后才能产生可信合成 DMD37 GT；后背主线仍需真正的后背躯干语义标注工具或独立验证过的 torso segmentation 来源。
