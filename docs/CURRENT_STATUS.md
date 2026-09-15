# 项目当前状态

更新时间：2026-09-15

本页是项目现役研究状态入口。各 `docs/handoffs/` 目录保留当时的协议、结果和历史结论；发生冲突时，以本页指向的最新正式交付及其机器可读结果为准。

## 当前目标

从真实 RGB-D 图像恢复可用于背部工程定位的人体 Mesh，并在几何、DMD37 表面对应、真实域泛化和拒答条件均有证据后，才进入穴位定位模型训练。工程定位结果不等于医学穴位确认，也不能直接作为机器人执行坐标。

## 已经成立

1. 官方 SAM 3D Body 推理、MHR Mesh 输出和真实图像叠加已经跑通。只生成 Mesh 不需要重新训练模型。
2. Cheap Txyz 使用当前帧 Depth 只修正整个人体的 XYZ 平移。在冻结的 HuMMan 36帧实验中，主距离指标从 63.63 mm 降到 22.48 mm；在独立 BEHAVE 5人、15序列、45帧实验中，从 31.17 mm 降到 17.80 mm，5/5人物整体改善。指标是 Depth observation 到 Mesh 的单向距离聚合，不是完整人体双向表面误差或穴位误差。
3. [SAM3D → Txyz 正式复现实验 V1.4.12](handoffs/real-scene-2026-09-14/sam3d-txyz-reproducibility-isolation-v1/formal-execution-v1.4.12/README.md) 已完成，Gate 为 `PASS_REPRODUCIBILITY_ISOLATION_EXECUTION`：
   - 固定输入、环境、seed 和帧顺序的 SAM B–F cohort 共225次推理，450个两两比较的 vertex、anchor、camera translation 漂移均为0且 hash 完全一致。
   - Txyz 对45帧分别完成同进程20次和新进程20次重复，未发现分歧。
   - 27项预注册下游特征全部为 `STABLE`。
   - 三种帧顺序的7帧测试在21个配对中的6个发现极小浮点顺序效应，最大 vertex 位移0.000999 mm、最大 anchor 位移0.000919 mm。该结果不推翻固定顺序复现结论，但后续实验必须冻结帧顺序。
4. 正式复现使用的运行资产、输入、点云、结果和交付完整性都有 hash 绑定。Git 保留完整 JSON 审计包；大型逐帧 NPZ 留在服务器。

## 当前 Gate

| 事项 | 状态 | 含义 |
| --- | --- | --- |
| SAM3D → Txyz 固定顺序复现 | `PASS_REPRODUCIBILITY_ISOLATION_EXECUTION` | 可继续冻结协议下的残差研究 |
| 真实后背躯干语义几何 | `POSTERIOR_GEOMETRY_NOT_READY` | 现有宽松 ROI 未通过独立 QA，不能当后背真值 |
| DMD37 → MHR 桥接 | `BRIDGE_REVIEW_INCONCLUSIVE` | 两套候选存在约20–30 mm表面切向分歧，尚未选定 |
| 合成 DMD37 | `SYNTHETIC_DMD37_NOT_READY` | Atlas 未放行，不生成正式合成标签 |
| Mesh teacher / 工程伪标签 | `MESH_TEACHER_NOT_READY` | O/A/C/G尚无独立后背真值排名 |
| RTMPose DMD37 微调 | `NOT_READY` | 上游标签合同未通过 |

DMD37 Gate 的证据见 [Back → DMD37 Bridge / Posterior V2](handoffs/real-scene-2026-09-11/back-dmd37-bridge-posterior-v2/README.md)。

## 数据与运行位置

- 2026-09-14 已按用户指令删除本机 HuMMan 解压子集、7z 分卷和两个 Hugging Face 下载缓存。本机不再保有这些原始数据。
- 最新正式复现结果服务器目录：`/raid5/xuhd/sam3d_txyz_repro_v147_formal_20260914/results`。
- 服务器元数据归档：`/raid5/xuhd/sam3d_txyz_repro_v1412_metadata.tgz`，SHA256 `70e417de411cc34a363655ef3d379f9baeac9518af325be1afc829d63ff1756a`。
- Git 中保留实验报告、指标、必要可视化与审计元数据；授权权重、原始数据和大型运行数组不进入 Git。

服务器路径来自正式执行账本，本次知识收尾没有重新登录服务器验证文件仍在线，因此服务器在线状态记为 `pending`。

## 下一步

主实验下一步是在 V1.4.12 冻结复现链上恢复 post-Txyz residual failure audit，区分整体平移修正后剩余误差来自姿势、体型、局部表面、遮挡还是传感器几何。

DMD37 线路在训练前必须先完成 V3 correspondence adjudication：修正解剖行组和顺序定义，独立裁决高分歧的 `DIRECT_SMPL` 与 `HISTORICAL_SMPLX` 对应。Atlas 放行前不生成 DMD37 伪标签、不启动 RTMPose 微调。

## 尚未成立

- Cheap Txyz 不能修复错误姿势、局部曲面、人体与物体接触形变或遮挡。
- HuMMan/BEHAVE 结果不能证明治疗床、裸背、产品相机或机器人接触条件下的精度。
- 当前没有医生确认的 DMD37 医学真值，也没有临床有效性或机器人安全结论。
- Blender/SKEL/MHR 坐标尚不能直接作为机器人执行坐标。
