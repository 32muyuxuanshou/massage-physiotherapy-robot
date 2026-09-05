# CROSS_GATE_RECONCILIATION_V1

本工作流统一旧 A/B 单轴资格与 Shape×Pose Cross 门禁，并将精确 face-pair 差分升级为可审计的三角形
窄相位与空间重叠簇分析。

## 现役结论

- 15 个 control 用同一 cluster gate 完成复核：baseline + 3 个非 baseline Shape、baseline + 6 个
  非 baseline Pose 获得 Cross-qualified；其余 5 个保持 CAUTION。
- 仅由合格父项组成的 3×6=18 格受限搜索完成：17 格 Cross-qualified，1 格因既有簇 crossing-depth
  代理增加约 1.173 mm 保持 CAUTION；15 个留出格中 14 格通过。
- 18/18 几何结果在全新原生 SKEL/Blender 进程中一致。
- 17 个合格格的固定相机 RGB-D 和第二次全新进程重放均 17/17 通过；Depth、Valid Mask、Skin Mask
  精确一致，最大 Depth/反投影误差分别为 1.269/1.295 mm。
- Eevee RGB 精确哈希不是硬门禁；本阶段不涉及相机多样性、医学真值或连续参数空间。

完整证据：
`outputs/内部工程证据/2026-08-31_17-27-40_CROSS_GATE_RECONCILIATION_V1/`。

## 方法与边界

- BVH 原始 face-pair 证据始终保留，不被聚类覆盖。
- 窄相位区分非共面相交线、共面面积、点接触和未确认候选。
- cluster 半径为 25 mm；新簇、严重度升级、床面间隙和 E01–E20 二环分别治理。
- crossing depth、segment length 都只是几何代理，不是物理穿透或软组织接触深度。
- baseline 本身有 293 对窄相位确认相交、归为 6 个历史簇；Cross-qualified 不等于全身零自交。
- 不修改正式插件、Atlas、canonical Blend、用户 Blend 或发布包。

## 入口

`run_cross_gate_reconciliation.py` 依次支持 control、benchmark、几何确定性、受限搜索、固定相机 RGB-D
及其确定性重放；最终资格和复核结果必须读取 evidence root 下的 `verification*.json`，不能仅凭中间
progress 或某个 case 的 PASS 推断整个阶段通过。
