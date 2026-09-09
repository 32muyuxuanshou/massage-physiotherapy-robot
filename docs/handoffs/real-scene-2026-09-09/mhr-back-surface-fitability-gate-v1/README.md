# MHR_BACK_SURFACE_FITABILITY_GATE_V1

更新日期：2026-09-09。最终 Gate 状态：**`INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED`**。本轮优先检查 MHR 表示能否在独立真实几何下拟合俯卧背部；审计发现当前没有合格真实 RGB-D/multi-view 表面观测，因此按停止条件没有运行 fitting，也没有 global finetuning。

## 研究问题、证据与判断

表示能力问题和预测问题已分开：SAM 可能预测错 MHR 参数，但 MHR 仍可能表达目标人体；也可能是俯卧软组织/床面接触超出当前参数化模型。只有给冻结的 MHR 独立几何，再看 held-out surface error，才能开始区分两者。

当前两段本地素材 V01/V02 是 RGB 宣传/演示视频。8 张精选帧包含真实俯卧背部和机器人遮挡案例，但没有 Depth、Depth 单位、RGB/Depth 注册、内参、畸变或外参。身份也未核验，不能把两段视频或相邻帧计成独立受试者。工作区中的 Depth/EXR 来自 Blender/SKEL 合成流程，不是真人传感器观测。

代码审计确认当前 MHR head 输出 519 维：全局旋转 6、body continuous 260、shape 45、scale/skeleton basis 28、双手 108、face 72；face 在当前 body forward 中被置零。camera head 是 3 维 `(s, tx, ty)`，再结合 bbox、焦距和内参转换成相机平移。当前 wrapper 的 `vertex_offsets` 参数没有实际使用，因此本 Gate 将来首先测试 pose/shape/skeletal scale 的表达，不假装已经具有局部接触形变自由度。

## README 要求的 15 个回答

1. **有真正独立 RGB-D/multi-view surface observation 吗？** 没有。
2. **observation 来自 visible bare back 吗？** RGB 中存在可见裸背区域，但没有对应真实 3D observation；因此没有合格 surface observation。
3. **RGB/Depth 可靠标定和注册了吗？** 没有 Depth，也没有标定或注册文件。
4. **Official SAM 的真实 surface 误差多少？** 无法计算；当前只有二维轮廓开发诊断。
5. **V2-E5 是否改善真实 surface？** 无法判断。V2-E5 只改善了当前 COCO 来源二维 joint validation。
6. **真实几何下 per-image/per-subject fitting 能否降低 held-out surface error？** 尚未执行，因为几何观测门未通过。
7. **改善来自 camera/pose/shape/skeleton/combined 哪项？** 没有合法实验结果。未来按四阶段受控诊断。
8. **有 parameter cheating 吗？** 本轮没有优化，因而没有新作弊；历史单图轮廓拟合已显示 camera 与 geometry 均能吸收二维误差，未来必须限制并报告漂移。
9. **Gate 是 PASS、INCONCLUSIVE 还是 FAIL？** `INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED`。
10. **是否值得现在采正式 30 人数据集？** 暂不启动。先用 3–5 人 Gate 判断表示与拟合链是否可行。
11. **下一个最小实验是什么？** 3 人、每人 A/B/C 三个标定 RGB-D bundle；A 拟合、B 独立视角评价、C 重复性。网络冻结，依次优化 camera、pose、shape/scale、combined。
12. **是否足以排除优化器和数据问题并判 FAIL？** 完全不足。当前没有进入优化。
13. **能说 Mesh 变准吗？** 不能。
14. **能说 DMD37 变准吗？** 不能；只能继续做绑定、传播和方法间差异。
15. **下一步最值得投入什么？** RGB-D 数据、标定与 fit/eval 独立性。没有它们，fitting、global finetuning、LoRA 和 MHR 表示扩展都缺少判断依据。

## 执行门与后续

采集协议固定在 [MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.md](MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.md)；机器可读版包含标定阈值、语义类别、held-out 设计和 Gate 执行顺序。数据审计见 [MHR_BACK_SURFACE_DATA_AUDIT_V1.json](MHR_BACK_SURFACE_DATA_AUDIT_V1.json)，参数接口见 [MHR_PARAMETER_INTERFACE_AUDIT_V1.json](MHR_PARAMETER_INTERFACE_AUDIT_V1.json)，停止决定见 [MHR_BACK_SURFACE_FITABILITY_DECISION_V1.json](MHR_BACK_SURFACE_FITABILITY_DECISION_V1.json)。

Gate PASS 前不启动 30 人训练集、不解冻 decoder、不上 LoRA。Gate 数据到位后，先完成 per-image/per-subject fitting；若多名受试者 held-out surface 一致改善且没有 camera/shape/scale 异常，再规划正式 target-domain dataset。

## Material Passport

本轮只读取两段本地 RGB 视频的既有抽帧清单、Blender 合成 RGB-D 资产索引和本地 SAM 3D Body 源码。没有复制原视频、真人帧、授权权重或合成数据进入新公开目录；Git 只包含审计结论、采集合同和代码接口说明。DMD37 未参与评价，`medical_truth=false`。
