# RGB-D Mesh System Baseline and Abstention V1

## 最终判断

本阶段没有训练 SAM，也没有修改任何已有 checkpoint。我们回答了两个产品问题：一次 Official + 便宜的深度平移修正，能否替代双模型 selector；Camera A 深度能否识别两个候选都失败。

最终状态是：

- **`BOTH_USEFUL_DIFFERENT_TRADEOFFS`**：Cheap C 的中央误差和速度更好；双模型 G 的尾部和部分困难人物更稳。
- **`ABSOLUTE_FAILURE_DETECTION_NOT_READY`**：现有数据可排序 BAD30 工程风险，但 BAD50/80 阳性太少，不能称为安全拒答器。

推荐把 **System C 作为下一版工程默认候选**，保留 **G_gpu 作为高鲁棒候选**。最终取舍必须由真实治疗床、多姿态、裸背 RGB-D 数据决定。

## 系统

- **O**：Official SAM 3D Body。
- **A**：冻结的 V2 Adapted specialist。
- **G_exact**：历史冻结规则，Camera A exact point-to-triangle `Delta > 15 mm` 且 coverage 不降低超过 0.02 时选择 A。
- **G_gpu**：CUDA surface-splat depth residual，阈值同为 15 mm；这是新的运行时近似。
- **B**：TRAIN-only constant Txyz bias。
- **C**：Official + Camera A depth bounded Txyz。只移动整体 Mesh，不改变姿态、旋转、形状、尺度或局部顶点。

System C 使用 16,384 个固定表面锚点、6 次鲁棒最近邻平移、去掉最大 20% 对应误差；每次分量移动不超过 0.05 m，最终 `|Txyz|` 上限为 0.177888 m，超界就回退 Official。所有参数在新 System Sealed 打开前冻结。

## 数据治理

- 已消费 development：此前 72 + 12 + 10 人。
- 新 SYSTEM_VAL：2 人、6 帧，仅用于冻结后验证，画面主要是俯卧支撑类。
- 新 SYSTEM_SEALED：4 人、12 个动作、36 帧。
- FINAL_DEEP_RESERVE：原始 15 人全部保留，像素未打开。

sealed 实际画面经过三张接触图逐帧复核，包含四点支撑、跪姿、坐姿、前倾、仰卧扭转、侧卧、臀桥、儿童式和俯卧支撑。每个小类别样本仍少，因此 pose/view 表只作描述，不宣称任意姿态泛化。

Camera A 负责 RGB 推理、selector 和 C correction；Camera B 只评价。Camera B 没有重新运行 SAM。同一个 Camera A Mesh 经 A→world→B 标定链变换，闭环最大误差小于 0.4 微米，低于预注册的 1 微米 float32 容差。

## 开发和 System VAL

在已消费 DEVELOPMENT / SELECTOR_VAL 上，C 的 Txyz 优于 Tz-only：

| 数据 | Official | Tz | Txyz C | Constant B |
|---|---:|---:|---:|---:|
| DEVELOPMENT | 59.915 | 19.084 | **18.605** | 28.604 |
| SELECTOR_VAL | 49.075 | 33.379 | **32.435** | 37.632 |

Txyz 在 SELECTOR_VAL 改善 11/12 人、32/36 帧；Official <30 mm 的 5 人没有 subject-level 退化。修正本身 P50/P90 为 109.6/131.0 ms，低于第二次 SAM forward。

新的 SYSTEM_VAL 很困难：O 为 141.009 mm，G 为 19.906 mm，C 为 100.776 mm。C 在一人上因超界安全回退，另一人明显改善但仍不及 Adapted。这一结果没有用于修改 C 或 G。

## 一次性多姿态 System Sealed

以下均为 subject-equal Camera-B whole-body surface 指标：

