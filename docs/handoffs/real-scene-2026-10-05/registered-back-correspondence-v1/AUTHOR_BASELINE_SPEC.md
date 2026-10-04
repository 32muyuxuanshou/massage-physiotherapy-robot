# 作者强参考：DiffusionNet-HKS 完整几何上下文

作者仓库nmwsharp/diffusion-net，实际commit `b1019b049597711d10259ce28250f7dfc4335a2b`；使用作者faust_hks.pth，4-block/128-width、128维特征、128谱基、30维functional map、lambda0.001，不重新训练/调参。

输入模板000与每个080–099完整注册网格；按照作者normalization / spectral operators / feature extractor / functional-map→vertex-map流程。结果再按当前900case中的考试180份观测索引读取对应，并沿当前指标计算，作者特征不输入GT对应。vts仅用于评分。

它是**完整几何的上下文参考**：看得到模拟缺失/噪声以前完整扫描，不是同输入的局部baseline。其作者训练使用000–079（比本轮60训练多20），不据其与我们的差异断言架构优劣。主对照仍是相同局部输入的NN/三学习方法。

支持结果不能掺进原主结果JSON。单独输出AUTHOR_BASELINE_RESULTS.json、checkpoint SHA、源码commit、环境/算子cache和逐源结果。所有原始/带几何的缓存仅服务器。单位与主合同一致，非测地距离/毫米/穴位误差。
