# 可视化入口

全部从实际缓存Mesh生成；没有重新拟合，没有生成式图片。青色人体是预测Mesh，不是真值。真实图下排是固定Camera B点到Mesh的距离，颜色统一截断150mm。

## 扫描VAL：固定12例

|身份/样本|对照图|
|---|---|
|p000460_a000064_000042_c08_l0|[RGB / Official / native / mixed](visualizations/p000460_a000064_000042_c08_l0.jpg)|
|p000460_a000064_000042_c24_l0|[RGB / Official / native / mixed](visualizations/p000460_a000064_000042_c24_l0.jpg)|
|p000460_a000064_000042_c40_l0|[RGB / Official / native / mixed](visualizations/p000460_a000064_000042_c40_l0.jpg)|
|p000460_a000064_000042_c56_l0|[RGB / Official / native / mixed](visualizations/p000460_a000064_000042_c56_l0.jpg)|
|p000495_a000093_000030_c08_l0|[RGB / Official / native / mixed](visualizations/p000495_a000093_000030_c08_l0.jpg)|
|p000495_a000093_000030_c24_l0|[RGB / Official / native / mixed](visualizations/p000495_a000093_000030_c24_l0.jpg)|
|p000495_a000093_000030_c40_l0|[RGB / Official / native / mixed](visualizations/p000495_a000093_000030_c40_l0.jpg)|
|p000495_a000093_000030_c56_l0|[RGB / Official / native / mixed](visualizations/p000495_a000093_000030_c56_l0.jpg)|
|p000526_a000150_000018_c08_l0|[RGB / Official / native / mixed](visualizations/p000526_a000150_000018_c08_l0.jpg)|
|p000526_a000150_000018_c24_l0|[RGB / Official / native / mixed](visualizations/p000526_a000150_000018_c24_l0.jpg)|
|p000526_a000150_000018_c40_l0|[RGB / Official / native / mixed](visualizations/p000526_a000150_000018_c40_l0.jpg)|
|p000526_a000150_000018_c56_l0|[RGB / Official / native / mixed](visualizations/p000526_a000150_000018_c56_l0.jpg)|

## 真实开发集：27帧×3seed

历史16帧及全部11个Official Txyz fallback。保留各seed，不按效果挑选。

