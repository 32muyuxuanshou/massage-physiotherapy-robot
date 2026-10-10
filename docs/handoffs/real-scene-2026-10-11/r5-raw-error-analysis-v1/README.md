# R5 新模型误差复盘：以不加 Txyz 的输出为主

**结论：新 Camera 头会救回一些位置错得很大的样本，但也会把原本较好的样本移错。当前不能替代 Official，更不能作为毫米级穴位定位模型。**本轮没有新训练；重读了全部缓存，重新汇总全部模型、身份与帧，并完成 CPU 特征敏感性诊断。

阅读顺序：

1. [通俗完整分析、训练是否充分、数据怎么用](ERROR_ANALYSIS.md)
2. [四名真实 VAL 受试者的主结果图](RAW_VAL_BY_IDENTITY.png)
3. [全部22名受试者的改善/恶化图](ALL_IDENTITY_RAW_CHANGES.png)
4. [训练收敛曲线](TRAINING_CONVERGENCE.png)
5. [真实与合成 Depth 输入的差异](VALID_DEPTH_DISTRIBUTION.png)

完整表格：

|文件|内容与数量|
|---|---|
|[MIXED_RAW_IDENTITIES.csv](MIXED_RAW_IDENTITIES.csv)|主新模型，3 seed × 22人＝66条；raw 为主，Txyz 单列诊断|
|[MIXED_RAW_FRAMES.csv](MIXED_RAW_FRAMES.csv)|主新模型，3 seed × 232帧＝696条；实际 Camera XYZ 变化|
|[MIXED_FRAME_REGIONS.csv](MIXED_FRAME_REGIONS.csv)|主新模型逐帧、逐部位对照，保留各区点数|
|[完整人表及模型数值附录](NUMERICAL_APPENDIX.md)|无需打开JSON即可阅读全部22人、全部模型、轮次和XYZ变化|
|[严重失败逐帧表](WORST_FRAMES.md)|每个seed、每个角色的10个最高P95帧，含实际XYZ变化|
|[ALL_REAL_IDENTITIES.csv](ALL_REAL_IDENTITIES.csv)|全部15个新模型 cell＋Official，共352条身份结果|
|[ALL_REAL_FRAMES.csv](ALL_REAL_FRAMES.csv)|全部15个新模型 cell＋Official，共3,712条帧结果|
|[ALL_REAL_MODELS.csv](ALL_REAL_MODELS.csv)|每个模型、每个开发角色的汇总|
|[ALL_REAL_REGIONS.csv](ALL_REAL_REGIONS.csv)|肩胸、躯干、腰、手臂等固定 proxy 分区；不是背部或解剖真值|
|[TRAINING_AUDIT.csv](TRAINING_AUDIT.csv)|15个训练 cell 的轮次、LR、loss、best/last、后期改善|
|[ALL_TRAINING_CURVES.csv](ALL_TRAINING_CURVES.csv)|全部390条实际训练轮次记录|
|[DATASET_IDENTITY_ROLES.csv](DATASET_IDENTITY_ROLES.csv)|所有已使用身份、数量、角色与用途|
|[DATASET_USAGE.json](DATASET_USAGE.json)|数据集、相机配置、源 Mesh 数量和身份划分|
|[SCAN_ACTUAL_EXPOSURE.json](SCAN_ACTUAL_EXPOSURE.json)|新纹理数据实际抽取次数与覆盖；20轮不是20遍 scan|
|[SYNTHETIC_TRUE_CAMERA_AXIS_ERRORS.json](SYNTHETIC_TRUE_CAMERA_AXIS_ERRORS.json)|有真实 root 标签的原生合成 VAL，三轴误差分解|
|[CAMERA_AXIS_BY_IDENTITY.json](CAMERA_AXIS_BY_IDENTITY.json)|真实数据实际位移、A 的 Txyz 诊断、两种初始化的最终位置差|
|[CACHE_CAMERA_AND_FEATURE_AUDIT.json](CACHE_CAMERA_AND_FEATURE_AUDIT.json)|重开3,480个实际 NPZ，12个 Body 字段一致性、特征分布与 SHA|
|[VALID_FRACTION_SENSITIVITY.json](VALID_FRACTION_SENSITIVITY.json)|CPU 单特征干预的逐帧 Camera 响应；不是新模型结果|
|[ANALYSIS_SUMMARY.json](ANALYSIS_SUMMARY.json)|种子均值/标准差、恶化数、各 seed 最差10帧|

实际缓存 Mesh 对照，全3 seed：

- [p001195：救回大位置偏差](p001195_a000053_000037_RAW_ALL_SEEDS.jpg)
- [p001196：原来较好，移动后变差](p001196_a000388_000011_RAW_ALL_SEEDS.jpg)
- [p100072：大残差与种子差异](p100072_a001242_000048_RAW_ALL_SEEDS.jpg)
- [p001202：相同 Body 被移错](p001202_a001230_000021_RAW_ALL_SEEDS.jpg)

上半部分是原始 K 下的透视 Mesh 叠图，蓝色是预测人体；下半部分是实际 A 点云与预测顶点的 Y-Z 正交诊断投影，**不是截面、不是 GT Mesh、不能冒充 RGB 透视叠图**。三维分数来自独立 Camera B，不用 A 的拟合分数替代。完整历史81张真实图仍见[原交付](../r5-camera-overnight-v1/VISUAL_INDEX.md)，本轮未删除失败帧。

代码：[`research/rgbd_sam3d_mhr/r5_camera_only`](../../../../research/rgbd_sam3d_mhr/r5_camera_only)。重算命令见 [REPRODUCE.md](REPRODUCE.md)。公开包不含 RGB-D 原始数据、权重或认证信息。
