# AI 感知模块

> **网页端最新交付（2026-09-09）：** [完整实验、批量mesh对照与当前训练状态](../docs/handoffs/real-scene-2026-09-09/README.md)。内含更正后的验证指标，请以此入口替代旧交付状态。
> **最新执行（2026-09-09）：** [69图82人体批量mesh对照](outputs/内部工程证据/2026-09-09_BATCH_MESH/README.md)完成。发现并修正两图三个人体的COCO标注对应，原模型/第2轮/第10轮NME更正为0.035207/0.035243/0.035442，未见主指标提升。全427记录已做对应审查；9条训练记录暂不使用新增人工loss。修正后的可见人工关节监督对照V2已启动10轮，尚无结果，Atlas和原模型未替换。

> **2026-09-08：微调/训练策略主线已获用户授权恢复。** 已完成20图官方MHR对照和回归头单步更新检查；还没有训练有效性结论或新正式checkpoint。统一从[当前状态与暂停/恢复记录](../docs/ai-workflow-pause-2026-09-08.md)恢复上下文。

官方SAM预训练推理、真实照片mesh叠加及项目37点传播已跑通。只贴mesh无需训练；没有完整复现论文训练与基准评测。当前计算服务器为172.18.18.151，COCO首批1,280张图片与原始人体标注已就绪；另行授权下载的官方COCO MHR标注24/24分片已验证，现有图库匹配641张图片、1,110条人体标注。其它SAM数据来源未下载。网络训练、穴位精度和标签放行状态以当前状态记录为准。

本模块包含正式SKEL标注工具、历史合成工程验证和独立的真实图像/MHR研究；正式Atlas与用户Blend保持保护。近期实验、服务器路径、数据清单和未完成事项均索引在暂停记录中，历史逐轮说明保留于内部实验目录。

## 医生标注软件

当前 Windows 一体化交付：

- 文件：`发布/医生穴位标注工作台_v2.3.0_正式完整版.zip`
- 大小：1,898,920,329 bytes
- SHA-256：`4CC3EB0425D65D9C81DD674B76D66D9785F7A3A4B4FDBDE9E2D16A23F51DCE99`
- 内含 Blender 4.5.12 LTS、便携 Python/SKEL 环境、插件及内部许可模型，无需另装运行环境。
- 仅适用于 Windows；模型和衍生包受原许可约束，不得外发给未获许可者。

使用方式：完整解压后运行 `开始使用_SKEL躯干与四肢标注.cmd`。`打开_SMPL-X独立研究工具.cmd`
只用于独立 SMPL-X 研究。只有在插件中主动执行“保存本次标注”才会提交 `.blend` 和正式 Atlas JSON；
未保存修改不会进入正式记录。

## 源码与工具入口

- 医生标注插件：`标注工具/blender_addons/smpl_acupoint_annotator/`
- SKEL 控制插件：`标注工具/blender_addons/skel_blender_controls/`
- RGB-D/投影/可见性核心：`标注工具/blender_addons/modules/training_export_core/`
- 内部 Blender MCP：`标注工具/blender_mcp/`
- 实验工作流：`标注工具/blender_mcp/workstreams/`
- 权威实验证据：`outputs/内部工程证据/`

源码是真相；`构建缓存/`、发布工作树的运行时副本和 ZIP 均为生成物。

## 历史合成工程进度（截至2026-09-03）

已经完成的工程闭环：

```text
SKEL face+barycentric Atlas
→ shape / pose 传播
→ 多相机可见性
→ RGB + camera-Z Depth + Valid/Skin Mask
→ 2D 关键点训练
→ Depth 反投影 3D
→ 合成可靠性/拒答可行性
```

该阶段冻结的主要实验事实：

- 17 个离散 Shape×Pose 组合通过固定俯卧场景门；Camera 兼容表冻结 54 个离散组合。
- 主工程 Pilot 为 360 张 RGB-D，另有 12 张 C4 极端侧视 challenge；E01–E20 均为非医学工程点。
- 边界混合解码器解决了 TinyHeatmapNet 在裁切边缘的大部分结构性偏差，但只授权合成工程评估。
- 24 个新 Shape–Pose 人体、168 张 RGB-D 完成可靠性数据门；Tiny 的可靠性/拒答仅证明合成可行。
- RTMPose-S（无预训练，RGB 160×128，80 epochs，seed 20260831）经过对称边界取景增强后完成三种
  Holdout。三条测试共 4,102 个可见点实例，所有 `>20 px` 错误降为 0。
- RTMPose-S 已使用同一批 24 个新人体重新训练自己的 availability 与 BAD15 拒答模型；三条定位器在
  6 个未触碰人体、42 张图上全部通过预冻结门，接受点中的 `>30 mm` 错误均为 0。

该阶段 RTMPose-S 测试结果（误差为原始 1280×1024 连续图像坐标）：

| Holdout | Mean | P95 | Max |
|---|---:|---:|---:|
| Combination | 1.837 px | 3.937 px | 7.493 px |
| Shape | 2.200 px | 4.462 px | 6.841 px |
| Pose | 1.830 px | 4.112 px | 5.250 px |

相较 Tiny Boundary Hybrid，RTMPose-S 三条合并的可见点加权平均误差从 2.207 px 降至 1.995 px，
Combination 与 Pose 明显改善；Shape 的 P95/Max 改善，但 Mean 退化 13.1%。该阶段记录的状态是：

`PASS_SYNTHETIC_CANDIDATE_WITH_SHAPE_MEAN_REGRESSION`

它可以作为下一合成阶段的定位器候选，但不是生产模型，也不能直接复用 Tiny 的可靠性模型和阈值。

## 真实场景研究：已暂停

当前状态与恢复原则统一见[暂停记录](../docs/ai-workflow-pause-2026-09-08.md)。只有贴mesh时直接使用官方预训练推理，无需先训练或准备训练数据集。模型局部几何修正、穴位传播、网络训练是不同工作，不自动捆绑执行。

2026-09-06的[研究资料](研究资料/真实场景关键点定位_2026-09-06/README.md)及[网页端交接](../docs/real-scene-research-2026-09-06.md)保留为历史版本，不代表暂停时的最新进度。长期精度/论文路线尚未完成，也未永久取消。

历史合成阶段证据：


- RTMPose 首轮容量比较：
  `outputs/内部工程证据/2026-09-02_17-58-03_LOCATOR_CAPACITY_COMPARISON_V1/`
- 边界修正与三 Holdout：
  `outputs/内部工程证据/2026-09-02_19-48-21_RTMPOSE_SHIFT_AND_THREE_HOLDOUT_V1/`
- 合成可靠性数据门：
  `outputs/内部工程证据/2026-09-02_14-58-10_RELIABILITY_DATASET_GATE_V1/`
- RTMPose-S 可靠性与拒答：
  `outputs/内部工程证据/2026-09-03_12-03-27_RTMPOSE_RELIABILITY_V1/`

更早的阶段结果仍保留在 `outputs/内部工程证据/`，作为历史证据，不再复制到本 README。

## 尚未成立

- E01–E20 不是医生确认的医学穴位，正式医学 Atlas 尚未完成。
- 已有真实RGB推理和局部开发实验；尚未建立独立真人定位精度、真实RGB-D及照片域泛化结论。
- Blender/SKEL 坐标尚不能直接作为机器人执行坐标。
- 床垫形变、软组织接触、接触法向、安全偏移、力/速度限制与急停链路尚未建立。

现有合成与真实图像结果均属于工程研究，不能宣称临床可用或机器人安全。
