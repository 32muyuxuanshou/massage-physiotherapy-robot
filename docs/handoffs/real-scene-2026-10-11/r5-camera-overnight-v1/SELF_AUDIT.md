# 完成后的自审

|检查|实际证据|结果|
|---|---|---|
|原生数据及封存|TRAIN3,200/VAL400导出；身份角色索引；导出器拒绝TEST|PASS；TEST未读取|
|扫描数据|3,072冻结Official缓存；TRAIN/VAL分开；扫描中心不充当MHR root|PASS|
|Body硬隔离|正向preflight；重开15×232实际NPZ，与compact源比较12个Body字段|PASS；见SAVED_OUTPUT_AUDIT.json|
|相机空间输出与一次Txyz|实际vertices=Body+Camera；校正前后顶点/Camera差仅applied translation|PASS；实际文件检查，容差1e-6m|
|Txyz历史合同|原评价器/fit_txyz；原anchor/A采样；232帧raw平移、fallback、B指标对历史逐帧比较|PASS；OFFICIAL_REPRODUCTION_GATE.json|
|扫描损失|原nvdiffrast，解析透视Z/梯度QA；TRAIN固定权重|PASS；WEAK_SUPERVISION_FREEZE.json|
|对照公平性|每seed相同父last、native RNG、学习率日程、更新次数；逐epoch native order SHA相同|PASS；MATCHED_CONTINUATION_AUDIT.json；scan额外计算公开|
|checkpoint选择|native VAL Camera L2；B及scan VAL不回流|PASS；各EXECUTION_IDENTITY.json|
|真实完整性|15组每组232帧；18TRAIN身份＋4VAL身份；全量逐帧/逐人输出|PASS；3,480记录，不删除坏例|
|Depth消融|9个checkpoint×11条件×400 native VAL；固定RGB/rays/有效性；缺Depth精确Official|执行完成；只说明Camera响应，Body固定不称新Body发现|
|图来自实际结果|12扫描＋81真实；原K透视z-buffer；显示固定历史16帧＋全部11fallback、3seed|PASS；已查看p001195与p001196及固定扫描样本|
|备份|GPU包128,785,261字节；真实评价包6,016,568,299字节；218与本地同SHA|PASS；两个BACKUP_RECEIPT|
|旧错误结果|恒定特征归一化造成数米异常；按TRAIN恒定通道修复；native3,600输出不变|修复完成，原始unmasked checkpoint/结果保留，不混入主表|

本轮没有追加庞大测试套件。结构QA、真实主执行路径、数值基线复现和实际缓存核验足以确认这次对照完成；它们不等于最终工程精度合格。

结果否定的是**当前Camera小头替换Official＋Txyz的主张**，不是所有RGB-D方法。native Camera GT、scan clothed Z、真实B点到三角面是三种评价，不互相换单位或合并成一个精度。真实数据已消费；仅4个VAL身份，不能据此声称泛化/统计显著/临床可用。后背region仍是历史proxy，未当椎体或穴位真值。

完整训练状态留在GPU核验包；原始数据/授权权重不上Git。218保留开启，AutoDL在全部GPU任务完成及备份核验后执行关机。所有计划任务提前完成，不再空转GPU或为排程时间追加训练。
