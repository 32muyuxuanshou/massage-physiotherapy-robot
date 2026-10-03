# 项目当前状态

更新时间：2026-10-04。现役入口以本页及所链接的机器可读结果为准；历史 handoff 保留当时的合同与结论。

## 目标

真实**俯卧背部 RGB-D → 个体 Mesh → 工程参考/规则定位 → 后续机器人坐标接口**。工程效果与可发表的方法贡献并行推进，表面距离、点位稳定性、医学准确率及部署精度分别验收。当前没有部署相机和独立临床穴位真值，可以继续离线工程，不将 AI 代理当临床标注。

## 最新实际交付

0. [工程模板与法向几何对照V2](handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2/FINAL_REPORT.md)：新8个ENG中性探针/300缓存/2,400传播完成；20人×3种子新增60个法向D，四方法240缓存/评价完成。16人测试角色后背距离Rigid 8.25、向量D 3.66、法向D 3.99 mm；切向移动1.86→0.48 mm，但跨种子点跨度7.39→7.75 mm，14/16人法向D的全身投影支持IoU弱于Rigid。300个BEHAVE候选资格筛查不足5×6帧，Sub07最多3个非相邻时刻/1序列，未启动新BEHAVE模型。470冻结源与240缓存核验PASS，原180基线逐点指标exact一致。没有新训练/SAM推理，不能作为临床或部署精度。

1. [可信俯卧五方法修正版](handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2-execution/FINAL_REPORT.md)：PressurePose 20人、开发4/测试角色16、3 seeds，共300缓存完成。优化前划分6 cm空间块留出，各分支共享新的Official。测试角色后背距离Rigid 8.25→Rigid+D 3.66 mm；属于近似相机合同下的同源空间留出，13/16人全身投影支持IoU下降，不是产品或穴位精度。
2. [表面与点位对应验证](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/FINAL_REPORT.md)：300缓存/单位/拓扑实读；2,400工程点、60共享规则框架及2,400规则代理点；BEHAVE五人固定45帧、五方法225网格、K1/K2/K3独立sensor对照完成。
3. 新BEHAVE posterior patch：Rigid 30.80→Rigid+D 30.32 mm，4/5人改善，Sub06略退化。180视图仅36个held-out后背小块/28帧有效；仅5帧/3人同时有K0及held-out后背参考。穿衣、非俯卧、已消费人物，**不足以确认俯卧裸背的稳定独立D增益**。[全部结果](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/results/p2/RESULTS.json)
4. 旧8点atlas：canonical原始cm，修正为×10 mm；缓存m×1000不变。同拓扑通过，但旧GV14/GV4上下颠倒、中线种子偏侧、左右与历史轴声明冲突。**语义HOLD，不生成医学标签或治疗目标。**[资产审计](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/results/p0/POINT_ASSET_AUDIT.json)
5. [公开数据资格](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/DATA_QUALIFICATION.md)：DMD历史205组全部视觉检查，1张确认俯卧；当前V2为0图。PCdare324非Output点云与1,326线候选已枚举，有源码支持的几何重新绑定；没有三维穴位GT或已核验校准prone RGB-D关联。

PressurePose和BEHAVE的区域、相机和聚合不同，不把绝对数值拼成同一项精度。全部失败和缺失保留，没有本轮训练/微调。

## 已有基础

- 官方SAM3D Body checkpoint/MHR推理、真实图像Mesh叠加已跑通；不等于从头复现论文训练。
- 历史Cheap Txyz：HuMMan36帧63.63→22.48 mm；BEHAVE五人45帧whole-body口径31.17→17.80 mm。单向depth点→面距离，不是穴位准确率。[历史报告](handoffs/real-scene-2026-09-11/behave-cheap-txyz-generalization-v2/results-v2.3/RESULTS.md)
- [固定顺序复现V1.4.12](handoffs/real-scene-2026-09-14/sam3d-txyz-reproducibility-isolation-v1/formal-execution-v1.4.12/README.md)历史Gate通过，225次SAM B–F固定顺序精确一致、27特征稳定；另有最大约0.001 mm帧顺序浮点效应，后续保持帧顺序冻结。
- 历史合成RTMPose只证明合成工程任务可行，不能推导当前真人穴位定位精度。

## 当前 Gate

| 事项 | 状态 |
|---|---|
| 缓存传播/单位/同拓扑 | 新ENG atlas几何绑定通过；人体解剖左右/旧医学语义仍未验证 |
| Rigid+D同源局部拟合 | 局部收益成立，存在轮廓/全局质量代价 |
| Rigid+D独立机位后背收益 | 已执行；收益小、覆盖有限，未通过强结论 |
| 法向D单因素对照 | 60新分支完成；切向代价下降，种子稳定性/完整网格合格性未通过 |
| 新BEHAVE共同后背cohort | 300候选筛查不足计划预算；未签发manifest，0新模型/拟合 |
| 8点atlas医学语义 | HOLD；独立代理候选也未医学验证 |
| Mesh+规则代理链 | 跑通；椎体/B-cun输入为代理 |
| 独立三维穴位/可靠目标对应 | 尚无资格数据，不报告准确率 |
| 新训练、Mesh teacher、DMD37伪标签 | 未启动/未放行 |
| 部署相机、机器人变换及接触控制 | 未验收 |

## 运行位置

最新实际执行服务器：`xuhd@172.18.18.151:436`，本轮4个CPU人物进程求解，没有新GPU模型加载。环境、代码、输入与资产SHA见[最新复现说明](handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2/REPRODUCTION.md)。上一轮BEHAVE为5张RTX2080Ti按人物运行，属于历史已完成批次。

- 最新：`/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003`
- 上一轮：`/raid5/xuhd/datasets/prone_back_point_validation_20261003`
- 300俯卧Mesh源：`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2`
- BEHAVE数据：`/raid5/xuhd/behave_rgbd_mesh_v1/data`
- 新资料：`/raid5/xuhd/datasets/back_prone_acquisition_20261003`
- SAM代码/权重：`/raid5/xuhd/sam3d_s01_pilot_20260906`，授权权重不入Git。

完整RGB复查保留服务器及本地`output/prone_back_point_validation_v1`；Git交付不含原图的预测图、代码、配置、索引和指标。原始数据、原生模型资产、大型NPZ不重发。

## 下一步

工程atlas V2与法向对照已完成。保留Rigid/向量D/法向D为基线；优先补同后背块的独立观测或已知相机/表面/对应的受控几何闭环，先厘清观测与目标对应。当前45帧不换样本，新cohort资格不足不填数。独立证据明确后，再决定RGB-D几何或参考/对应模块训练。

本轮原计划见[工程模板与几何机制验证计划V2](research/2026-10-03-no-deployment-camera/NEXT_EXECUTION_PLAN_V2.md)，执行结果以上方最新报告为准。完整原RGB新副本在本地 `output/back_geometry_correspondence_v2/private_review/INDEX.html`。

医学对应最终需要可靠独立目标参考，部署效果最终需要设备标定和验收。当前小残差不能替代这两项。
