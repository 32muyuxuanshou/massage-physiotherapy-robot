# R3.1：诊断、文献驱动候选与匹配小规模实跑

2026-10-10。**本轮完成，候选正式多 seed 大训练暂不放行。** A 没有显示稳定几何优势；B 明显加强了公制 Depth 的使用，却没有改善真实 VAL 的整体误差。不能把合成改善升级成真实后背或穴位精度。

## 1. 实际做完什么

- 历史 R3 Cross 三 seed 的 fixed-mask Depth 诊断：seed11 的15条件，以及seed23/37的5条件确认；每条件合成400张、真实232帧，TEST 未读取。
- 同一232帧、同一冻结 Camera B 点集：Official、历史 RGB-only 三seed、历史 Cross 三seed，各增加历史 Cheap Txyz，共1624次修正和B评价。
- p001196全部8帧 + TRAIN尾部恶化最大的6帧：14份原始失败分析、RGB/Depth/mesh/B点云残差图、camera-only与预测mesh Kabsch诊断。
- 9篇原始论文下载与重点方法/图阅读；两个独立候选真实实现：A Geometry-Guided Cross-Attention；B MHR-Aware Geometry Refinement。
- 四组同预算 fresh pilot：100 TRAIN合成身份/800图，50 VAL身份/400图，seed11，8epochs，batch16，LR3e−4；各有best/last、400张合成原生输出及232帧真实输出。
- 四模型fixed-mask Depth干预、候选机制干预；额外4组预先定义的机制干预在全部232帧上用同一B点集评价，共928次真实推理。
- 16张六方法对照图（14预选失败+2普通VAL身份）、训练曲线、完整逐帧表及私有checkpoint/native输出备份。

所有网络输出仍是原生 MHR；没有自由顶点偏移、真实训练或封存 TEST 选择。训练Official参数前后hash未变。A/B零初始化最大顶点差低于2e−6m，有限梯度检查PASS。

## 2. 原有 Cross 到底在使用什么 Depth 信息

历史R3 seed11合成对应顶点误差：正确Depth **84.97mm**；只留Mask/rays **142.80mm**；去相对通道 **96.17mm**；去绝对通道 **138.07mm**；固定前景中位深度 **96.21mm**。其他两seed也出现正确Depth优于Mask/rays-only。

因此“只利用Mask”不成立；Depth数值确实有作用。但真实VAL将Z整体增加200mm，三seed的Mesh平均仅变化约 **1.5–2.4mm**，公制距离响应很弱。通道归零与RGB固定/Z偏移是诊断干预，不是自然物理相机变化，也不要求输出恰好平移200mm。

## 3. 强基线改变了判断

真实主指标为独立Camera B测量点到预测精确三角面的距离，按frame→sequence→subject等权聚合。表中med/P95是逐帧统计量的等权均值，不是全部点混合的中位数。

| 方法 | TRAIN med / P95 mm | VAL med / P95 mm | VAL ≤50mm覆盖 |
|---|---:|---:|---:|
| Official | 53.97 / 119.74 | 30.59 / 69.84 | 74.43% |
| Official + 历史Cheap Txyz | **24.65 / 80.32** | **11.23 / 41.60** | **97.07%** |
| RGB-only pilot | 44.89 / 108.65 | 21.31 / 54.51 | 88.67% |
| Cross pilot | 48.15 / 113.51 | 21.58 / 55.92 | 87.45% |
| Geometry A pilot | 48.66 / 114.86 | 21.40 / 54.54 | 86.91% |
| MHR B pilot | 34.68 / 94.90 | 24.35 / 60.46 | 84.26% |

Official+Txyz的232帧中有11帧触发历史177.888mm上限fallback，仍保留评价。TRAIN有173/192帧median改善、10帧P95恶化；VAL有39/40帧median改善、1帧P95恶化。它不是全样本完美，也不是骨骼/穴位真值证明。

历史R3 Cross三seed增加Txyz后VAL为14.32/13.09/12.99mm，均未超过Official+Txyz的11.23mm。**新模型仅胜过RGB起点，不足以证明胜过直接使用深度的便宜基线。**

## 4. 两个候选的事实结果

合成VAL对应顶点/去平移顶点/Camera误差分别为：

| 匹配模型 | 顶点camera mm | 去平移顶点 mm | Camera mm |
|---|---:|---:|---:|
| RGB-only | 97.69 | **63.24** | 75.86 |
| Cross | 108.88 | 67.25 | 85.86 |
| Geometry A | 107.49 | 65.76 | 86.32 |
| MHR B | **83.23** | 68.23 | **47.45** |

