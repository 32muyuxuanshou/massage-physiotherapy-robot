# Mesh → 解剖规则 → 穴位的整体流程 V2

## 一句话结论

我们的主流程应该是：

```text
真实 RGB/RGB-D
→ SAM3D Body Mesh
→ 后背区域与姿态质量检查
→ 体表/骨性标志 proxy 定位
→ 个体化 B-cun 坐标系
→ 穴位公式和表面投影
→ 规则结果
→ 可选学习型残差校正
→ 机器人坐标与安全检查
```

现在不应该直接训练一个“从图像预测穴位”的黑盒模型。

## 阶段 1：真实人体 Mesh

输入是真实场景 RGB 或 RGB-D。SAM3D 负责人体分割、姿态、形状和表面 Mesh。输出必须保留：

- `vertices`、`faces`、`cam_t`、姿态参数；
- 人体坐标系与相机标定；
- `POSTERIOR_TORSO_V1` mask；
- Mesh surface residual 和可见性质量。

Mesh 只回答“皮肤表面在哪里”，不能单独回答“C7、T3、T9、L2 或肩胛骨边界在哪里”。

## 阶段 2：解剖参考标志

对背部目标，优先建立：

- 后正中线；
- C7/肩颈交界 proxy；
- 肩胛骨内侧缘或其可见表面 proxy；
- 骨盆/髂嵴或 L2 高度 proxy；
- 左右侧和姿态方向。

这里要区分三种情况：

1. **直接可见标志**：从 RGB/RGB-D 或 Mesh 曲率/轮廓找到；
2. **骨性标志的皮肤 proxy**：用 MHR skeleton、肩部轮廓或姿态先验近似；
3. **不可观测标志**：只能估计，必须降低 confidence，不能标成 GT。

当前 MHR 没有真实骨骼和椎体 CT，因此 T3/T5/T9/L2 只能先通过 body-local spine interpolation 得到 proxy。这个 proxy 需要在后续数据中单独验证。

## 阶段 3：个体化 B-cun 坐标系

不要使用固定毫米偏移。根据实际标志计算 subject-specific scale，例如：

```text
scale_cun = measured_landmark_distance_mm / standard_cun_count
```

把每个目标点表示为：

```text
(vertebral level, lateral B-cun, local surface offset)
```

对背部，肩胛/脊柱参考距离可以作为比例坐标的候选，但必须与标准条文和数据中的实际标志定义绑定。B-cun 不等于 finger-cun，也不等于 canonical MHR 的某个固定 XYZ。

## 阶段 4：穴位公式与表面投影

先在 body-local 2D/3D 坐标中计算点，再投影到 Mesh 表面：

1. 由椎体水平和 lateral B-cun 得到局部目标；
2. 沿局部后背切平面/表面法向搜索；
3. 选择 `POSTERIOR_TORSO_V1` 内的 face；
4. 保存 face index、barycentric、surface normal 和坐标系；
5. 对每个点输出 confidence 与失败原因。

最终记录不是只有一个 XYZ，而是：

```text
point = {
  rule_coordinate,
  surface_xyz,
  face_index,
  barycentric,
  local_normal,
  confidence,
  visibility,
  provenance
}
```

## 阶段 5：学习模块的正确位置

只有规则基线建立后，才考虑学习模块。学习模块优先做三件事：

1. `landmark head`：识别 C7、肩胛、骨盆等参考标志；
2. `visibility/quality head`：判断标志是否被衣物、姿态或遮挡破坏；
3. `tangent residual head`：在规则点的局部切平面中预测小残差。

建议的最终形式是：

```text
p_final = SurfaceProject(p_rule + Δ_tangent)
```

并用结构约束限制：

```text
L = L_landmark + λ1 L_rule_residual + λ2 L_pairwise_cun + λ3 L_surface + λ4 L_visibility
```

不建议第一版直接回归 3D XYZ，也不建议在没有标注的情况下把虚拟穴位作为医学监督。

## 阶段 6：评价设计

必须至少比较三条路线：

| 方法 | 含义 |
|---|---|
| Rule-only | Mesh/landmark + B-cun/体表公式 |
| Direct predictor | 图像或 Mesh 直接回归穴位 |
| Hybrid | Rule-only 初始化 + landmark/残差校正 |

评价顺序：

```text
point → camera/frame → sequence → subject
```

主指标：

- 3D surface geodesic / point-to-surface error；
- 2D reprojection error；
- per-point 和 per-subject median/P95；
- landmark confidence 与定位误差的关系；
- occlusion、pose、body-shape 分层结果；
- left/right symmetry 和 B-cun pairwise consistency。

没有真人或临床标注时，只能做：

- synthetic deformation sanity；
- same-topology transfer QA；
- rule consistency；
- existing engineering mesh visualization。

不能把这些称为真实穴位准确率。

## 阶段 7：机器人输出

穴位表面坐标进入机器人前，还需要：

- 相机到机器人坐标变换；
- 表面法向和切向姿态；
- 运动学可达性；
- 与肩胛、脊柱、衣物和遮挡的碰撞检查；
- 对按摩接触的力/速度限制。

针刺深度、内部肌肉/骨骼安全距离不能由皮肤 Mesh 单独推断；需要额外的解剖成像或保守的临床规则，并且不属于当前工程闭环。

## 对当前仓库的修正

当前 `VIRTUAL_ACUPOINTS_ENGINEERING_V1.json` 的 8 个点降级为：

```text
ATLAS_SEED_ONLY_RULE_COMPUTATION_PENDING
```

它们可以用于：

- canonical 可视化；
- 同拓扑传播代码测试；
- 规则引擎的输入模板。

它们不能用于：

- 声称真人穴位真值；
- 直接监督模型训练；
- 临床或安全结论。