| System | Absolute ↓ | Aligned* ↓ | P90 ↓ | P95 ↓ | Coverage ↑ |
|---|---:|---:|---:|---:|---:|
| O Official | 63.634 | 19.628 | 143.151 | 159.913 | 0.626 |
| A Adapted | 26.592 | 15.741 | 69.972 | 88.919 | 0.754 |
| G_exact | 25.471 | 15.908 | 68.232 | **85.173** | **0.774** |
| G_gpu | 23.921 | **15.699** | 68.232 | **85.173** | **0.774** |
| B constant Txyz | 32.686 | 18.842 | 88.070 | 109.250 | 0.722 |
| C per-frame Txyz | **22.483** | 17.501 | **67.760** | 87.706 | 0.752 |

\* Aligned 使用 Camera B 真值进行 XYZ-only oracle 对齐，只作诊断。

C 的 absolute 比 G_gpu 好 1.438 mm，P90 好 0.472 mm；G_gpu 的 P95 好 2.533 mm、aligned 好 1.802 mm、coverage 高 0.022。说明 C 更擅长纠正全局位置，G 的人体内部姿态/表面对应更好。

按人物看，C 在 3/4 人上最低；`p000838` 上 G_exact 为 27.62 mm、C 为 34.51 mm。低误差保护方面，Official <30 mm 的 10 帧中，A 拉坏 6 帧，G_exact/G_gpu/C 都是 0。高误差救援方面，Official ≥60 mm 的 18 帧中，G 全部改善，C 改善 13 帧。C 有 5 帧触发超界并回退 Official。

G_gpu 与 G_exact 在 sealed 上 35/36 决策一致；G_gpu 最终反而更低，是因为唯一不同帧上的选择更接近 Camera B 真值。这是一次 sealed 观察，不能回头用来调 GPU 阈值。

## 运行成本

2080 Ti sealed P50：

| 系统组成 | 时间 |
|---|---:|
| Official forward | 276.0 ms |
| Adapted 第二次 forward | 309.4 ms |
| GPU residual | 43.4 ms |
| G_gpu 总计 | 628.8 ms |
| Cheap Txyz correction | 110.9 ms |
| C 总计 | **386.9 ms** |

相对 Official，G_gpu 增加约 352.8 ms并改善 39.71 mm；C 增加约 110.9 ms并改善 41.15 mm。峰值 CUDA allocation 约 3.06 GB。计时不包括数据解码和 Camera B 研究评价。

## Abstention

已消费数据上，selected rendered-depth residual 对 BAD30 的 AUC 为 DEVELOPMENT 1.000、SELECTOR_VAL 0.938。VAL 从 100% 接受降到约 58% 接受时，平均误差从 24.71 降到 18.11 mm，BAD30 从 27.8% 降到 4.8%。但 BAD50 只有 2/1 个阳性，BAD80 两组都是 0 个，无法验证严重失败检测，也没有把 abstention 带入 sealed。

30/50/80 mm 都只是工程诊断阈值，不是临床安全阈值。

## 可以和不可以声称什么

可以说：在 HuMMan RGB-D、数据集人物 ROI、4 个新人物的多动作 sealed 上，C 与 G 都显著优于 Official；C 提供更好的中央 absolute/速度，G 提供更好的尾部、aligned 和覆盖表现。

不能说：任意姿态都鲁棒、治疗床或裸背已经验证、背部 Mesh 更准、DMD37 穴位更准、已经达到临床安全，或 raw RGB 全自动流水线完成。当前指标仍是 whole-body surface。

## 下一步唯一建议

固定 C 和 G_gpu，不再在 HuMMan 上调规则。采集或整理一批**失败富集的真实产品域多姿态 RGB-D**：治疗床、裸背、遮挡、侧卧/坐姿/俯卧和困难深度；Camera A 运行系统，独立几何传感器或 Camera B 评价。该实验直接决定产品默认使用 C、G_gpu，还是按运行模式保留两套。

关键入口：`FINAL_SYSTEM_DECISION_V1.json`、`SYSTEM_COMPARISON_V1.json`、`SYSTEM_RUNTIME_COST_V1.json`、`SUPPORTED_POSE_RESEARCH_MATRIX_V1.json`、`ABSOLUTE_FAILURE_ABSTENTION_V1.json`、`SYSTEM_SEALED_RESULTS_V1.json` 和 `visualizations/`。
