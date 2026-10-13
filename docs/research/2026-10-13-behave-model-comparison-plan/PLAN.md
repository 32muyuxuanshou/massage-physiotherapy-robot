# BEHAVE 现有模型统一评价计划

日期：2026-10-13。状态：**方案已整理，正式实验未启动。**

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: plan
- Origin Date: 2026-10-13
- Verification Status: UNVERIFIED（指本计划的正式实验）
- Version Label: behave_comparison_plan_v1

## 目标

在 BEHAVE 同一组 RGB-D 帧上评价现有模型，与 M³ 的论文报告 PVE 并列展示，同时判断误差主要来自整体位置还是人体几何。本轮不重新训练、不修改网络，不以完整复现 M³ 为前提。

M³ 的 70.9 mm 是 BEHAVE TRAIN 微调后的 TEST PVE，93.1 mm 是未进行这一步微调的结果。作者未明确公开对齐、时间戳、机位和汇总细节，两者只能列作论文报告参考，不能宣称同协议排名。

## 1. 无卡准备：盘点与真实帧坐标检查

1. 核查 AutoDL 与 218 上已有 BEHAVE、日期标定、RGB/Depth/person mask、`person/fit02/person_fit.ply`；缺什么补什么，不默认重新下载全部大包。
2. 核查固定 MHR→SMPL 映射、面片顺序、Official 及训练 checkpoint 的 SHA。复用指标交付 `79c652bb`。
3. 使用 2–3 个已消费帧验证真实 fitting mesh 的世界→K0 转换，并按官方加载/投影实现做对照。不能仅凭变换与逆变换闭环宣称实帧配准正确。
4. 检查 fitting mesh 的顶点数量、顺序和参考空间；RGB、原始 Depth、参考人体、预测人体必须使用同一日期和相机合同。拟合参考保留为 fitted reference，不称扫描或医学绝对真值。
5. 若只有旧预测缓存，可以先做 CPU 核验；现有 GPU 尚未核查，不能把全部新推理标成可在无卡模式完成。

## 2. 在任何新精度结果出现前冻结样本和模型

- 输入机位固定 K0。Depth 优化只用 K0；K1/K2/K3 只用于观测表面评价。
- 新对照输入域显式统一：K0 RGB 用 LINEAR 去畸变，已配准轴向 Z 和 mask 用 NEAREST 去畸变，目标 K 等于官方 K；不调整外参、尺度或内参来贴合预测。dataset-mask bbox 外扩 25 px，各方法使用相同 mask 输入。这与历史直接使用 distorted RGB 的跑法不同，不能声称逐数值重现历史分数。独立相机评价仍使用原始 ray table 得到的传感器三维点。
- 正式目标：官方 TEST 的 90 个序列，每序列取结构完整时间戳的 25%、50%、75% 位置，共约 270 帧。按确定公式取整并去重，实际数量写入 manifest。它是官方 TEST 子采样，不冒称完整测试。
- 先做资产覆盖盘点。若 90 序列暂不能全部取得，先报告缺失和实际覆盖，再冻结可执行队列；不能根据模型精度决定下载或保留哪一个序列。
- 历史 Date03 消费帧仅用于回归核验，正式报告记录重合数量。官方 TEST 是序列划分，不等于全部新人物；整轮不宣称完全未见泛化。
- 保留失败帧；纯数据损坏/缺少参考在模型运行前登记，不能在看到误差后删帧。
- 方法：Official、Official+历史 Cheap Txyz、G1、R5 Coarse、R5 Full。另列已有 RGB-only 训练模型作为控制，区分额外训练与 Depth 的贡献。
- 所有训练模型使用 seeds 11/23/37；Best 与 Last 事先锁定并分别报告。Best 按原 native VAL 选择规则，Last 为第 50 轮。不能根据 BEHAVE 结果挑 checkpoint。
- Official 也保留 seeds 11/23/37 的推理重复核验；其权重相同，不能称三次独立训练。Txyz Anchor、K0 点采样和全部评价点预先固定，不人为增加采样差异。
- 新模型主结果直接输出，不加 Txyz。Official+Txyz 复用历史 16,384 anchors、6 次迭代、20% trimming、每轴 ±0.05 m、总范数 0.17788820176363325 m 和原 fallback。

