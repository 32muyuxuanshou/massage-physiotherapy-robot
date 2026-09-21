# Mesh 逐帧误差审计 V1

## Material Passport

- 日期：2026-09-20；模式：validate；Verification Status: **ANALYZED**。
- 范围：已有 3 人、9 sequences、18 timestamps × 3 输入；没有运行新 SAM、优化或训练。
- 主证据：K1/K2/K3 sensor points → predicted mesh surface。Supporting：BEHAVE fitted SMPL，不能当绝对 GT。
- 来源：`SOURCE_SHA256.json`，含 3 份 attribution、54 份 formal raw JSON、3 份 formal report、36 张叠图。
- 输出：全量 `ERROR_AUDIT.json`、修正 `ATTRIBUTION_AGGREGATED.json`、`formal-recomputed/`、[54 行逐帧索引](FRAME_INDEX.md)、[18 帧视觉复核](VISUAL_REVIEW.md)。

## 先纠正两个交付问题

1. 旧 attribution aggregator 跳过 sequence，直接做 frame→subject。现在恢复全部层级的 median：**camera→frame→sequence→subject→总体**。即使每条 sequence 都有两帧，先取 sequence median 与直接取六帧 median 也不等价。旧 `ATTRIBUTION_ANALYSIS_V1.md` 不再作为结论依据。
2. 旧 `FINAL_REPORT_V3.md` 的 FULL T+Pose=13.27 与当前交付 raw/report JSON 重算的 13.72 不一致；UPPER 对应 13.93→14.06。54 份 raw 与三份 report 中同一条记录完全相等，因此当前可复算数字应以 `formal-recomputed/` 为准。旧总结表产生差异的历史过程尚未确认，本轮不猜测原因。

旧文件保留，并加 superseded 提示。本轮不改变原始输出、样本或算法。

## 完整数值

下面是 **attribution rerun** 按正确层级重算的 held-out sensor median，单位 mm；各方法优化均从 Txyz 初始化。

| 输入 | Official | Txyz | T only | T+global rot | T+body pose | T+Pose |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 30.77 | 16.53 | 14.84 | 14.34 | 13.54 | 13.27 |
| UPPER | 35.21 | 16.52 | 17.06 | 16.36 | 14.57 | 14.07 |
| LOCAL_TORSO | 35.49 | 21.76 | 22.71 | 23.42 | 21.58 | 21.66 |

与之独立的 **formal V3 原始输出重算** 是：

| 输入 | Official | Txyz | T+Pose |
|---|---:|---:|---:|
| FULL | 30.77 | 16.53 | 13.72 |
| UPPER | 35.21 | 16.52 | 14.06 |
| LOCAL_TORSO | 35.49 | 21.76 | 21.66 |

两次执行不能混成同一次。逐帧 camera-median 指标的跨运行最大绝对差：Official 0.00040 mm、Txyz 0.00297 mm、T+Pose 0.907 mm 以内。36 张现有叠图对应 formal V3，不是 attribution rerun 的独立分支；后者没有保存分支 vertices。

## 逐帧改善与恶化

计数是严格正负号描述，不代表统计显著，也没有为结果新设通过阈值。

| 输入 | Txyz 优于 Official | T+Pose 优于 Txyz | T+Pose 劣于 Txyz | 联合优化逐帧增益中位数 | 最差逐帧增益 |
|---|---:|---:|---:|---:|---:|
| FULL | 17/18 | 14/18 | 4/18 | +2.79 mm | −4.18 mm |
| UPPER | 16/18 | 15/18 | 3/18 | +1.50 mm | −2.28 mm |
| LOCAL_TORSO | 15/18 | 11/18 | 7/18 | +2.49 mm | −18.92 mm |

54 条件行全部未触发 Txyz fallback。整体嵌套中位数之差与逐帧配对差的中位数是不同统计量，不能相互替代。

LOCAL_TORSO 的联合优化相对 Txyz：Sub03 为 56.35→29.61，Sub04 为 21.76→14.08，Sub05 为 21.31→21.66 mm。因此 **不是所有人都无收益，也不是所有人都稳定受益**。尤其 Sub03 的 T-only 已到 30.50 mm，联合优化的大部分改善不能全算成 Pose gain。

最差案例为 `Sub04/Date03_Sub04_stool_sit/t0015.000`：LOCAL Official=69.09、Txyz=71.94、T-only=90.57、T+Pose=90.86 mm；联合优化额外平移约 63.84 mm。T-only 已明显恶化，说明该案例不能简单归咎于“加了姿态自由度”。

