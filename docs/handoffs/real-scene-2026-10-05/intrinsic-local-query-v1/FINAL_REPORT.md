# 局部曲面编码对照：成熟全身模型不能直接搬来

实际完成362局部点云算子（133.59秒）、360考试case×三方法=1080评价（29.20秒），冻结作者权重，无新训练。实际1080预测缓存与360输入重算4320检查PASS，全部40扫描结果图保留。

## 相同观测下的结果

单位：注册身份位置欧氏差/sqrt(各库完整曲面面积)×100。不是mm、测地误差或穴位准确率。FULL表示**完整后背ROI点云**，仍不是完整全身。

| 数据/输入 | HKS NN | 作者DiffusionNet描述子 NN | 作者局部 functional map |
|---|---:|---:|---:|
| FAUST FULL | 14.00 | 15.87 | 10.99 |
| FAUST PARTIAL | 11.61 | 14.98 | 13.36 |
| FAUST NOISY_PARTIAL | 12.23 | 13.21 | 13.83 |
| SCAPE FULL | 12.22 | 11.25 | 10.05 |
| SCAPE PARTIAL | 10.96 | 12.10 | 12.49 |
| SCAPE NOISY_PARTIAL | 11.03 | 12.80 | 13.66 |

此前作者完整身体上下文参考PARTIAL为FAUST1.70、SCAPE2.40；当前局部functional map为13.36、12.49。此差同时包含**输入范围、点云离散、局部谱边界、归一化与训练分布变化**，不能单独归因“缺少上下文”或宣布DiffusionNet架构无效。它说明全身预训练模型原样用于局部背部不够。

与前轮成对模型使用相同360case和同一query评分。作者权重训练80 FAUST、小模型训练60，资源不同；局部输入信息范围公平，不等于模型训练资源公平。所有FAUST/SCAPE考试来源已消费，不称新泛化。

## 决定

保留默认拓扑传播，停止原样搬运全身HKS编码器。下一阶段做**局部输入的身体位置参考＋曲面特征双路query学习**，同时比较身体分支、几何分支、双路；只用训练/开发选择，SCAPE不调参。该结构是研究原型，不能把普通特征融合当已经成立的顶会贡献。

最终工程仍是RGB-D→MHR整体先验→后背测量表面→稳定身份/参考→规则/atlas→xyz/face/bary/normal。当前不批准医学位置与机器人治疗；现有approx相机及作者注册标签的证据边界保持。

## 完整交付

[协议](PROTOCOL.md)、[配置](CONFIG.json)、[case](CASE_MANIFEST.json)、[算子列表](OPERATOR_MANIFEST.json)、[源freeze](SOURCE_FREEZE.json)、[执行记录](EXECUTION_LEDGER.json)、[完整结果](RESULTS.json)、[逐扫描表](PER_SOURCE_RESULTS.csv)、[缓存核查](CACHE_REPLAY.json)、[40扫描图](figures)。

源码`run_intrinsic.py --phase all`与`analyze_intrinsic.py`；服务器 `/raid5/xuhd/datasets/registered_human_correspondence_20261005/intrinsic_local_query_v1`。原FAUST/SCAPE、vts、局部算子及预测扫描坐标仅服务器；Git保留全量指标、实际缓存路径/hash与图，不重新分发原研究数据。
