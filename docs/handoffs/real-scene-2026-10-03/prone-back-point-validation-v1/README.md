# 表面与工程点对应验证 V1

2026-10-03。实际执行完成，未训练，医学对应未验证。先读[最终报告](FINAL_REPORT.md)，复现和服务器路径见[执行说明](REPRODUCTION.md)。

| 审查内容 | 完整入口 |
|---|---|
| 冻结详细计划 | [执行前规格](../../../research/2026-10-03-no-deployment-camera/DETAILED_EXECUTION_PLAN_V1.md) |
| 本轮代码/未修改基线 | [源码](code/)、[基线快照](frozen_baseline_code/) |
| 单位/300缓存/语义HOLD | [资产审计](results/p0/POINT_ASSET_AUDIT.json)、[缓存身份](results/p0/CACHE_SOURCE_MANIFEST.json)、[修正atlas](results/p0/ENGINEERING_ATLAS_UNIT_CORRECTED.json) |
| 2,400点/480移动配对 | [逐点输出](results/p1/PROPAGATED_POINTS.jsonl)、[配对](results/p1/PER_POINT_DIAGNOSTICS.csv)、[人物汇总](results/p1/SUMMARY.json)、[全部尾部](results/p1/ALL_POINT_TAILS_AND_LIMITATIONS.json) |
| 180视图ROI/Camera QA | [ROI冻结](results/p2/BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json)、[最终QA](results/p2/CAMERA_QA.json)、[初始coarse gate失败](results/p2/CAMERA_QA_INITIAL_COARSE_GATE_FAILURE.json) |
| 正式合同/资产/配置 | [合同](results/p2/P2_EXECUTION_CONTRACT.json)、[运行freeze](results/p2/P2_RUNTIME_FREEZE.json)、[配置补充](results/p2/P2_SUPPLEMENTAL_EXECUTION_FREEZE_PRE.json)、[聚合冻结](results/p2/P2_AGGREGATION_VISUAL_FREEZE.json) |
| 评价索引/225最终网格 | [实际索引](results/p2/FROZEN_POSTERIOR_EVALUATION_INDICES.json)、[缓存身份](results/p2/FINAL_MESH_CACHE_MANIFEST.json) |
| 相机→帧→序列→人物 | [相机](results/p2/PER_CAMERA_METHOD.csv)、[帧](results/p2/PER_FRAME_HELDOUT.csv)、[序列](results/p2/PER_SEQUENCE_HELDOUT.csv)、[人物](results/p2/PER_SUBJECT_HELDOUT.csv)、[主结果](results/p2/RESULTS.json) |
| 45帧原始指标/优化元数据 | [全部帧evaluation与mesh metadata](results/p2/ALL_FRAME_EVALUATIONS_AND_METADATA.json)；大NPZ在服务器，路径/SHA见缓存身份 |
| 运行与完整性 | [Smoke](results/p2/SMOKE_GATE.json)、`results/p2/EXECUTION_LEDGER_*.json`、`INTEGRITY_*.json`、[Launcher post](results/p2/P2_SUPPLEMENTAL_EXECUTION_INTEGRITY_POST.json) |
| 缓存独立重算 | [15组数组exact equal](results/p2/CACHE_ONLY_RECOMPUTATION_CHECK.json) |
| K0改善/heldout退化 | [配对审计](results/p2/RIGID_D_PAIRED_AUDIT.json)、[输入可见性描述性分层](results/p2/K0_VISIBILITY_DESCRIPTIVE_AUDIT.json) |
| PCdare/DMD资格 | [报告](DATA_QUALIFICATION.md)、[匿名结果](results/p3/) |
| 60框架/2,400规则代理点 | [共享身份](results/p4/SHARED_REFERENCE_FRAME_MANIFEST.json)、[规则点](results/p4/RULE_PROXY_POINTS.jsonl)、[方案分歧](results/p4/METHOD_POINT_DISAGREEMENT_SUMMARY.csv) |
| 全部图与文件身份 | [逐图索引](VISUALIZATION_INDEX.md)、[验收](DELIVERY_VALIDATION.json)、[文件SHA](FILES_MANIFEST.json) |

人工对模型叠图的实际检查范围见[视觉复核记录](VISUAL_REVIEW.md)。生成全量图与人工看完全部图是两件事。

BEHAVE有900条相机—方法记录，其中675条潜在held-out记录，只有180条对应36个可用后背视图。28/45帧有held-out后背；5帧/3人同时有K0与held-out后背。无参考的视图明确缺失，不是0 mm。

Git内105页均为不含原始RGB的预测/点位图，不能单独用于判断原图对齐。完整RGB叠图有60页PressurePose和45页BEHAVE，实际保留：

- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p1_cached_transfer/visualizations/`
- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p2_behave_crossview/private_rgb_review/`
- 服务器ROOT下对应同名目录，ROOT见复现说明。

紫色/绿色为预测Mesh/预测轮廓；青色是输出前冻结的RGB参考小块。编号点是旧工程种子，医学语义HOLD，不是医生GT。数值和绘图不重新拟合。

原数据/授权权重/原生MHR资产/大NPZ不入Git。含PCdare原路径或姓名线索的完整关联留服务器，公开表匿名化。P0/P1/P2执行、P3当前资产资格、P4代理链及P5证据决策完成；独立医学参考验证、训练、部署和治疗未完成。
