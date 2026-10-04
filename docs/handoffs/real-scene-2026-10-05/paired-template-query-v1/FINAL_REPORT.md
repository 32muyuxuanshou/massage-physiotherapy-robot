# 成对模板查询 V1：接口完成，跨库精度不足

结论：任意源模板query→当前可见扫描→face/bary绑定已经实际跑通；小型共享PointNet不能承担最终定位。它在SCAPE显著退化，局部近邻编码也没有改善。保留失败，进入成熟曲面编码器对照，不在考试数据上继续调参数。

## 实际执行

- FAUST：60扫描训练、20开发、20已消费考试；SCAPE：模板000及20跨库姿态考试，不是20患者，不进入训练/开发。
- SCAPE实际冻结名单为mesh052–071。原协议“051–070”是编号文字错误；作者包无051而有071，实际manifest在训练前即为052–071，未根据结果换样本。见[说明](COHORT_CLARIFICATION.md)。
- 模板输入为点坐标/法向和query，而不是固定FAUST坐标或GT对应。FAUST26query、SCAPE27query；GT可见性只用于评分，网络推理全部query。
- 两个模型×三个初始化×1200步，实际训练480.08秒，推理25.65秒；360考试case、2520方法评价。
- 2520实际缓存、40原始网格、360case独立重算，15120检查PASS；原冻结资产未改变。所有40扫描图均交付。

## 结果

数值为注册身份位置欧氏误差 / 各自完整曲面sqrt(area)×100，不是毫米、测地距离或穴位误差。初始化与扰动种子平均→每扫描→20扫描中位。

| 数据/输入 | 几何NN | PAIR_GLOBAL | PAIR_LOCAL | 作者DiffusionNet完整上下文支持参考 |
|---|---:|---:|---:|---:|
| FAUST FULL | 8.79 | 2.07 | 2.04 | 1.74 |
| FAUST PARTIAL | 8.72 | 1.96 | 2.09 | 1.70 |
| FAUST NOISY_PARTIAL | 8.27 | 1.87 | 1.93 | 1.70 |
| SCAPE FULL | 18.41 | 6.93 | 8.63 | 2.44 |
| SCAPE PARTIAL | 18.13 | 7.22 | 8.67 | 2.40 |
| SCAPE NOISY_PARTIAL | 17.75 | 7.63 | 8.68 | 2.40 |

PARTIAL的SCAPE P95：GLOBAL15.80、LOCAL17.09、NN22.56。SCAPE平均query可见率约80%；缺失query仍会产生输出，其正确性未批准。

DiffusionNet为实际作者FAUST-HKS权重、原functional map实现，作者commit `b1019b049597711d10259ce28250f7dfc4335a2b`。SCAPE21完整几何算子、180case评分实际63.77秒。**它先看到完整未扰动曲面，且预训练80扫描；小模型只有局部观测、训练60扫描。** 因此这些数值支持“强编码器值得检验”，不能证明完全公平的架构优势。各方法仍用相同query评分，详见AUTHOR_SCAPE_RESULTS及前轮AUTHOR_BASELINE_RESULTS。

## 对工程和论文的决定

保留任意模板query接口，停止采用这两个小模型作为最终匹配器。FAUST中的改善不是临床背部定位证据；跨库退化表明当前描述子不够可靠。完整上下文参考明显更好，但局部可用性尚未证明，下一阶段只用相同局部点重建算子进行对照。

最终模型应区分可见表面几何与身体上的身份位置，利用全身MHR姿态参考和局部RGB-D观测共同定位；当前实验未实现RGB融合、医学参考标志或可靠性预测，也没有临床标注。不能据此宣称模型创新已足够顶会。

## 交付与复现

- [协议](PROTOCOL.md)、[配置](CONFIG.json)、[冻结case](CASE_MANIFEST.json)、[源hash](SOURCE_FREEZE.json)。
- [训练](TRAINING_LEDGER.json)、[执行](EVALUATION_LEDGER.json)、[全量结果](RESULTS.json)、[逐来源CSV](PER_SOURCE_RESULTS.csv)、[缓存重算](CACHE_REPLAY.json)。
- [作者跨库参考](AUTHOR_SCAPE_RESULTS.json)、[40扫描图](figures)、[可视化hash](VISUALIZATION_MANIFEST.json)、完整code。
- 服务器：`/raid5/xuhd/datasets/registered_human_correspondence_20261005/paired_query_v1`；相同SAM虚拟环境Python；`code/paired_experiment.py --phase prepare/train/evaluate`与`code/analyze_pair.py`。重新prepare会覆盖派生缓存，应使用新目录进行新实验。
- 原始FAUST/SCAPE数据、vts、模型权重及预测扫描坐标不入Git。FAUST仅研究许可，产品训练权需另行取得。Git提供全部逐case指标和服务器实际缓存路径/hash；不是只交汇总。
