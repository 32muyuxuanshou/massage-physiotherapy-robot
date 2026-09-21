# 工程部位可见性关联审计

本表把每个工程部位的深度点按 K0 投影分为 ROI 内外，并与严格三角面残差关联。`roi_fraction` 是该部位采样点落在输入 ROI 内的比例；它不是人体真实可见面积。

| 条件 | 部位 | ROI fraction | Official | Txyz | T+Pose |
|---|---|---:|---:|---:|---:|
| FULL | torso | 0.999 | 32.16 | 13.65 | 15.16 |
| FULL | arms | 0.987 | 33.22 | 14.05 | 12.23 |
| FULL | legs | 0.999 | 32.12 | 13.55 | 11.47 |
| FULL | head | 0.986 | 32.33 | 18.86 | 13.46 |
| FULL | hands_feet | 0.976 | 50.51 | 31.84 | 31.27 |
| UPPER | torso | 0.983 | 24.24 | 13.68 | 12.89 |
| UPPER | arms | 0.979 | 21.87 | 15.04 | 12.64 |
| UPPER | legs | 0.716 | 21.43 | 18.53 | 15.00 |
| UPPER | head | 0.973 | 25.57 | 16.22 | 9.09 |
| UPPER | hands_feet | 0.468 | 33.00 | 25.99 | 20.47 |
| LOCAL_TORSO | torso | 0.666 | 29.76 | 18.14 | 14.40 |
| LOCAL_TORSO | arms | 0.560 | 28.65 | 18.10 | 13.08 |
| LOCAL_TORSO | legs | 0.579 | 30.11 | 24.43 | 17.63 |
| LOCAL_TORSO | head | 0.083 | 31.94 | 28.32 | 20.29 |
| LOCAL_TORSO | hands_feet | 0.356 | 59.18 | 49.98 | 43.78 |

## 解释

LOCAL_TORSO 中头部只有约 8.3% 的采样点落在 ROI，hands_feet 约 35.6%，而 torso 约 66.6%。这和误差排序一致：hands_feet 最高，head 也明显高于 torso/arms。它支持“输入可见性降低后远端补全更难”的工程假设。

但不能把 `roi_fraction` 当作严格遮挡率：它由 K0 投影、mask-derived box 和相机畸变共同决定；部位标签来自预测 mesh 最近顶点。该结果用于决定下一轮实验分层，不用于临床或解剖结论。

下一步应按 `head/legs/hands_feet` 高风险层做分层 held-out 评价，并额外保存残差点坐标和 face label；如果要训练，应优先做 visibility-conditioned completion 与不确定性输出，而不是对所有顶点使用同一个全局损失。
