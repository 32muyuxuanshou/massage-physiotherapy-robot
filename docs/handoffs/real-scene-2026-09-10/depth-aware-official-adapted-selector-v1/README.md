# Depth-aware Official / Adapted Selector V1

## 结论

本阶段通过：`PASS_DEPTH_AWARE_SELECTOR`。在规则冻结后首次打开的 10 个新人物、30 帧上，只看 Camera A 的 RGB-D 几何残差，逐帧选择 Official 或 Adapted；再用从未参与选择的 Camera B 深度考试。选择器 30/30 选中了 Camera B 上更好的候选，subject-equal absolute surface error 为 **30.662 mm**，优于 Always Official 的 **68.613 mm** 和 Always Adapted 的 **32.271 mm**，并在这批数据上达到 O/A Oracle 的 **30.662 mm**。

这证明的是：在 **HuMMan RGB-D + dataset-provided ROI** 条件下，“通用模型 + 专用模型 + 深度选择器”比固定使用任一模型更稳。它不证明 raw RGB 自动流水线、背部局部 Mesh 或 DMD37 穴位已经更准。

## 方法和数据治理

- Generalist：官方 SAM 3D Body ViT-H，SHA256 `3b1cb897...d66056`。
- Specialist：V2 single-view winner，seed 20260910，update 120，SHA256 `1aedfd0f...f107`。
- DEVELOPMENT：72 人；SELECTOR_VAL：12 人；新的 SELECTOR_SEALED：10 人；FUTURE_RESERVE：21 人。
- 新封存集来自此前只做结构清单、没有读取像素或模型结果的 QA alternates。原 15 人 Final Reserve 全部保留。
- 每帧只从 Camera A RGB、内参、深度和数据集人物 ROI 生成两个 Mesh 与残差。Camera B 只负责最终标签和指标。
- 主特征是 Camera A 精确 point-to-triangle median：`Delta = R_Official - R_Adapted`。
- 冻结规则：`Delta > 15 mm` 且 `coverage_A >= coverage_O - 0.02` 时选 Adapted，否则选 Official。少于 2048 个点、缺深度或平局均回退 Official。
- 阈值只在已消费数据上确定。打开新 sealed 之前，规则、模型、人物、帧和指标已冻结并写入 hash receipt。

三个候选分数都做了审计。point-to-triangle 最强：development 的 AUC 为 0.956、相关系数 0.954；selector VAL 的 AUC 为 1.000、相关系数 0.976。有限阈值集合为 0/2/5/10/15 mm，15 mm 在两组开发数据上没有 false switch，因此采用保守阈值。校准分箱见 `SELECTOR_CALIBRATION_CURVE_V1.json`。

## 一次性 sealed 结果

| 系统 | Absolute ↓ | Translation-aligned* ↓ | P90 ↓ | P95 ↓ | Coverage ↑ |
|---|---:|---:|---:|---:|---:|
| Always Official | 68.613 mm | 22.529 mm | 137.321 mm | 157.449 mm | 0.6431 |
| Always Adapted | 32.271 mm | 21.353 mm | 88.815 mm | 117.696 mm | 0.7122 |
| Depth selector | **30.662 mm** | **17.239 mm** | **81.771 mm** | **108.662 mm** | **0.7298** |
| O/A Oracle（只作分析上限） | 30.662 mm | 17.239 mm | 81.771 mm | 108.662 mm | 0.7298 |

\* Translation-aligned 使用 Camera B 真值做 XYZ-only oracle 对齐，只是诊断，未参与选择。

Selector 捕获了 Official 到 O/A Oracle 的 100% 改善空间；这是这 30 帧的结果，不能理解为未来数据一定 100% 正确。它选 Adapted 23 帧、Official 7 帧，winner accuracy 100%，False Switch 0，Missed Rescue 0。覆盖率没有通过减少覆盖刷分；选择后的覆盖率反而最高。

低误差保护用 Camera B 上 Official <30 mm 定义，仅用于评价：5 个低误差帧中，Always Adapted 拉坏 4 个，Selector 拉坏 0 个，并在 4/5 帧保留 Official。高误差救援用 Official >=60 mm 定义：10 个困难帧全部由 Adapted 获胜，Selector 全部救回。当前 sealed 没有选择错误；最大残余风险是两个候选同时失败，选择器无法产生比候选更好的 Mesh。

