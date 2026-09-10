# PUBLIC RGB-D Single-view vs Multi-view Surface Finetuning V2

当前状态：**V2 VAL 选模与 one-shot V2 SEALED 已完成；Final Reserve 未打开。最终 Gate 为 `OBJECTIVE_CONFLICT_LOW_ERROR_PROTECTION_FAILED`。**

本阶段比较相同 Camera A RGB、K、dataset-provided person ROI 下的两个训练臂。S 只用 Camera A depth 表面监督；M 在训练时增加同步 Camera B depth。两者推理输入都只有 Camera A 单张 RGB+K 和同一个数据集 ROI。为了保证 shape、scale、hand、face 输出逐元素与 Official 相同，当前实现先做 Official reference pass，再做 adapted pass，因此是单图输入但需要两次 forward。

## 实验结论

四个正式训练均完成，共 1,860 次 optimizer updates、约 5.11 GPU 小时。S 两个 seed 的最佳 V2 VAL absolute 分别为 24.791/22.412 mm，均值 23.601 mm；M 为 21.992/23.981 mm，均值 22.986 mm。M 平均仅好 0.615 mm，并且第二个 seed 更差，没有达到预注册的“至少 2 mm 且两个 seed 均不差”标准。因此判定 **`NO_MATERIAL_MULTIVIEW_GAIN`**，选择计算更简单的 S，冻结 `seed=20260910, update=120`，checkpoint SHA-256 为 `1aedfd0f2cf6819078b9aae451ea681c51239f0945180dc2459122710dc3f107`。

选中 S checkpoint 在固定 V2 VAL 上为 24.791 mm absolute、15.279 mm translation-aligned、P90 65.237 mm、P95 93.182 mm、coverage 0.7902。Official 为 59.901/17.580/114.589/130.134 mm、coverage 0.6951；TRAIN-only Txyz 为 28.570/17.580/69.847/86.931 mm、coverage 0.7702；Historical V1 E1 为 30.413/15.085/70.137/87.522 mm、coverage 0.7699。

这说明选中模型相对 Official 同时改善绝对误差 35.111 mm 和对齐误差 2.301 mm，支持 V2 VAL 上存在一部分非平移几何改善。它相对 Historical V1 E1 的 absolute 好 5.622 mm，但 aligned 差 0.195 mm，且 P95 差 5.660 mm，因此不能声称几何质量全面超过历史模型。V2 VAL 有 10/12 subjects 的 absolute 优于 Official。

首次打开的新 V2 SEALED 上，Official / Txyz / Historical V1 E1 / V2 winner 的 absolute 分别为 49.371 / 37.738 / 30.429 / 30.368 mm；aligned 为 21.079 / 21.079 / 20.052 / 19.835 mm。V2 winner 相对 Official 的均值 absolute 改善 19.003 mm、aligned 改善 1.244 mm，P90/P95 改善 40.124/39.883 mm，coverage 从 0.6873 升至 0.7010。然而 absolute 只有 6/12 subjects 改善，并未达到多数；Official absolute <30 mm 的 5 人全部退化。结果表明均值和尾部收益主要来自修正大误差对象，同时牺牲已经较准的对象，因此当前 S 模型不能无条件替换 Official。

现有 coverage 指标支持“没有通过少覆盖来换取较低中位误差”，但评估产物没有保存所有 comparator 的共同交集像素，严格 common-coverage paired error 尚未计算。

四个 raw formal run reports 没有顶层 `best` 字段。最佳点由 `history[*].fixed_val` 可确定性重建，并由 `FORMAL_TRAINING_AGGREGATE_V1.json` 和 `FORMAL_CHECKPOINT_MANIFEST_V1.json` 绑定。它是报告 schema 缺陷，不能把 raw report 本身说成已经包含 authoritative top-level best。

## 第 42 节的 36 个问题

