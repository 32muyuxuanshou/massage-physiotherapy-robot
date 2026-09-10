# PUBLIC RGB-D Single-view vs Multi-view Surface Finetuning V2

当前 Training Readiness：**`READY_FOR_SINGLE_MULTI_AB`**。正式 S/M × 2 seeds 训练已经按冻结协议启动，V2 SEALED 与 Final Reserve 仍未打开。本页先记录训练前已经完成的合同；最终模型结果将在训练和新 SEALED 门控完成后补充。

## 研究问题

对完全相同的单张 Camera A RGB、K 和 dataset-provided ROI，训练时增加同步 Camera B Depth 表面监督，能否在 unseen subjects 上提高第一次 MHR 输出？推理时两组都只接收 Camera A 的单张 RGB；Multi-view 只存在于训练监督。

## Readiness 结果

- 现有归档结构池 131 人；新完成 geometry QA 57 人，171/171 同步记录通过，342 个 camera views 精确解码，14 张 contact sheet 已视觉复核。
- Split：TRAIN 60（15 历史 V1 TRAIN + 45 新人）、VAL 12 新人、V2 SEALED 12 新人、Final Reserve 15 新人；所有主 split subject-disjoint。
- 没有新增下载。V2 SEALED 与 Final Reserve 仅冻结身份和归档 hash，没有选择/读取帧。
- Pose/Camera-only exact freeze 已通过 100 steps：shape、scale、derived MHR scales、hand、face 在 1/10/100 steps 最大变化均为 0；有效训练自由度 1,325,325。
- Exact freeze 需要同一张 RGB 的 Official reference pass，并在六个 decoder 阶段钳制非目标输出。它仍是单图输入、无 fitting，但不是普通单次 forward。
- 16,384 个 topology-bound deterministic anchors 通过；2080 Ti 上独立 surface 计算可行。
- S 每 update：Camera A 16,384 anchors + 2,048 observations。M：A/B 各 8,192 anchors + 各 1,024 observations。总预算相同，view 内 mean 后跨 view mean。
- 真实 DEV 梯度 M/S 范数比：pose 0.895、camera 0.886、joint 0.891，没有两倍梯度问题。
- 固定 180 个 TRAIN A/B pairs，60 人全部通过 geometry QA；跨相机一致性 subject-macro median 9.174 mm。这不是 sensor error floor。
- 固定 VAL：12 人、36 行，observation、point indices、K、mask 均有 hash。
- TRAIN-only Txyz bias `[+9.724, -22.741, -98.794] mm`；新 VAL readiness 近似为 Official 61.281 mm、Txyz 30.799 mm。该值是 deterministic-anchor NN，不冒充最终 exact primary。
- 粗粒度 MHR 工程分区已由官方 LBS weights 建立：torso、arms、legs、head、hands/feet。上/下躯干、前/后背和医学穴位区域不可确定。

## 冻结训练协议

四个 paired runs：S/M × seeds `20260910`、`20260911`。每个 run 最多 540 optimizer updates，固定 VAL 每 60 updates，patience 3；每 180 rows 构成一个等效 epoch并按 seed 确定性重排，S/M 同 seed 的 update order hash 完全相同。

每个 run 在固定 VAL 上选择 subject-equal absolute exact point-to-triangle 最低的 eligible checkpoint。P90/P95 不得超过 Official 的 1.10 倍，coverage 不得比 Official 低超过 0.02。S/M 以两个 paired seeds 的 best primary 平均比较；M 至少平均改善 2 mm 且两个 seed 均不差于 S，才算 material multi-view gain。Translation-aligned 只解释 placement 与非平移 geometry，不参与选模。

如果 arm winner 冻结，预先指定 seed `20260910` 的 best eligible checkpoint 作为新 SEALED 候选；seed `20260911` 只用于稳定性复现。差异不足 2 mm 时判 `NO_MATERIAL_MULTIVIEW_GAIN`，优先保留计算更简单的 S。

## 关键文件

- [Readiness Gate](PUBLIC_RGBD_FINETUNING_V2_READINESS.json)
- [Subject QA](HUMMAN_V2_SUBJECT_QA_V1.json) 与 [Split](HUMMAN_V2_SUBJECT_SPLIT_V1.json)
- [Output Freeze Test](POSE_CAMERA_OUTPUT_BLOCK_FREEZE_TEST_V1.json)
- [Deterministic Anchors](MHR_DETERMINISTIC_SURFACE_ANCHORS_V1.json)
- [Pair Manifest](MULTIVIEW_PAIR_MANIFEST_V1.json) 与 [Geometry QA](MULTIVIEW_GEOMETRY_QA_V1.json)
- [Gradient Budget](SINGLE_MULTI_GRADIENT_BUDGET_AUDIT_V1.json)
- [Fixed Evaluation Manifest](V2_FIXED_EVALUATION_MANIFEST.json)
- [Single Protocol](TRAINING_PROTOCOL_SINGLE_V1.json) 与 [Multi Protocol](TRAINING_PROTOCOL_MULTI_V1.json)

历史 V1 文件没有修改。当前结果只面向 HuMMan、dataset-provided ROI、单 RGB+K inference 的工程研究，不代表治疗床俯卧裸背、DMD37、医学穴位或机器人定位已经解决。
