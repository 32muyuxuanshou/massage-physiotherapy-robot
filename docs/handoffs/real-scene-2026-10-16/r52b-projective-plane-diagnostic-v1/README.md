# R5.2b：投影点面求解补充验证

**已完成零训练全量实验、复核与两端实际SHA备份。不进入学习权重训练。**

Gemini建议先做验证是对的；“两种强组件组合必胜”“已找到Fine唯一病因”“能确定精确上限”都不成立。本轮主配对直接否定了点面求解普遍优于中位数的说法。

|方法|HuMMan TRAIN median/P95 mm|HuMMan VAL median/P95 mm|BEHAVE median/P95 mm|
|---|---:|---:|---:|
|原Full Last Fine|20.524 / 76.648|14.359 / 44.550|19.827 / 83.583|
|Official＋历史Txyz|24.645 / 80.317|11.226 / 41.604|16.524 / 78.497|
|投影中位数3步，256候选|22.821 / 80.599|12.382 / 43.772|17.761 / 80.484|
|投影点面LS3步，256候选（预设主对照）|22.305 / 79.209|13.464 / 44.720|17.779 / 80.065|
|上述点面＋Huber|22.707 / 79.790|13.130 / 44.813|17.674 / 80.180|
|投影点面3步，1024候选|20.458 / 75.302|12.462 / 43.710|17.292 / 79.155|
|投影点面3步，4096候选|20.533 / 76.440|12.022 / 44.128|17.376 / 79.246|

表中为先frame→sequence→identity等权，再对3个seed求均值；BEHAVE先K1/K2/K3等权。不是合并所有点的总体median/P95。逐seed、SD、逐身份、所有18方法均在完整报告中。Official旧参考共用历史缓存，不是本轮重新做三次模型推理。

## 结论

- HuMMan VAL同条件3步，中位数换点面在三个seed均变差；BEHAVE median基本持平。不能把R5.2的“NN＋点面”收益直接搬到投影对应。
- 增加候选有帮助，但没有同时解决跨域和P95。Huber、方向衰减没有稳定带来尾部收益，6步常比2/3步更差并增加回退。
- Native 4096候选顶点误差83.321mm，低于Fine94.524mm；Camera参数误差却61.138mm，高于Fine20.610mm。更贴表面不等于真实参数更准。
- 当前可见性检查Mesh自遮挡，不等于识别了场景物体；法线来自预测Mesh，不能叫“绝对可靠法向距离”。法线矩阵也没有普遍缺秩，点少不是已经证实的唯一原因。
- **保留原R5与经典几何基线，停止追加同类求解配置。** 这轮不支持直接训练逐点权重。回到实际后背工作区域、固定拓扑工程点和独立观测来决定后续方法，不以全身贴合替代穴位精度。

## 完整审查入口

- [直观HTML：全部方法、每seed、图与分析](reports/R52B_投影点面验证.html)；本地可直接打开同名HTML，图在相同reports目录。
- [最终全表](reports/FINAL_REPORT.md) · [分析与已知失败身份](reports/ANALYSIS.md) · [自审](reports/SELF_AUDIT.md)
- [逐seed/逐身份层级汇总](reports/RESULTS.json) · [48708条逐帧CSV](reports/ALL_FRAMES.csv) · [逐帧JSON](reports/FRAME_RESULTS.json)
- [预设配对](reports/PAIRED_CONTRASTS.json) · [负收益转移](reports/NEGATIVE_UPDATE_TRANSFERS.csv) · [原fallback/失败身份](reports/KNOWN_FAILURES.json) · [部位proxy结果](reports/REGION_RESULTS.json)
- [实际Query数量、法线谱、条件数](reports/QUERY_DIAGNOSTICS.json) · [B端案例选择](reports/FIGURE_SELECTION.json) · [结论记录](reports/CONCLUSION.json)
- [执行合同](code/EXPERIMENT.json) · [执行/复现说明](code/REPRODUCE.md) · [全部代码](code)
- [预执行冻结](evidence/EXECUTION_FREEZE.json) · [全量旧参考复现](evidence/REFERENCE_REPRODUCTION_FULL.json) · [最终实际文件检查](evidence/POST_INTEGRITY.json) · [备份回执](evidence/BACKUP_RECEIPT_final.json)

## 本轮范围与实际检查

Native VAL400帧/50身份、HuMMan TRAIN192帧/18人及VAL40帧/4人、BEHAVE270帧/3人/90序列；三个父模型seed11/23/37，共2706状态、18方法、48708方法记录、216汇总。没有新增训练、没有读封存Native/HuMMan TEST、没有新增Scan或PressurePose评价；BEHAVE是已消费子集。

只用A拟合，只改translation；各步重新投影/可见性。20%欧氏截断，Huber固定20mm与3次IRLS，方向衰减独立成组；固定嵌套256/1024/4096候选。每轴50mm、总177.88820176363325mm上限，超限回原Coarse，原Fine参考保持不变。

首批15状态通过，10824条四项旧参考数值最大差异0；14181个实际文件检查通过；三域缓存复算通过。约42.7分钟完成主执行，含GPU求解、CPU独立评价与完整性检查，不是端到端模型延迟。

实际修正过一个执行衔接问题：全量fit重写了包含耗时的JSON，15帧先导评价仍链接旧hash。已保留先导输出并原样重评这15帧，[回执](evidence/REFRESH_PILOT_EVALUATION.json)。原执行入口`run.py`逐字节保留；未来复跑入口`run_reproduction.py`仅隔离先导缓存。后者静态/目录衔接检查通过，未另跑第二轮全量。没有改科学算子或评价器。

Git局部`.gitattributes`保持原执行文件的LF/CRLF字节，避免Git换行转换破坏runtime SHA。`FILES_MANIFEST.json`以实际Git index blob逐项计算，自身除外。预执行科学代码和后加报告工具的身份边界见执行冻结及复现说明。

## 存储与备份

- 218计算/完整目录：`/raid5/xuhd/rgbd_sam3d/r52b_projective_plane_diagnostic_v1`
- Windows：`E:/项目-按摩理疗机器人/output/r52b_projective_plane_diagnostic_v1`
- 完整私有卷：`R52B_PROJECTIVE_DIAGNOSTIC.tar.gz`，**1171248009 bytes、12451文件**。
- 218/Windows实际SHA一致：`94db66abf8bb419e6e6a4a2fc531e3939181ed08eb3acd42ce4e967ee6b96df4`。
- 旧G几何/GT/B点依赖原已备份`R5_FOCUSED_GEOMETRY.tar`，SHA `8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36`。新卷包含A输入、最终Body/Camera、轨迹、逐点评价、图表、代码与先导证据；不重复打包原ViT特征。新缓存复算无需主干网络。

直连SFTP，不经FlClash；凭据不入Git。原始数据/权重/大NPZ不入Git。服务器保持开启，没有新增付费实例。

## 证据边界

Native为对应顶点和Camera参数误差；真实域主证据是固定独立深度点到预测三角面的距离；BEHAVE拟合SMPL PVE只是支持证据。更低分不能证明解剖对应、皮肤表面或穴位更准。未新增RGB IoU或完整推理耗时。既有开发证据多次消费，本轮不是全新确认性测试。

[KinectFusion, ISMAR2011](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ismar2011.pdf)已采用投影关联与点面ICP。采用经典算子或改为可微层本身不等于新的论文贡献。