## 工程成本

严格 Adapted 合同需要先跑 Official reference forward，再跑 Adapted forward，所以系统需要两次 SAM forward。2080 Ti 上实测中位数：Official 0.287 s，Adapted 第二次 forward 0.288 s，合计约 0.575 s。研究评测器中的完整距离、对齐与双相机渲染中位数约 44.59 s，主要是未优化的 CPU exact point-to-triangle 与 Camera B 评价，不能当作产品 selector 延迟。峰值 CUDA allocation 约 3.05 GB。下一轮若产品化，必须实现只含 Camera A 的 GPU residual kernel，并重新测端到端延迟。

Cheap Txyz 没在这批 selector sealed 上新跑。原因是这次预注册问题限定为“不修改 Mesh，只在 O/A 中选择”，且新的 Txyz sealed 实现没有在打开前冻结。历史 TRAIN-only Txyz 仍保留在上一阶段交付，不能事后加入这批正式结果。

## 29 个交付问题的直接回答

1. 不继续训练 SAM，因为已有模型互补性很强，当前瓶颈是何时用 Specialist。
2. Official 保护简单样本；Adapted 大幅改善许多困难姿态，但会拉坏一部分原本正确的人。
3. 能预测：开发 AUC 0.956/1.000，新 sealed 30/30。
4. 最有效特征是 Camera A point-to-triangle residual delta。
5. tau 从五个预注册候选中按开发集的保守错误权衡定为 15 mm。
6. 是，只用 consumed development 和 selector VAL。
7. 是，rule receipt 和 readiness 在读取 sealed 像素前冻结。
8. 10 个此前未用于模型/规则结果的人，共 30 帧。
9. Always Official 68.613 mm。
10. Always Adapted 32.271 mm。
11. Selector 30.662 mm。
12. Oracle 30.662 mm，仅作分析上限。
13. 在本 sealed 捕获 100% O/A Oracle 空间。
14. 是，低误差帧的负迁移从 4/5 降到 0/5。
15. False Switch 0。
16. Missed Rescue 0。
17. 是，>=60 mm 的 10 个困难帧全部被救援。
18. Selector P90/P95 为 81.771/108.662 mm，均优于两固定系统。
19. 没有；coverage 为 0.7298，高于 O 和 A。
20. 目前只输出 low-evidence 诊断概念，尚未验证可靠的拒绝策略。
21. 是，严格 Adapted 需要两次 forward。
22. 两次 forward 约 0.575 s；含精确对齐和 Camera B 评价的研究实现约 45.16 s/帧，不能直接部署。
23. SAM forward 成本约为 Official-only 的两倍，另有待 GPU 化的深度评分。
24. 这批未正式比较 Cheap correction，不能声称 selector 一定更值；下一次应在新数据上预注册比较。
25. 可以限定称为“HuMMan RGB-D + dataset ROI 下更鲁棒的 whole-body Mesh system”。
26. 不能称为更准确的背部 Mesh，因为没有独立背部区域指标。
27. 不能说 DMD37 更准，本阶段没有穴位标签。
28. 下一步唯一优先项是将 Camera A residual GPU 化，并在新的姿态覆盖数据上预注册比较 Selector、Official 和 cheap correction。
29. 因为科学信号已经很强，当前最大工程风险是计算成本和数据域覆盖，而非再调一次 SAM 参数。

## 复现与审计入口

- `SELECTOR_RULE_FREEZE_RECEIPT_V1.json`：封存前规则。
- `DEPTH_AWARE_SELECTOR_READINESS_V1.json`：打开门禁。
- `SELECTOR_SEALED_RESULTS_V1.json`：逐帧正式结果与总表。
- `HUMMAN_SELECTOR_SEALED_GEOMETRY_QA_V1.json` 与 `visualizations/`：30 帧几何和目视 QA。
- `code/audit_depth_selector_features.py`：严格两阶段模型推理和残差计算。
- `raw/`：服务器日志与未聚合特征。

额外审计发现：上一阶段 V2 SEALED 脚本没有在 Adapted forward 应用已声明的 Pose/Camera output clamp。这里已按正式 VAL 合同做两阶段修正复跑；V2 winner absolute 从历史报告 30.368 mm 变为 30.363 mm，差 0.005 mm，原结论不变。本阶段所有开发与 sealed 结果都使用修正后的严格两阶段合同。
