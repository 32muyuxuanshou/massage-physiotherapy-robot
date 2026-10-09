# 可视化索引

绿色是预测 Mesh 的投影轮廓，紫色是同一预测 Mesh 的填充；都不是人体真值。下排是独立 Camera B 的测量点，用实际点到预测三角面的距离着色。0–150 mm 固定色标。

这16个展示案例包括14个预先选定失败及2个其他 VAL 身份；总体结论使用全部232帧，不以展示样本均值代替。上轮30-epoch失败分析图另在 `failure_visuals`，不能把它与本轮8-epoch图混用。

| 身份/帧 | 角色 | 来源 | 六组对照图 |
|---|---|---|---|
| p001196_a000388 / 11 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000011.jpg) |
| p001196_a000388 / 40 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000040.jpg) |
| p001196_a000388 / 69 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000069.jpg) |
| p001196_a000388 / 98 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000098.jpg) |
| p001196_a000388 / 127 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000127.jpg) |
| p001196_a000388 / 156 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000156.jpg) |
| p001196_a000388 / 185 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000185.jpg) |
| p001196_a000388 / 214 | VAL | R3 prespecified failure | [打开](pilot_visuals/p001196_a000388_000214.jpg) |
| p100072_a001242 / 48 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p100072_a001242_000048.jpg) |
| p100072_a001242 / 63 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p100072_a001242_000063.jpg) |
| p001202_a001230 / 21 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p001202_a001230_000021.jpg) |
| p001202_a001230 / 40 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p001202_a001230_000040.jpg) |
| p100069_a005191 / 6 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p100069_a005191_000006.jpg) |
| p001202_a001230 / 28 | TRAIN | R3 prespecified failure | [打开](pilot_visuals/p001202_a001230_000028.jpg) |
| p001194_a000062 / 5 | VAL | first other VAL identity | [打开](pilot_visuals/p001194_a000062_000005.jpg) |
| p001199_a001398 / 1 | VAL | first other VAL identity | [打开](pilot_visuals/p001199_a001398_000001.jpg) |