1. **新的 QA 后有多少真正 usable subjects？** 新增 57 个完成 geometry QA 的 subjects；171/171 同步记录、342 views 通过。整个 frozen 主 split 含 99 人，其中 TRAIN 还复用 15 个已 consumed 的历史 V1 TRAIN。
2. **哪些历史 subjects 被标记 consumed？** `p000757,p000783,p000816,p000821,p000823,p000826,p000830,p000831,p000837,p000842,p000853,p000859,p000861,p000874,p000878,p000879,p000880,p000881,p000902,p000913,p000914,p000924,p000942,p000956,p000973,p001002,p001008,p001018,p001037,p001088,p001110`。其中 15 个 V1 TRAIN 只在 V2 TRAIN 内复用；历史 DEV/VAL/SEALED 不进入新的 VAL、V2 SEALED 或 Final Reserve。
3. **Train / Val / New SEALED / Final Reserve 各多少人？** 60 / 12 / 12 / 15，四个主 split subject-disjoint。
4. **是否新增下载，多少 GB？** 没有，0 GB；复用已在服务器的公开 HuMMan 归档。
5. **Pose/Camera-only 是否真正实现？** 是。有效可训练自由度 1,325,325，只允许 global rotation、body pose 和 camera FFN 更新。
6. **Shape 是否 exact unchanged？** 是，100-step 预检和全部非 SEALED 正式验证的最大差为 0。
7. **Scale 是否 exact unchanged？** 是，最大差 0。
8. **Derived MHR scales 是否 unchanged？** 是，最大差 0。
9. **Hand/face 是否 unchanged？** 是，两者最大差均为 0。
10. **Deterministic 16,384 surface sampling 是否通过？** 是；face indices、非负 barycentric、roundtrip 都通过，barycentric sum 最大误差 `1.1920929e-7`。
11. **Single 与 Multi 每次 update 的总 surface supervision budget 是否相同？** 是。两者均为 16,384 predicted anchors 和 2,048 observed points。
12. **Multi 用几个 view？** 两个同步 view：A/B 各 8,192 anchors、各 1,024 observations，跨 view 取 mean。
13. **Input 是否仍只有单 RGB？** 是，两个模型都只输入 Camera A RGB+K+同一 dataset ROI；Camera B 只提供训练监督。
14. **两个模型 gradient budget 是否同量级？** 是。真实 DEV 的 M/S median gradient norm ratio 为 pose 0.895、camera 0.886、joint 0.891。
15. **TRAIN-only Txyz baseline 如何？** V2 VAL absolute 28.570 mm、aligned 17.580 mm、P90 69.847 mm、P95 86.931 mm、coverage 0.7702。
16. **Official 如何？** V2 VAL absolute 59.901 mm、aligned 17.580 mm、P90 114.589 mm、P95 130.134 mm、coverage 0.6951。
17. **Historical V1 E1 在新 VAL / 新 SEALED 如何？** 新 VAL 为 absolute 30.413 mm、aligned 15.085 mm、P90 70.137 mm、P95 87.522 mm、coverage 0.7699；新 SEALED 为 30.429/20.052/80.470/101.812 mm、coverage 0.7067。
18. **Single-view 新模型如何？** 两 seed best absolute 为 24.791/22.412 mm，均值 23.601 mm；冻结候选为前者。
19. **Multi-view 新模型如何？** 两 seed best absolute 为 21.992/23.981 mm，均值 22.986 mm。
20. **VAL winner 是谁？** 按预注册规则选择 S；具体 SEALED 候选为 S seed 20260910 update 120。
21. **为什么？** M 只平均好 0.615 mm，小于 2 mm 门槛，而且两个 seed 的方向不一致。
22. **New SEALED 上 winner 是否改善？** subject-equal 均值改善：absolute 从 49.371 降至 30.368 mm，aligned 从 21.079 降至 19.835 mm；但这不是多数 subject 的稳健改善。
23. **多数 subject 是否改善？** 没有。新 SEALED 相对 Official 仅 6/12 absolute 改善，另外 6 人退化；相对 Txyz 为 8/12，相对 Historical V1 E1 为 6/12。
24. **low-error subjects 是否仍系统退化？** 是。新 SEALED 中 Official absolute <30 mm 的 5 人全部退化，增量为 +17.903、+11.990、+22.383、+0.873、+0.808 mm。
25. **absolute improvement 多少？** V2 VAL 相对 Official 改善 35.111 mm；新 SEALED subject-equal mean 改善 19.003 mm（38.49%）。
26. **translation-aligned improvement 多少？** V2 VAL 相对 Official 改善 2.301 mm；新 SEALED 改善 1.244 mm。新 SEALED 相对 Historical V1 E1 仅改善 0.217 mm。
27. **如果 absolute 涨、aligned 不涨，如何解释？** 主要是相机平移/放置改善，不能归因于身体形状或姿态几何改善。
28. **如果 aligned 也涨，是否可说非平移 geometry 改善？** 可以在同一评估域内有限地说“存在部分非平移几何改善”，但不能扩展到未测域、背部或医学定位。
29. **P90/P95 如何？** V2 VAL 为 65.237/93.182 mm。新 SEALED winner 为 74.939/98.203 mm，Official 为 115.063/138.086 mm，两项改善 40.124/39.883 mm；也优于 Txyz 和 Historical V1 E1。
30. **Coverage 如何？** V2 VAL 为 0.7902。新 SEALED winner 为 0.7010，Official 为 0.6873，提升 0.0137；比 Historical V1 E1 低 0.0058。严格 common-coverage paired error 未在结果中持久化，不能声称完全相同像素支持下的配对优势。
31. **是否存在作弊？** 没有发现 split 泄漏、SEALED 选模、额外推理 view 或输出块漂移。winner 在 SEALED 前冻结，SEALED 只评 Official/Txyz/V1/winner，Final Reserve 未打开；dataset ROI 和两次 forward 仍必须披露。
32. **是否有可信 torso map？** 有一个 topology-bound、由官方 LBS weights 派生的粗工程 torso map，2,122 vertices / 4,250 faces，资产和 topology hash 已绑定。
33. **能否说背部/torso 已改善？** 不能。该 map 不能区分上/下躯干、前/后表面或医学穴位；现阶段只能报告 whole-surface 指标。
34. **Multi-view supervision 有价值、无明显增益还是有害？** 在当前等预算两 seed 协议下是 **无明显增益**。数据不足以断言普遍有害。
35. **下一步最值得测试什么？** 唯一优先实验：固定 S 路线，加入面向 Official 低误差样本的 protective/non-regression gating 或 loss。
36. **为什么？** 新 SEALED 已明确显示 5/5 低误差对象退化，而总体均值和尾部仍改善。保护实验直接检验这个已观察到的冲突；Shape/Scale、Synthetic、LoRA 或单纯扩大数据暂时都会混入新的变量，无法先回答能否保住已经正确的 Official 预测。

