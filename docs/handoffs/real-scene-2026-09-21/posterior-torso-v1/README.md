# Posterior Torso V1：后背评价区域与穴位标注最小闭环

## 目的

本交付回答两个最便宜、但会直接影响后续路线的问题：

1. Mesh 误差是否发生在真正的后背表面，而不是被 whole-body 或 generic torso 平均掉；
2. 在 canonical MHR 上建立少量、可追溯的背部穴位拓扑标签，再用少量正常真人验证拓扑传播是否值得进入模型设计。

## 当前裁决

这不是一次训练，也不是医学真值发布。A 与 B 是两个不同的合同：

- A 是 **mesh 评价区域合同**；
- B 是 **解剖标签与医生验证合同**。

两者在医生验证前不合并成训练损失。

## A：POSTERIOR_TORSO_V1

当前状态为 `CANDIDATE_REQUIRES_CANONICAL_VISUAL_QA`。现有工程 body-part map 明确没有前后分界，现有 `posterior_cross_section_ok` 也只是点级 sanity check，因此不能直接复用为后背区域。

正式冻结前必须完成：

1. 在冻结的 MHR LOD1 上人工检查候选面片是否覆盖背部皮肤；
2. 排除头、颈、双臂、臀腿及躯干前侧；
3. 保存 face ids、vertex ids、mesh/face/rest-vertex SHA256；
4. 用至少一个渲染视图和一个法向/连通性检查确认区域没有断裂或镜像；
5. 冻结后所有 FULL/UPPER/LOCAL_TORSO 的 residual 统计按该 mask 单独报告。

在完成视觉 QA 前，不使用任意 XYZ 阈值将候选区域称为正式后背真值。

## B：canonical MHR 穴位标注

医生需要在 canonical MHR 上标注 5–8 个目标点。交付中的 JSON 是标注模板，不包含医生结果。每个点至少保存：

- 名称、左右侧和点类别；
- MHR face index 与 barycentric coordinate；
- canonical XYZ 与 body-local 坐标；
- 使用的体表标志/骨度分寸依据；
- 标注者、轮次、时间和复核状态。

`medical_truth` 在医生复核前必须为 `false`。拓扑 transfer 只表示工程上的表面对应，不表示跨人医学真值。

## 真人小规模验证

医生标签返回后，先用 3–5 名正常志愿者做 pilot：背向站立、固定相机与标定，记录医生在 RGB-D 表面上的点。报告：3D surface distance、2D 重投影误差、两名医生的 inter-rater agreement、canonical transfer 稳定性。该 pilot 不涉及机器人接触，也不宣称治疗效果。

## 决策门

- 若后背 mask 能在三维 surface residual 中稳定区分 FULL/UPPER/LOCAL_TORSO，A 进入正式评价；
- 若穴位 transfer 在医生间和真人 pilot 上误差可接受，才设计 acupoint head/loss；
- 若 transfer 只在 canonical mesh 上成立而真人复核不稳定，则保留为可视化工程功能，不把它包装成论文医学贡献。

## 本交付不做的事

- 不启动 SAM3D 或新的微调训练；
- 不把 DMD37 历史点位当作医学金标准；
- 不从当前 generic torso map 推导后背真值；
- 不在没有医生输入时填写穴位坐标或报告医学精度。

