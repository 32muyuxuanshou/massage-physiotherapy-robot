# 俯卧背部 Mesh 修正版对照 V2

**状态：本地准备与 S107 CPU 检查完成；服务器暂不可用，正式实验未运行（0/300）。**

本轮要确认深度修正是否真正改善后背表面，而不是靠评价错误、测试点参与优化或漏掉困难射线得到好看的分数。沿用原 20 人、4 人开发/16 人测试和种子 0/1/2；不训练模型，不添加触诊、穴位或不确定性模块。所有受试者已经用于历史诊断，不能称为未见泛化人群。

## 已交付

| 内容 | 文件 |
|---|---|
| 冻结方法、超参数与聚合公式 | [EXPERIMENT_CONTRACT.json](EXPERIMENT_CONTRACT.json) |
| 20 人原始 RGB 后背 ROI，可逐张复核 | [POSTERIOR_RGB_ROI.json](POSTERIOR_RGB_ROI.json)、[roi_review](roi_review) |
| 历史相机、bbox、原始文件身份 | `CALIBRATION_INPUT.json`、`BBOX_INPUT.json`、`RAW_INPUT_IDENTITY.json` |
| 后背面片与来源说明 | `POSTERIOR_FACE_MASK.json`、`POSTERIOR_REGION_PROVENANCE.json` |
| 正式入口、评价、缓存、绘图、汇总、测试 | [code](code) |
| 8 项纯代码/mock 检查 | [LOCAL_PREFLIGHT.json](LOCAL_PREFLIGHT.json) |
| 本地 S107 结果、划分索引与图 | [LOCAL_EXECUTION_REPORT.md](LOCAL_EXECUTION_REPORT.md)、[local_s107](local_s107) |
| 相机证据及其限制 | [CAMERA_AUDIT.md](CAMERA_AUDIT.md) |
| 旧新口径差异 | [OLD_NEW_DIFFERENCES.md](OLD_NEW_DIFFERENCES.md) |
| 缓存文件路径、键、形状及 SHA256 | [LOCAL_CACHE_INDEX.json](LOCAL_CACHE_INDEX.json) |
| 恢复服务器后的命令 | [SERVER_RUNBOOK.md](SERVER_RUNBOOK.md) |
| 执行/待执行清单 | [EXECUTION_RECORD.json](EXECUTION_RECORD.json) |

## 五组正式对照

`Official`、`Official+Txyz`、`Official+Txyz+Pose`、`Official+Rigid`、`Official+Rigid+D`。

先冻结原点云的 **6 cm 相机 XY 空间块、20% 块留出**，然后每人仅做一次新的 Official RGB 推理，保存完整 MHR 参数。四个优化分支共享此初值，只读取当次训练点。完整点云仍用于历史 bbox；这是共享的上游输入，已经写入合同，不宣称整个输入过程完全独立。

Txyz 保留六次迭代、每轴单步 ±50 mm、177.88820176363325 mm 总范数限制，保存 raw/applied translation 和 fallback。O2 保留 25 次、1024 点、anchor stride 2、Huber 0.02、学习率 0.003/0.001、两项先验 0.01；不优化 shape/scale。Rigid/D 的函数体与历史代码 AST 相同，D 的 λ=0.15 等现有设置不改。

先运行 S104/S107/S165/S187 开发检查，结构通过后运行完整 20 人，共 300 条方法—人物—种子记录。Official 的三个种子评价复用同一次推理，不算三次独立实验。

## 评价与图

主诊断为：RGB 后背 ROI 内相同留出点 → 固定 2152 个工程后背三角面。保留旧 torso 20–62% → 全 Mesh 距离供对账。另报连续透视射线残差、命中率和所有方法共同命中点残差。**没有命中时不伪装成零误差**；汇总不偷偷跳过无有效值的种子。

每个方法/种子保存最终顶点、面、完整 MHR 状态、外部 R/t/D、实际训练/姿态采样索引及配置。Rigid/D 不是新 MHR 参数化模型：保留原始 MHR prior，并单存外部变换和 effective camera translation，避免混淆。最终网格是评价和所有图片的唯一几何来源。

图片包括透视 RGB 对照、后背残差点图、真正按相机 X 取面的切片、三轴平移图与质量图。紫色填充和绿色边界都来自预测 Mesh；青色点是点云投影；黄色框是冻结后背 ROI。绿色不是人体真值轮廓。

逐种子统计先求算术平均成为逐人记录，再汇总开发/测试受试者中位数；保存每人的变化，不只选最好的总分。轮廓参考为完整过滤点云的投影支撑，属于共享上游辅助诊断，不是独立手工分割 GT。

## 证据边界与下一步

当前相机来自床垫共面四角及官方 viewer 位置的历史重建，没有恢复该次物理 RGB-D 的完整原始标定。因此本轮结果统一解释为 **该重建坐标合同下的同源空间留出诊断**，不称独立毫米级精度或裸背穴位定位精度。

本地只有 S107 原始 `p_select.p`，且本地没有 Torch、完整权重、anchor 文件和已核实 GPU 环境。本地结果只覆盖旧 RGB-only Official → Rigid → Rigid+D、一个种子，**不代替新的五组正式实验**。

服务器恢复后按 runbook 核实环境与资产，再执行开发阶段和完整阶段。届时才能回答改善是否稳定，以及下一笔时间应投入相机、几何模型还是穴位解剖对应。成功标准是可解释、可复查，不是必须比历史 3.60 mm 更小。