|帧|seed11|seed23|seed37|
|---|---|---|---|
|p001194_a000062_000005|[对照](real_visualizations/p001194_a000062_000005_s11.jpg)|[对照](real_visualizations/p001194_a000062_000005_s23.jpg)|[对照](real_visualizations/p001194_a000062_000005_s37.jpg)|
|p001195_a000053_000006|[对照](real_visualizations/p001195_a000053_000006_s11.jpg)|[对照](real_visualizations/p001195_a000053_000006_s23.jpg)|[对照](real_visualizations/p001195_a000053_000006_s37.jpg)|
|p001195_a000053_000021|[对照](real_visualizations/p001195_a000053_000021_s11.jpg)|[对照](real_visualizations/p001195_a000053_000021_s23.jpg)|[对照](real_visualizations/p001195_a000053_000021_s37.jpg)|
|p001195_a000053_000037|[对照](real_visualizations/p001195_a000053_000037_s11.jpg)|[对照](real_visualizations/p001195_a000053_000037_s23.jpg)|[对照](real_visualizations/p001195_a000053_000037_s37.jpg)|
|p001195_a000053_000052|[对照](real_visualizations/p001195_a000053_000052_s11.jpg)|[对照](real_visualizations/p001195_a000053_000052_s23.jpg)|[对照](real_visualizations/p001195_a000053_000052_s37.jpg)|
|p001195_a000053_000068|[对照](real_visualizations/p001195_a000053_000068_s11.jpg)|[对照](real_visualizations/p001195_a000053_000068_s23.jpg)|[对照](real_visualizations/p001195_a000053_000068_s37.jpg)|
|p001195_a000053_000083|[对照](real_visualizations/p001195_a000053_000083_s11.jpg)|[对照](real_visualizations/p001195_a000053_000083_s23.jpg)|[对照](real_visualizations/p001195_a000053_000083_s37.jpg)|
|p001195_a000053_000114|[对照](real_visualizations/p001195_a000053_000114_s11.jpg)|[对照](real_visualizations/p001195_a000053_000114_s23.jpg)|[对照](real_visualizations/p001195_a000053_000114_s37.jpg)|
|p001195_a000986_000011|[对照](real_visualizations/p001195_a000986_000011_s11.jpg)|[对照](real_visualizations/p001195_a000986_000011_s23.jpg)|[对照](real_visualizations/p001195_a000986_000011_s37.jpg)|
|p001195_a000986_000096|[对照](real_visualizations/p001195_a000986_000096_s11.jpg)|[对照](real_visualizations/p001195_a000986_000096_s23.jpg)|[对照](real_visualizations/p001195_a000986_000096_s37.jpg)|
|p001195_a000986_000182|[对照](real_visualizations/p001195_a000986_000182_s11.jpg)|[对照](real_visualizations/p001195_a000986_000182_s23.jpg)|[对照](real_visualizations/p001195_a000986_000182_s37.jpg)|
|p001195_a000986_000210|[对照](real_visualizations/p001195_a000986_000210_s11.jpg)|[对照](real_visualizations/p001195_a000986_000210_s23.jpg)|[对照](real_visualizations/p001195_a000986_000210_s37.jpg)|
|p001196_a000388_000011|[对照](real_visualizations/p001196_a000388_000011_s11.jpg)|[对照](real_visualizations/p001196_a000388_000011_s23.jpg)|[对照](real_visualizations/p001196_a000388_000011_s37.jpg)|
|p001196_a000388_000040|[对照](real_visualizations/p001196_a000388_000040_s11.jpg)|[对照](real_visualizations/p001196_a000388_000040_s23.jpg)|[对照](real_visualizations/p001196_a000388_000040_s37.jpg)|
|p001196_a000388_000069|[对照](real_visualizations/p001196_a000388_000069_s11.jpg)|[对照](real_visualizations/p001196_a000388_000069_s23.jpg)|[对照](real_visualizations/p001196_a000388_000069_s37.jpg)|
|p001196_a000388_000098|[对照](real_visualizations/p001196_a000388_000098_s11.jpg)|[对照](real_visualizations/p001196_a000388_000098_s23.jpg)|[对照](real_visualizations/p001196_a000388_000098_s37.jpg)|
|p001196_a000388_000127|[对照](real_visualizations/p001196_a000388_000127_s11.jpg)|[对照](real_visualizations/p001196_a000388_000127_s23.jpg)|[对照](real_visualizations/p001196_a000388_000127_s37.jpg)|
|p001196_a000388_000156|[对照](real_visualizations/p001196_a000388_000156_s11.jpg)|[对照](real_visualizations/p001196_a000388_000156_s23.jpg)|[对照](real_visualizations/p001196_a000388_000156_s37.jpg)|
|p001196_a000388_000185|[对照](real_visualizations/p001196_a000388_000185_s11.jpg)|[对照](real_visualizations/p001196_a000388_000185_s23.jpg)|[对照](real_visualizations/p001196_a000388_000185_s37.jpg)|
|p001196_a000388_000214|[对照](real_visualizations/p001196_a000388_000214_s11.jpg)|[对照](real_visualizations/p001196_a000388_000214_s23.jpg)|[对照](real_visualizations/p001196_a000388_000214_s37.jpg)|
|p001199_a001398_000001|[对照](real_visualizations/p001199_a001398_000001_s11.jpg)|[对照](real_visualizations/p001199_a001398_000001_s23.jpg)|[对照](real_visualizations/p001199_a001398_000001_s37.jpg)|
|p001202_a001230_000021|[对照](real_visualizations/p001202_a001230_000021_s11.jpg)|[对照](real_visualizations/p001202_a001230_000021_s23.jpg)|[对照](real_visualizations/p001202_a001230_000021_s37.jpg)|
|p001202_a001230_000028|[对照](real_visualizations/p001202_a001230_000028_s11.jpg)|[对照](real_visualizations/p001202_a001230_000028_s23.jpg)|[对照](real_visualizations/p001202_a001230_000028_s37.jpg)|
|p001202_a001230_000040|[对照](real_visualizations/p001202_a001230_000040_s11.jpg)|[对照](real_visualizations/p001202_a001230_000040_s23.jpg)|[对照](real_visualizations/p001202_a001230_000040_s37.jpg)|
|p100069_a005191_000006|[对照](real_visualizations/p100069_a005191_000006_s11.jpg)|[对照](real_visualizations/p100069_a005191_000006_s23.jpg)|[对照](real_visualizations/p100069_a005191_000006_s37.jpg)|
|p100072_a001242_000048|[对照](real_visualizations/p100072_a001242_000048_s11.jpg)|[对照](real_visualizations/p100072_a001242_000048_s23.jpg)|[对照](real_visualizations/p100072_a001242_000048_s37.jpg)|
|p100072_a001242_000063|[对照](real_visualizations/p100072_a001242_000063_s11.jpg)|[对照](real_visualizations/p100072_a001242_000063_s23.jpg)|[对照](real_visualizations/p100072_a001242_000063_s37.jpg)|

## 汇总图

- [原生训练曲线](summary/NATIVE_TRAINING_CURVES.png)
- [匹配续训曲线](summary/CONTINUATION_CURVES.png)
- [真实VAL对照](summary/REAL_VAL_COMPARISON.png)
- [全部22身份P95变化](summary/ALL_IDENTITY_P95.png)

扫描与真实各自的VISUALIZATION_MANIFEST.json保存样本、seed、选择来源和显示合同。原始RGB/大Mesh缓存属于私有资产。