**A：**在此预算下真实VAL仅比Cross降低0.18mm，4个VAL身份中仅1个的median改善。删除3D bias后的合成误差107.10mm，甚至略好于完整107.49mm；真实VAL21.50 vs21.40mm，差异很小。删除global context也没有实质退化。没有证据把新增组件称为必要贡献。

**B：**合成顶点改善主要伴随Camera误差下降；去平移顶点不优于RGB-only。真实TRAIN相对Cross有14/18身份median改善，但VAL只有1/4，13/40帧改善、25/40帧P95恶化。因此存在开发分布/几何更新迁移问题，尚不证明是训练随机波动、哪项shape参数错误或最终模型上限。

B的Depth消融显示明确机制：同pose/camera跨身份错配后合成顶点 **355.69mm**；去局部对应 **135.53mm**；固定中位Z **105.95mm**；正确为83.23mm。真实VAL的+200mm干预使Camera平均变化88.35mm、Mesh变化84.57mm，明显强于原Cross/A。**有几何响应不等于有几何精度。**

## 5. Camera与形状增量的独立相机审计

以下是固定checkpoint推理干预，未重训、不根据B选择权重或调整阈值：

| B条件 | TRAIN med/P95 mm | VAL med/P95 mm |
|---|---:|---:|
| 完整B | **34.68 / 94.90** | 24.35 / 60.46 |
| 去局部对应 | 41.43 / 103.28 | 26.10 / 64.18 |
| 只应用Camera增量 | 36.83 / 95.35 | **23.24 / 58.01** |

局部对应对B的确有价值；但完整形状/姿态增量在TRAIN提供少量额外收益，在VAL反而变差。这支持下一阶段**分开公制Camera条件和人体局部几何**，不能直接把B的所有增量作为最终模块。

本轮B直接更新最终native参数，符合R3.1的候选范围；尚未接入官方Camera Head内部投影合同。用户新提交R4要求Camera参数/投影一致性，因此R4应另实现相机head条件分支，不能将B原样重命名成R4方案。

## 6. 失败归因与视觉核查

历史p001196第40帧：Official18.83/48.98mm，Cross43.25/105.90mm；Camera增量约 `[5.21,38.37,-95.79]mm`。仅将该Camera增量应用到Official就变为46.48/107.01mm；Cross预测mesh刚性对齐到Official后降至22.38/60.64mm。主要问题是整体位置漂移，仍有形状残差。不是标定真值误差的直接测量。

TRAIN p100072第48帧是俯身/支撑动作，腿的遮挡与姿态更难。Cross相对Official的去中心对应顶点变化约64.21mm；仅去刚性差异后P95仍221.60mm，高于Official141.49mm，因此不能归结为纯平移。shape/scale/pose参数均有变化，当前证据不能将因果唯一归到某项。

已查看放大对照图和固定0–150mm色标的B残差图。绿色/紫色都是预测Mesh，B热图颜色标记真实测量点到预测面的距离。衣物与遮挡可能影响观测；没有证实的Mask/物体污染不当作事实，更没有据此过滤难点。

## 7. 下一步裁决

1. 工程继续保留Official+Cheap Txyz为强基线；它目前胜过新候选，不称最终俯卧背部定位验收。
2. 不因一个seed的小规模结果宣布A方向不可能，也不为微小平均收益直接启动其正式多seed。
3. 保留B的“人体结构对应＋公制几何”研究线索，但将Camera与body更新分别验证；当前完整B不能晋升为最终模型。
4. 本轮诊断完成后转入用户已授权的独立R4任务：官方Camera Head接入、物理一致相机距离测试、局部几何attention、自审/短跑。R4通过自身门槛后才长跑，不能由本轮负结果直接跳过这些检查。

最终俯卧后背、医学穴位、裸露皮肤接触和机器人坐标尚未验收。当前HuMMan是真实开发证据，不是最终独立临床测试；Official预训练是否与HuMMan重叠未知。

## 审查入口

- [完整数字表](RESULT_TABLES.md) · [机器可读汇总](R31_SUMMARY.json)
- [合同](EXPERIMENT_CONTRACT.md) · [结构与实现](ARCHITECTURES.md) · [文献决策](LITERATURE_DECISIONS.md)
- [可视化索引](VISUAL_INDEX.md) · [复现实跑入口](REPRODUCE.md)
- 原始逐帧 JSON 在 `diagnostics/`、`pilots/`、`ablations/`、`real_mechanisms/`；私有大缓存与checkpoint见备份回执。
