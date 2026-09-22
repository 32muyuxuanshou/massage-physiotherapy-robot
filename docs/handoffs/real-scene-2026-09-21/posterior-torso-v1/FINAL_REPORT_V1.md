# POSTERIOR_TORSO_V1 工程闭环报告

## 结论

本阶段完成了一个可复现的后背 Mesh 与穴位拓扑工程闭环：冻结 MHR LOD1 后背评价区域，生成 8 个 provisional canonical 点，并将这些点传播到 5 个已有真实工程预测 Mesh（B1–B5）。

这证明了 **同一 MHR 拓扑上的点传播链路可用**，但没有证明穴位位置的临床准确性，也没有进行新的模型训练。

## 已验证事实

| 项目 | 结果 |
|---|---:|
| MHR vertices / faces | 18,439 / 36,874 |
| 后背 mask faces / vertices | 2,152 / 1,196 |
| 最大连通分量 | 99.91% |
| 后背法向 z 均值 / 中位数 | -0.708 / -0.833 |
| 虚拟工程点 | 8 |
| 预测 Mesh 样本 | B1–B5，共 5 个 |
| 预测拓扑检查 | 5/5 PASS |
| canonical identity transfer | 0 mm 最大误差 |
| synthetic rigid transfer | 0 mm 最大误差 |

## 穴位标签

点集合为 BL13 左右、BL15 左右、BL18 左右、GV14、GV4。点的位置用 WHO 的椎体水平和后正中线/旁开规则作为初始化依据，再投影到 canonical MHR 后背表面。每个点保存 face index 和 barycentric coordinate。

所有点都带有：

```text
virtual_engineering_label = true
medical_truth = false
review_status = PROVISIONAL_NO_CLINICIAN_VALIDATION
```

## 传播结果

每个 B1–B5 样本均保存：

- `PROPAGATED_POINTS.json`
- `virtual_acupoints.ply`

传播使用冻结 face+barycentric 对应，不使用最近邻重新猜点。5 个样本的 `faces` 与冻结 MHR faces 逐元素一致。

## 可视化

- canonical 后背 mask：`candidate_posterior_preview.png`
- canonical mask + 8 个点：`posterior_acupoint_overlay.png`
- B1–B5 传播 montage：`prediction_acupoint_montage.png`

## 不应过度解释的地方

1. canonical MHR 的工程投影不是医生标注；
2. 同拓扑传播误差为 0，只说明实现正确，不说明跨人解剖对应正确；
3. B1–B5 的点坐标处于各自预测 Mesh 的坐标系，尚未与真人表面标注计算医学误差；
4. 后背 mask 的肩部边界仍属于工程冻结，可在后续数据 QA 中修订；
5. 当前结果不足以支持治疗、诊断或临床安全声明。

## 下一阶段决策门

现在有两个合理方向：

- **工程方向**：把 `POSTERIOR_TORSO_V1` 接入现有 Mesh residual 评价，比较后背区域而不是 whole-body 平均；
- **研究方向**：使用这 8 个点作为 topology-aware auxiliary target，设计穴位 head 或表面坐标损失，并在独立数据上验证泛化。

在没有真人标注时，第二条只能作为工程研究假设，不能写成医学验证结论。