UPPER 的 body branch 相对 T-only 有 13/18 帧改善；LOCAL 为 11/18，配对改善中位数只有 0.44 mm。分支之间同时重新优化 translation，不能视为严格的纯姿态因果分解。

## 过拟合迹象与长尾

formal V3 中 K0 全人体 median 变好、held-out median 变差：FULL 4/18、UPPER 3/18、LOCAL 5/18。优化目标下降而 held-out 变差：4/18、3/18、7/18。这是与 partial-observation overfit 一致的迹象，并非每个失败都已确定根因。

这里有重要测量边界：现有 K0 evaluation 使用**全 person-mask 点**；优化才是 ROI-only 点。它不是 crop-only K0 accuracy。优化 loss 还包含 trimming 和 prior，也不是独立几何指标。不能把这两者混称为“可见躯干已经对齐”。

attribution 的 T+Pose 单 camera P95 最大值：FULL 437.36、UPPER 553.99、LOCAL 591.10 mm。P95 超过 100 mm 的 camera 行分别是 6/54、17/54、33/54；100 mm 只作为本轮事后描述切点，不是新 Gate。全量 P95 已保存。

**中位数约 20 mm 不代表全身每个区域都约 20 mm。** 长尾可能涉及肢体补全、物体/衣物、mask、深度噪声等；现有摘要没有残差对应点坐标，不能直接将高 P95 标成“深度异常”或“背部误差”。单向 observed→mesh 距离也不完全惩罚多余/幻觉表面。

## 对训练的判断

按 formal V3，LOCAL 相比 FULL 在校正后的 held-out 指标上三个人都更差；fitted SMPL 对校正后方向也一致，说明局部输入下仍有问题值得研究。

但 Official 并非 3/3 同方向：Sub05 的 LOCAL 30.49 比 FULL 46.33 mm 更好。fitted reference 的 Official 也并非全部同方向。此前要求的“Official/Txyz/T+Pose 全都稳定更差 + 跨人一致 + reference 支持”没有全部满足。因此本轮**不宣布 TARGETED_ADAPTATION_JUSTIFIED，不直接启动训练**。

工程上保留 Txyz 基线；T+Pose 在局部输入下不能无条件当可靠提升。下一步优先从已保存 formal vertices 重算全量 54 条件的逐点残差与区域归属，补 crop-only K0、K1/K2/K3 残差空间位置，并同时报告 median/P95/coverage。先分清“背部错”与“手脚补全错”，再决定可见区域拟合、不可见部位补全或训练策略。此项无需重新跑 SAM，也不需要立即扩充新人物。

目前误差属于人体 surface 对齐误差，**不是 DMD37 穴位误差，也不是医生定位准确度**。有衣物且缺少临床点真值，不能据此承诺毫米级穴位定位。

## 统计解释检查（11/11）

| 检查 | 本轮处理 |
|---|---|
| Simpson / 聚合掩盖异质性 | 恢复 sequence 层，明确三人不同趋势 |
| Ecological fallacy | 不从三人总体推断每帧都改善 |
| Berkson / 选择偏差 | 冻结 feasibility 样本，不能外推自然人群 |
| Collider bias | 未新增结果依赖筛选或控制变量 |
| Base-rate neglect | 非临床筛查，未声称灵敏度/阳性预测值 |
| Regression to mean | 全量配对比较，最坏案例仅作诊断展示 |
| Survivorship | 54/54，失败/恶化行未丢弃 |
| Look-elsewhere | 六方法三条件全量报告，无显著性筛选 |
| Forking paths | 本轮事后审计明确标注，原算法不改 |
| Correlation / causation | 分支差异不等于纯解剖原因 |
| Reverse causality | 不根据高残差推定噪声来源或临床机制 |

只有三个人且每序列相邻帧相关，不将 54 行当 54 独立受试者；本轮未计算或宣称统计显著、泛化成功或临床有效。

## 复算

从仓库根运行（仅 CPU 读取 JSON；aggregator 需要 numpy）：

```powershell
python docs/handoffs/real-scene-2026-09-20/code/aggregate_attribution_v1.py --root docs/handoffs/real-scene-2026-09-20/attribution_v1 --out docs/handoffs/real-scene-2026-09-20/error-audit-v1
python docs/handoffs/real-scene-2026-09-20/code/build_error_audit_v1.py
python docs/handoffs/real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/code/aggregate_formal_v3.py --shards docs/handoffs/real-scene-2026-09-20/formal-back-local-model-evaluation-continuation-v1/formal_eval_v3_complete --out docs/handoffs/real-scene-2026-09-20/error-audit-v1/formal-recomputed
```
