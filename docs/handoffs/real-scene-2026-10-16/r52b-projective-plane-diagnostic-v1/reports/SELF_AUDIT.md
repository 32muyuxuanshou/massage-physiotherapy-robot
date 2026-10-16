# R5.2b 自审

## 实验问题与范围

只验证经典投影点面求解能否改善当前Fine的几何更新。18个预设方法、3个父模型seed、2706状态；零训练，不扩展为新的可学习求解器。保留之前的原始模型与实验。

## 实际验证项

- `SOLVER_PREFLIGHT.json`：三个seed×三个数据域及已知失败身份共15状态，初始Query/采样/可见性和一步中位数与R52对账。解析已知translation、平面秩退化的最小范数解。
- `INPUT_FREEZE.json`：全量源缓存实际SHA匹配旧冻结值；Body张量与冻结预测exact equality；旧参考fit实际SHA匹配R52 POST_INTEGRITY。
- `EVALUATOR_PREFLIGHT.json`：旧Official+Txyz/Fine的真实独立指标重现；新评价器与旧文件归一化换行后的文本完全相同，未改距离、点集、变换或聚合公式。
- `REFRESH_PILOT_EVALUATION.json`：全量fit JSON包含变化的耗时字段，15帧先导评价旧hash失效。保留旧文件于pilot_evaluation，再用原评价器重算15帧；没有修改拟合或指标以“通过”检查。
- `CACHE_REPLAY_QA.json`：三个数据域的代表端点从新A-grid+Body/Coarse缓存独立复算，覆盖普通点面、Huber与4096候选，不加载ViT或B。
- `POST_INTEGRITY.json`：检查预执行科学代码/配置、实际原输入与G资产、最终compact预测，以及评价记录链接的fit SHA；全部2706记录与18方法完整性。
- `BACKUP_RECEIPT_final.json`：218私有完整卷与Windows实际字节SHA一致。原始数据/权重/大型NPZ不入Git，凭据仅进程环境。

## 数据边界

拟合函数只使用A端depth/valid/K/affine与预测Body/Coarse。旧manifest及参考JSON包含历史评价metadata，但这些值不进入更新、权重或样本选择；“A-only”不意味着manifest里从未出现任何B端统计字符串。原始B点仅用于评价；Native `.pt`对象含GT字段，但拟合不访问它。封存Native/HuMMan TEST未读，BEHAVE为已消费子集。

Native为对应顶点/Camera参数；HuMMan与BEHAVE主指标为固定独立点→三角面；拟合SMPL PVE为支持证据。所有方法每帧同一评价点；没有删负面样本。四个旧参考重新评价，不计为新的模型推理或训练。

## 不能据此声称

不声称精确上限、绝对可靠对应、全域胜出、临床/穴位精度、参数根节点真值更准、端到端推理时延或新的论文贡献。可见数/法线谱只是局部求解系统信息，不等于解剖可观测性真值；当前全身Query也不能替代后背区域验证。

报告/可视化/缓存复算工具为执行后的描述分析，不影响拟合、点集、权重或选模；其最终版本另由Git文件清单冻结。未自动追加训练、实例或关机操作。

## 本次实际结论

代码/流程/全量实验已完成。10824条旧参考数值最大差异0；48708条方法记录、216组汇总；POST_INTEGRITY实际14181文件通过。新方案没有稳定超过旧基线，因此不进入学习权重训练。备份回执将在完成后与本报告一同交付。

实际执行保留原run.py；未来复跑入口run_reproduction.py仅将先导评价隔离，避免旧fit哈希复用，不改科学算子。该入口已静态编译，未另跑第二轮全量实验。

为保持实际执行字节，交付目录使用局部.gitattributes禁止Git转换冻结Python/JSON换行；代码公式未改变。
