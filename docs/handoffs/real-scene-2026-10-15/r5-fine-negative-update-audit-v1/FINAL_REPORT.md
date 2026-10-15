# 218迁移与Fine负收益诊断

本轮1,442个缓存文件共15,344,760,005字节全部实际SHA通过。Native VAL400、HuMMan232共享缓存，以及BEHAVE270×3seed缓存均已就位。原三个Full Last权重和训练源码SHA匹配，218三张2080Ti已实际运行；未训练、未关闭服务器、未经过FlClash。

2,706条Query重放完成，坐标数值全部在0.0001m范围；2,705条满足主要Query关联标准，一条BEHAVE Query计数差一个，完整保留并单列。为隔离Coarse浮点变化，Fine上下文使用冻结历史Coarse值；这不是新模型、不是新主分数。

Native每seed坏更新分解：

|seed|方向相反|正交分量抵消收益|平行分量本身过冲|总坏帧|
|---|---:|---:|---:|---:|
|11|38|20|9|67|
|23|40|25|3|68|
|37|29|38|5|72|

只缩小步长不够：Native固定半步Camera误差31.28mm，高于当前Fine的20.61mm。即使使用真值完美阻止所有Camera坏更新，在Coarse/Final二选一范围内也仅降到19.30mm，平均改善约1.31mm；不能把这个离线oracle当部署方法或表面精度上限。

关键补查：Camera变差不等于表面变差。

|seed|Camera变差帧|其中full-mask深度median改善|full-mask/共同命中median都改善|再要求命中率和IoU不下降|
|---|---:|---:|---:|---:|
|11|67|46|40|34|
|23|68|49|43|40|
|37|72|48|45|41|

这是新增Native clean GT轴向深度诊断，不替换历史主分数，不是俯卧后背或穴位精度。full-mask保留未命中零深度惩罚；完整结果同时保存共同命中误差、命中率、IoU与逐帧值。full-mask P95含数米漏覆盖惩罚，不是纯表面距离。不能按Camera误差上升直接抑制这些更新。

HuMMan VAL坏更新组Query轴向残差较小（约10–15mm），BEHAVE也有类似现象；Native坏/未坏两组均约61–62mm。残差方差、局部深度跳变和max-pool通道集中度没有统一跨域规律，不支持直接把异常点或衣褶当主要原因。

建议先验证Camera参数与可见表面监督的差异，保守门控作为独立对照，不直接按方差设计新架构或启动训练。全部统计为已消费数据上的描述性诊断；Native/HuMMan封存TEST未读取、Camera B未参与拟合，无新训练。BEHAVE仍是已消费的官方TEST子集，不能称全新测试集。

工作根：`/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1`。

Python：`/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`。

本轮仅重放缓存后的Camera/Fine，未测完整SAM3D端到端速度或显存。
