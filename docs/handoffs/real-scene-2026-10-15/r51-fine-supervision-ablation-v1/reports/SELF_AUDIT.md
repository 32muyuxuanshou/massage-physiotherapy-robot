# R5.1执行自审

结论：本轮12个有限消融单元已执行，所有预定评价完成；结果支持监督目标取舍，未得到足以升级方法的真实稳定优势。不是新的正式大规模模型训练。

|检查|实际证据|状态|
|---|---|---|
|四组同seed配对初始化/数据顺序|TRAINING_ALL逐epoch SHA；summarize218实际assert|PASS|
|Coarse与Body隔离|PREFLIGHT Coarse无梯度；仅Fine state保存；48次原模型重装检查Body exact unchanged|PASS|
|预采样不改变数学路径|前向最大差7.45e-9m；参数梯度最大差2.384e-7；E0损失相等|PASS|
|损失与L2预冻结|SCIENCE_FREEZE与L2_CALIBRATION实际SHA；L2仅TRAIN标定|PASS|
|训练完整性|4组×3seed×6epochs；84个epoch权重；没有pending/running/errors|PASS|
|选模隔离|SELECTION_FREEZE在新真实评价前生成；旧Best、Joint Best、Last全部保留|PASS|
|旧评价器与父结果重现|8帧先导；全部父预测逐帧复算均在浮点网格扰动界内；最大BEHAVE PVE差0.0052mm以内|PASS|
|原固定点集/三角面距离|几何包与4621文件实际SHA；B不参与拟合|PASS|
|全量真实评价|21唯一状态×502帧=10542原始预测+10542指标；重用选择状态不重复计算冒充新实验|PASS|
|结束后二次资产核验|POST_INTEGRITY实际重读27503文件；原资产/输入不变|PASS|
|失败结果保留|逐帧、逐人、部位proxy、救回/新增坏、P95与三个seed完整；失败图明确选例规则|PASS|
|历史61.06/本轮59.64对账|相同逐帧结果，不同汇总权重；JSON同时保存两种口径|PASS|
|备份|三卷各自实际SHA回执；备份完成状态以BACKUP_RECEIPT为准|见回执|

## 对Gemini建议的最终裁决

固定Coarse、把两档监督和L2拆开、提前冻结选模、记录真实梯度，这些建议可执行且已执行。但“降Camera一定修复表面”“小残差就是噪声底限”“全局L2能消灭负收益”等说法不能预设成立。实际显示：删掉Camera监督改善合成、损害真实；0.5只有微小收益，L2无稳定收益。

E0不是原50轮joint训练复现，是固定Coarse后的匹配续训。E1_half代码名沿用，但权重是0.5，即原2.0的四分之一。不同seed父模型不同，只保证seed内部配对。

## 未验证与限制

- 仅6轮有限续训，不证明收敛、最优学习率或最优权重。
- 实测梯度仅固定8张Native TRAIN探针、Fine最后层，不是全网络或全部数据因果证明。
- 正交分量针对Coarse→GT平移方向，不能称背部切向误差；表面指标也不是Camera参数真值。
- HuMMan TRAIN/VAL与BEHAVE子集已消费；封存Native/HuMMan TEST未读，BEHAVE是历史官方TEST子集，不冒称没有读任何名为TEST的数据。
- Scan full-mask Z包含未命中惩罚。BEHAVE点云有遮挡/异常、SMPL是拟合参考，不能证明裸背、穴位、临床精度或M³同协议领先。
- 本轮没有完整RGB→Mesh端到端计时。缓存Fine训练吞吐不能用作系统延迟。
- 服务器保持开启；没有追加组合、长跑、R6或付费实例。

原DATA_RESTORE_RECEIPT的MISSING是准备阶段发现历史包不含Scan；后续已实际传输并SHA核验。DATA_READY记录解决链，未覆盖原始回执。
