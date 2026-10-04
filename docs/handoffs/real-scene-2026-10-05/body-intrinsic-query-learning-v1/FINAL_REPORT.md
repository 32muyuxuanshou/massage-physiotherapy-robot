# 局部身份学习结构对照：双路没有成立

三卡实际完成9次训练，各1200steps；训练算子720份（264.89秒），全量网络考试3240评价（57.53秒），非学习控制360评价。实际3600缓存、360case重算14400检查PASS，所有40扫描图交付。模型只由20开发来源的固定PARTIAL seed0选择，SCAPE不参与训练/开发。

## 核心结果

单位为注册身份位置欧氏误差/各库完整曲面sqrt(area)×100，不是毫米或穴位准确率。FULL为完整后背patch，非全身。先模型/输入seed平均、再每扫描、最后20扫描中位。

| 数据/输入 | 分位坐标 NN | BODY | INTRINSIC | DUAL |
|---|---:|---:|---:|---:|
| FAUST FULL | 2.74 | 2.13 | 11.68 | 2.55 |
| FAUST PARTIAL | 2.91 | 2.21 | 12.17 | 2.63 |
| FAUST NOISY_PARTIAL | 2.98 | 2.11 | 13.49 | 2.85 |
| SCAPE FULL | 13.92 | 6.46 | 10.27 | 7.64 |
| SCAPE PARTIAL | 13.68 | 7.17 | 9.80 | 8.07 |
| SCAPE NOISY_PARTIAL | 13.22 | 7.04 | 10.20 | 8.73 |

PARTIAL P95：FAUST NN8.48/BODY3.82/INTRINSIC26.18/DUAL12.06；SCAPE20.43/16.07/21.75/18.85。DUAL不能因某一个初始化较好而升格：SCAPE三个初始化约7.87/5.99/9.26，整体8.07；BODY约6.97/6.34/8.22，整体7.17。全部初始化在COMPARISON_RESULTS保留。

## 判断

1. 身体位置分支比新非学习坐标控制更好，但跨SCAPE仍明显退化，未解决可靠身份定位。
2. 局部训练比冻结几何模型在部分跨库读数上好，但仍弱于BODY。不是继续加曲面特征就能改善。
3. DUAL同时伤害中位与尾部，当前“几何＋位置concat”架构不采用。它不能作为已成立论文贡献，不继续在SCAPE上加轮数/换权重。
4. BODY仅进入离线MHR接口作诊断，不升级默认。注册作者对应、oracle后背ROI、完整身体归一化、作者初始化已见开发来源这些限定仍在；没有临床结论。

非学习控制在训练开始后、正式网络考试前独立登记；见BASELINE_ADDENDUM。没有修改已冻结训练代码/损失/超参数，不能说它属于最初预注册。BODY与几何分支也不是相同预训练资源比较。

## 交付

[协议](PROTOCOL.md)、[结构图](MODEL_ARCHITECTURE.png)、[方法方向](METHOD_DIRECTION.md)、[配置](CONFIG.json)、[源hash](SOURCE_FREEZE.json)、[720新/362复用算子](OPERATOR_MANIFEST.json)、三份TRAINING_LEDGER、[网络原始全量](RESULTS.json)、[控制原始全量](BASELINE_RESULTS.json)、[完整对照与初始化](COMPARISON_RESULTS.json)、[40图](figures)、[缓存复算](CACHE_REPLAY.json)。

服务器 `/raid5/xuhd/datasets/registered_human_correspondence_20261005/body_intrinsic_query_v1`；代码run_learning prepare/train/evaluate及分析脚本。数据、算子、权重和原扫描预测缓存留服务器；Git交全部逐case指标及实际路径/hash。沿用原模型环境，没有修改SAM环境依赖。
