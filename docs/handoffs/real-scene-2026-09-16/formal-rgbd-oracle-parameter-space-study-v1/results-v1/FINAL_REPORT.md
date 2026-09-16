# FORMAL RGB-D ORACLE PARAMETER-SPACE STUDY V1

## 最终裁决

**STRUCTURED_PARAMETER_SPACE: STRONG_GO**

在固定 Official SAM 3D Body 初始化和已冻结 O1 Cheap Txyz 后，单视角 K0 RGB-D 确实包含可用于 **Pose 参数修正** 的额外几何信息，并能推广到完全未参与优化的 K1/K2/K3。最强组是 **O2（Translation + Pose）**。这证明的是 parameter-space utility，不证明传感器残差可被唯一分解为 Translation/Pose/Shape。

Shape-only（O3）没有通过主指标。联合组 O4 通过 STRONG_GO，但整体弱于 O2，说明当前 Shape 自由度没有在 Pose 之外提供可靠增益。

## 正式范围与防泄漏

- 数据：与 Cheap Txyz V2.3 相同的 45 formal frames、5 fresh subjects、15 sequences。
- Stage A：只读取 K0 RGB-D、person mask、相机标定、Official MHR 参数与 O1 translation；完成 45×3 次 O2/O3/O4 优化后冻结资产和 SHA256。
- Stage B：Stage A manifest 完成后才读取 K1/K2/K3。
- 评价：dataset-mask-assisted RGB-D；主指标为 observed person points → predicted mesh triangles 的精确 surface distance。
- aligned：严格复用历史项目定义，即 nearest-vertex XYZ-only 对齐、最多 8 轮、单轴步长 ±0.1 m、收敛阈值 1e-5；对齐后仍用 exact point→triangle 评价。
- K0 只作诊断，不进入 GO/NO-GO 主结论。
- Regional metrics：`NOT_YET_AVAILABLE`。项目没有冻结的 canonical MHR anatomical partition，因此没有事后挑选背部区域。

## 总体 held-out 结果

subject-aware 聚合顺序为 K1/K2/K3 → frame → subject，最终取 5 个 subject median。

| Method | Median ↓ | vs O1 | P90 ↓ | P95 ↓ | ≤50 mm ↑ | Aligned median ↓ | Aligned vs O1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| O0 Official | 30.11 mm | — | 72.68 | 94.03 | 77.72% | 17.36 | — |
| O1 T only | 18.61 mm | baseline | 54.03 | 82.44 | 88.02% | 16.46 | baseline |
| O2 T+Pose | **16.63 mm** | **−10.62%, −1.98 mm** | 54.57 | 70.31 | 87.90% | 15.17 | **−7.84%** |
| O3 T+Shape | 18.85 mm | +1.29%, +0.24 mm | 60.84 | 80.12 | 84.70% | 16.11 | −2.10% |
| O4 T+Pose+Shape | 17.14 mm | **−7.92%, −1.47 mm** | 55.10 | **69.75** | 87.12% | **15.14** | **−8.04%** |

O2 相比 O4 的 median 还低 0.50 mm（约 2.93%），所以“更多自由度”没有带来更强的整体主指标。O4 的 P95 略优，说明联合参数可能改善部分尾部误差，但不足以证明 Shape 的稳定贡献。

## 一致性与过拟合

| Method | Subjects improved | Sequences improved | Frames improved | K1 frames | K2 frames | K3 frames |
|---|---:|---:|---:|---:|---:|---:|
| O2 | **5/5** | **13/15** | **35/45** | 38/45 | 34/45 | 35/45 |
| O3 | 3/5 | 10/15 | 29/45 | 28/45 | 27/45 | 27/45 |
| O4 | **5/5** | **12/15** | **34/45** | 36/45 | 34/45 | 35/45 |

K0 改善而 held-out 恶化的帧数：O2 8/45、O3 17/45、O4 8/45；其中同时满足 K0 改善超过 2 mm 且 held-out 恶化超过 2 mm 的强过拟合帧分别为 4、1、4。可见 partial-observation overfitting 真实存在，但没有推翻 O2/O4 的跨人物总体收益。

最明显受益的序列集中在 backpack_back 与部分 yogaball：O2 的最大 sequence median 改善包括 Sub03 backpack_back −3.79 mm、Sub04 yogaball_play −3.61 mm、Sub05 yogaball −3.18 mm、Sub06 backpack_back −3.04 mm。最明显恶化是 Sub07 stool_sit：O2 +3.71 mm、O4 +3.68 mm，O3 更达到 +8.92 mm。

## Stage A 参数变化与数值健康

