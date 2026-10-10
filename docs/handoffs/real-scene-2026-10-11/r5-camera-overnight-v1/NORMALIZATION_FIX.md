# TRAIN恒定特征修正

首次原生GT训练后的真实评价发现异常：公制XYZ seed11的VAL表面距离约5.65m，全部232帧Txyz回退。Official＋Txyz仍精确复现11.22625/41.60429mm，评价链没有为新模型改口径。

实际检查：native TRAIN normalized principal point两通道15/16均为0.5，真实输入约0.4976/0.5118。旧std floor1e-4将差值放大成−24.34/+118.27；这两个常量通道在native训练从未产生输入变化。不能把未训练的权重对这种放大的响应当成正确相机估计。

修法只由TRAIN min==max确定：常量通道的归一化值恒定为零。没有拿B拟合、调权重或选择mask。对全部3,600张native，旧归一化值本来就恰好为零，修正保持native输入/输出完全相同，9个模型无须重训；optimizer、Body和checkpoint选择不变。迁移脚本为18个best/last加入明确的metric_active buffer和父checkpoint SHA。

历史native目录改名native_v1_unmasked保留。首轮真实native__结果与修正版repaired__结果分开；首轮不再继续无效计算，已生成输出保留。AutoDL在修正前只做了渲染梯度QA，未训练，原QA保留为PRE_FIX_RASTER_QA_UNUSED；正式权重重新按同一固定TRAIN32+32协议计算。

这个修复关闭了已确认的常量特征数值放大问题，**不代表已经解决近距、纹理、姿态等合成到真实差异**。修正版真实结果仍须完整评价。
