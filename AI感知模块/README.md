# AI 感知模块

本模块建立按摩理疗机器人的人体表面穴位先验与视觉定位链路。医生在冻结的 SKEL 皮肤上标注 Atlas，
内部工程使用 SKEL shape/pose 与虚拟相机生成 RGB-D 数据并训练二维关键点定位器。SMPL-X 是独立研究
工具，不与 SKEL 叠加。

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

## 当前工程进度（2026-09-03）

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

当前冻结的主要实验事实：

- 17 个离散 Shape×Pose 组合通过固定俯卧场景门；Camera 兼容表冻结 54 个离散组合。
- 主工程 Pilot 为 360 张 RGB-D，另有 12 张 C4 极端侧视 challenge；E01–E20 均为非医学工程点。
- 边界混合解码器解决了 TinyHeatmapNet 在裁切边缘的大部分结构性偏差，但只授权合成工程评估。
- 24 个新 Shape–Pose 人体、168 张 RGB-D 完成可靠性数据门；Tiny 的可靠性/拒答仅证明合成可行。
- RTMPose-S（无预训练，RGB 160×128，80 epochs，seed 20260831）经过对称边界取景增强后完成三种
  Holdout。三条测试共 4,102 个可见点实例，所有 `>20 px` 错误降为 0。
- RTMPose-S 已使用同一批 24 个新人体重新训练自己的 availability 与 BAD15 拒答模型；三条定位器在
  6 个未触碰人体、42 张图上全部通过预冻结门，接受点中的 `>30 mm` 错误均为 0。

RTMPose-S 当前测试结果（误差为原始 1280×1024 连续图像坐标）：

| Holdout | Mean | P95 | Max |
|---|---:|---:|---:|
| Combination | 1.837 px | 3.937 px | 7.493 px |
| Shape | 2.200 px | 4.462 px | 6.841 px |
| Pose | 1.830 px | 4.112 px | 5.250 px |

相较 Tiny Boundary Hybrid，RTMPose-S 三条合并的可见点加权平均误差从 2.207 px 降至 1.995 px，
Combination 与 Pose 明显改善；Shape 的 P95/Max 改善，但 Mean 退化 13.1%。因此当前状态是：

`PASS_SYNTHETIC_CANDIDATE_WITH_SHAPE_MEAN_REGRESSION`

它可以作为下一合成阶段的定位器候选，但不是生产模型，也不能直接复用 Tiny 的可靠性模型和阈值。

## 当前唯一主任务

下一主任务是 `REAL_RGBD_DOMAIN_GATE_V1`：确定真实 RGB-D 相机型号、分辨率、内参、畸变、深度尺度
和噪声特征，采集少量真实俯卧样本，量化合成域到真实域的差距。在真实域门完成前，不因追求“更新模型”
继续扩大网络搜索；当前 RTMPose-S 可靠性结果只冻结为合成工程候选。

当前权威证据：

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
- 尚未验证真实人体、真实 RGB-D 噪声和照片域泛化。
- Blender/SKEL 坐标尚不能直接作为机器人执行坐标。
- 床垫形变、软组织接触、接触法向、安全偏移、力/速度限制与急停链路尚未建立。

因此，现阶段结果只能用于合成工程研究，不能宣称临床可用或机器人安全。