## 审计边界与下一门控

- **ROI 边界：**训练和评估都使用 HuMMan dataset-provided person ROI、registered depth/mask 与 K；没有测试 raw-image person detector、遮挡恢复、治疗床俯卧裸背、DMD37 或机器人定位。
- **两 pass exact freeze：**第一次 Official pass 缓存六阶段非目标输出，第二次 adapted pass 钳制这些输出；这是 exact invariance 的代价。
- **区域结论：**LBS map 只支持粗工程分区，不能把 whole-surface 结果改写成 back/torso/acupoint 改善。
- **SEALED 边界：**winner 在首次 V2 SEALED 访问前冻结，loser 未在 SEALED 上选模；one-shot 结果已写入。Final Reserve 继续未打开。

## 关键产物

- [Readiness](PUBLIC_RGBD_FINETUNING_V2_READINESS.json)、[Subject split](HUMMAN_V2_SUBJECT_SPLIT_V1.json)、[Output freeze](POSE_CAMERA_OUTPUT_BLOCK_FREEZE_TEST_V1.json)
- [Formal aggregate](FORMAL_TRAINING_AGGREGATE_V1.json)、[Curve decision](TRAINING_CURVE_DECISION_V2.json)、[Winner freeze](V2_WINNER_FREEZE_MANIFEST.json)
- [VAL baselines](V2_VAL_BASELINES_EXACT_V1.json)、[New SEALED](NEW_SEALED_TEST_RESULTS_V1.json)、[Absolute vs aligned](ABSOLUTE_VS_ALIGNED_V2.json)、[Coverage](COVERAGE_AUDIT_V2.json)
- [Single metrics](SINGLE_PER_VALIDATION_METRICS.json) / [CSV](SINGLE_PER_VALIDATION_METRICS.csv) / [curve decision](TRAINING_CURVE_DECISION_SINGLE_V1.json)
- [Multi metrics](MULTI_PER_VALIDATION_METRICS.json) / [CSV](MULTI_PER_VALIDATION_METRICS.csv) / [curve decision](TRAINING_CURVE_DECISION_MULTI_V1.json)
- [Invariance final](PARAMETER_OUTPUT_INVARIANCE_FINAL_V1.json)、[Failure cases](FAILURE_CASES_V2.json)、[Experiment decision](FINAL_EXPERIMENT_DECISION_V2.json)
- [Engineering body-part audit](BODY_PART_MAP_AUDIT_V1.json)、[Geometry QA](MULTIVIEW_GEOMETRY_QA_V1.json)、[Gradient budget](SINGLE_MULTI_GRADIENT_BUDGET_AUDIT_V1.json)
