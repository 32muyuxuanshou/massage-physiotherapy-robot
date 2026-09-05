# CAMERA_VISIBILITY_DIVERSITY_V1 内部证据

状态：`PASS_WITH_RESTRICTIONS`

本目录验证前一门冻结的 17 个离散 Shape×Pose 与 4 个离散相机/遮挡条件的兼容性。E01–E20 是
非医学工程点；未修改正式插件、canonical SKEL、正式 Atlas、用户 Blend 或发布 ZIP。

## 结果

- 总处理：68 个样本-相机配对；最终兼容：54 个。
- `C1_MILD_OBLIQUE`：17/17；340 个点均为 `VISIBLE`。
- `C2_EDGE_CROP`：17/17；234 `VISIBLE`，106 `OUT_OF_FRAME`。
- `C3_EXTERNAL_OCCLUDER`：17/17；221 `VISIBLE`，119 `EXTERNAL_OCCLUDED`。
- `C4_SELF_OCCLUSION_STRESS`：仅 3/17 兼容；全矩阵合计 246 `VISIBLE`、85 `BACK_FACING`、
  9 `SELF_OCCLUDED`。14 个不兼容配对不得进入后续数据集。
- 54 个兼容配对的最大 Depth 误差 2.908945 mm，最大反投影误差 2.944394 mm。
- 全新进程复跑：资格、通用 QC、相机 QC、几何、Depth、Valid Mask、Skin Mask 均 68/68 一致；
  Eevee RGB 精确哈希 0/68 一致，不作为几何硬门禁。

## 重要限制

极端侧视相机是在诊断网格及首次 51 格矩阵之后校准的，当前 3 个兼容格只构成冻结的离散兼容映射，
不构成无偏留出验证，也不能外推到连续相机参数。前三类相机证明了受控斜视、裁切和外部遮挡标签，
不等于真实相机标定或真实人体泛化。

更早时间戳的失败目录保留用于审计：它们记录了相机命名守卫、schema 读取、Depth 阈值以及极端相机
兼容策略的修正过程；不得将其与本目录的最终结论混用。

## 下一门

审查本目录和兼容表后，才可据此设计 300–500 样本工程 Pilot。Pilot 必须先冻结抽样规则、拆分策略、
渲染质量门和失败处理；医生医学 Atlas、真实 RGB-D、医学传播和机器人安全均仍未开始验证。
