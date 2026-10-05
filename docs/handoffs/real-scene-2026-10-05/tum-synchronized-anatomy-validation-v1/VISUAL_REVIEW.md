# 全量图复核

2026-10-05实际查看以下全部9页，每组17病例（6＋6＋5），未根据结果筛图。

|类型|第1页|第2页|第3页|
|---|---|---|---|
|冻结模型|[external01](montages/external_01.jpg)|[external02](montages/external_02.jpg)|[external03](montages/external_03.jpg)|
|两参考|[references01](montages/references_01.jpg)|[references02](montages/references_02.jpg)|[references03](montages/references_03.jpg)|
|来源/坐标|[source01](montages/source_01.jpg)|[source02](montages/source_02.jpg)|[source03](montages/source_03.jpg)|

图例：红色为待考试CT代理，白色为预测（模型图叠三个初始化）；参考图青色T3/L2为输入，完全不进入成绩。表面颜色为实际皮肤光栅Y，不是RGB或完整CT。

实际观察：`000088AE`有序网络整组等级明显下移，虽然全部点贴面，身份位置失效。`103731`表面/代理明显弯曲，两参考只能解决端点和总跨度，不能恢复中间侧弯，因此比例基线仍约36.55 mm。`nGV6HRUZf3k`普通预测在中央聚集，比例基线改善但仍有剩余偏差。`00004296/0000ED7B`部分参考校准网络优于比例先验，保留这些反例。

前6例和末4例有NIfTI世界变换；中间7例明确标Export frame，不能以图形合理性宣称世界坐标已验证。来源图全部重新从公开输入缓存生成正确标签，不改变任何输入、目标或推理。