## 3. 小批正常路径 → 固定全量

先跑 6–12 个已消费/专门登记的 smoke 帧，覆盖不同日期、姿态和遮挡，检查输入、坐标、各 checkpoint、保存及图像生成。Smoke 不用于调参或选择正式样本；记录其与正式子集是否重合。

每次保存：原生 MHR Body、Camera、相机顶点、映射后的 SMPL 编号顶点、配置/权重 SHA、K0 优化点索引、K1–3 评价点索引和 Txyz raw/applied/fallback。评价与可视化从缓存读取，不重新拟合。

小批通过才运行已冻结队列。新前向需要已授权、可用的 GPU；评价 PVE 和缓存核验可以在 CPU 上完成。不新增付费实例，不关闭服务器。

## 4. 分开报告三个问题

|问题|指标|限制|
|同一个模板顶点位置是否正确|6,890 对应顶点平均 L2：绝对 PVE|包含整体位置与人体几何，映射本身是近似对应|
|去掉整体位置后身体几何如何|去质心平移 PVE；PA-PVE 仅作辅助|不把质心对齐叫 pelvis/root 对齐；PA 不能证明绝对定位|
|是否贴近独立可见观测|固定 K1/K2/K3 点到精确三角面 median/P95、50 mm coverage|只证明观测表面，不能代替顶点对应或穴位真值|

- PVE 每帧先取所有顶点距离均值，主表按帧等权均值，同时保留 sequence→identity 等权和逐帧表。
- 传感器表面指标保留各 camera 明细，再 camera→frame→sequence→identity，公式写进配置，不与 PVE 混为一个毫米数字。
- R5 Coarse/Full 只做整体平移：同一 Official Body 的去质心 PVE 理应与 Official 一致。若出现差异，先检查 Body、映射、单位和坐标处理，不解释成人体改善。
- G1 的去平移结果才用于检查其人体变化是否有益。其他没有原生 Body 真值的指标不被命名为 Pose/Shape 真值误差。
- MPJPE 暂不进主表：必须先取得明确回归器和关节定义，不能猜作者关节集合。
- 逐 seed、逐身份、P95 和全部失败保留。只对本轮数据与指标作结论，不把 BEHAVE 结果直接外推成俯卧裸背或穴位精度。

## 5. 交付与下一项判断

输出固定数据/权重清单、CPU 实帧坐标 QA、全部模型缓存、逐帧/序列/身份 CSV/JSON、Best/Last 分表、论文报告值的来源说明，以及 HTML。

HTML 包含 RGB 叠图、预测/拟合参考区分、侧面/俯视三维图、同编号顶点误差和独立传感器表面残差；选图规则预先固定，保留失败索引。许可约束下 RGB 图留本地/私有服务器，Git 交付代码、指标、索引和报告。模型和大缓存备份至 218，记录 SHA 回执。

结果判断：

- 若 R5 改善绝对 PVE、保持人体几何且改善独立表面，继续公制定位路线；还需实测运行成本和目标点精度。
- 若人体几何误差主导，定位 Head 的能力已到边界，再设计人体几何/对应模块。
- 若 G1 改善去平移几何但定位不稳定，研究把其人体与定位收益分别保留，而不是直接扩大原共享融合。
- 若 Official+Txyz 明显更好，保留工程基线，不能仅凭新模型名称宣布研究成功。
- 若坐标或参考投影异常，先修数据适配，再评价模型，不用训练补偿评价错误。

这轮结束再决定训练方向；不自动重构或开始新一轮长跑。

## 来源

- 已阅读用户提供的 M³ v2 PDF：`C:/Users/Administrator/Downloads/2508.08178v2.pdf`。
- [BEHAVE 官方数据结构与 sequence split](https://github.com/xiexh20/behave-dataset)。
- [现有指标桥接合同](../2026-10-13-behave-metric-alignment/README.md)。
- 原 R5 checkpoint 选择合同：`research/rgbd_sam3d_mhr/r5_complete/R5_COMPARISON_CONFIG.json`。