45/45 帧的 O2、O3、O4 均完成；三组均为 45/45 K0 objective 下降，0 个 numerical failure。

| Method | Median ΔT | Pose coefficient L2 | Shape/scale coefficient L2 | Median vertex displacement | K0 sensor-loss reduction |
|---|---:|---:|---:|---:|---:|
| O2 | 17.85 mm | 0.1326 | 0 | 25.09 mm | 32.45% |
| O3 | 12.22 mm | 0 | 0.2803 | 12.26 mm | 12.01% |
| O4 | 18.04 mm | 0.1314 | 0.2255 | 24.23 mm | 34.11% |

这些量级没有出现数值爆炸，但“人体合理”只能作有限判断：当前 MHR 的 `body_pose` 是 133 维模型参数，不是公开的逐关节 axis-angle 表，因此不能诚实地把 coefficient delta 冒充逐关节 geodesic rotation。正式资产保留了初始/最终参数与 mesh，可在获得官方参数到解剖关节旋转的映射后补算。当前结论依赖 held-out surface geometry，而不依赖该缺失的解释性指标。

## 14 个必须回答的问题

1. **O2 是否稳定优于 O1？** 是。median −10.62%，aligned −7.84%，5/5 subjects、13/15 sequences、35/45 frames 改善。
2. **O3 是否稳定优于 O1？** 否。主 median 恶化 1.29%，仅 3/5 subjects 改善；aligned 虽改善 2.10%，不足以建立 Shape-only 价值。
3. **O4 是否稳定优于 O1？** 是。median −7.92%，aligned −8.04%，5/5 subjects、12/15 sequences 改善。
4. **哪个参数空间贡献最大？** Pose。O2 是最低主 median；O4 未超过 O2，O3 未通过。
5. **aligned 中是否仍存在改善？** O2/O4 明确存在，分别 7.84%/8.04%，所以收益不是再次微调 translation 所能解释完的。
6. **是否跨 subject 一致？** O2/O4 的绝对主指标为 5/5；O3 为 3/5。部分 subject 的 aligned 方向仍不一致，应保留为限制。
7. **是否跨 sequence 一致？** O2 为 13/15，O4 为 12/15；并非由少量序列单独驱动。
8. **是否明显 K0 overfitting？** 存在局部过拟合，O2/O4 各 8/45 帧；但整体 held-out 仍显著改善，因此不是全局性失败。
9. **哪些姿势最受益？** backpack_back 最稳定，部分 yogaball 也明显获益。
10. **哪些最易恶化？** Sub07 stool_sit 是最清楚的失败簇，应作为下一阶段的重点反例。
11. **correction magnitude 是否人体合理？** 无数值爆炸，median vertex displacement 约 12–25 mm；但缺少 MHR 逐关节旋转映射，不能完成临床意义上的姿态合理性证明。
12. **是否支持 Body-Model-Aware Residual Factorization？** 支持继续研究“body-model-aware pose correction”，但不支持宣称唯一残差分解，也不支持先建设完整大网络。
13. **Partial-Observation-Aware Refinement 是否应成为主要问题？** 是。held-out 总体提升与 8/45 过拟合帧同时存在，说明如何约束单视角可见表面对全身参数的影响是核心方法问题。
14. **是否已有证据需要 O5 Local Surface Correction？** 没有。尚未建立冻结的区域残差和跨 subject 局部结构证据；本轮明确不实施 O5。

## 下一步研究裁决

建议推进一个最小的 learned/refined **Pose correction** 方向，核心围绕 partial-observation-aware constraints、可见性与不确定性；Shape 分支暂不作为主线。下一步先复现 O2 的收益边界和 Sub07 stool_sit 失败机制，再决定网络结构。当前数据不支持 local vertex deformation、O5 或大规模 T/P/S 全分支系统。

## 完整交付

- `stage_a/STAGE_A_MANIFEST.json`：45帧 × O2/O3/O4 冻结资产路径、hash、loss、参数变化和运行状态。
- `stage_b/`：900条 frame-camera-method 原始指标及 frame/sequence/subject/overall 聚合。
- `failure_audit/`：top 10 改善、恶化、K0 overfit，含 K0–K3 delta、aligned delta 与参数变化。
- `report/visualizations/`：63 张 PNG，覆盖改善、恶化和过拟合案例的 K0–K3 overlay 与 front/side/top geometry。
- `audit/MHR_ORACLE_AUDIT.json`：MHR 参数组、重建误差和梯度审计。
- `hashes/SHA256SUMS.json` 与 `EXECUTION_LEDGER.json`：执行和文件完整性审计。
