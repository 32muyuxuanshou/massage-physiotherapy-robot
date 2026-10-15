# Fine 负收益与逐 Query 重放

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run / analysis
- Origin Date: 2026-10-15 Asia/Shanghai
- Verification Status: COMPLETE；迁移、GPU Query重放、Native表面对照与完整性核验已完成
- Version Label: fine_negative_update_audit_v1

## 目标与边界

继续 `acb9f0a6`：区分 Fine 负收益的方向、平行过冲、正交分量，并读取实际256个 Query 的残差、局部深度变化和池化贡献。只做诊断，不训练、不改网络、不新增 Gate，不使用封存 Native/HuMMan TEST。

沿用 Native VAL400、HuMMan TRAIN192/VAL40、既有 BEHAVE270及 seeds11/23/37。原误差与坏帧标签保持原报告值；没有用新 GPU 输出重算或替换正式分数。

## 迁移执行

用户已授权优先使用 `172.18.6.218:436` 的8张2080Ti。独立环境位于 `/raid5/xuhd/rgbd_sam3d/runtime218/env`；工作根 `/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1`。

恢复原有 SHA 核验备份中的 Native VAL400和HuMMan232缓存；直连SFTP补传BEHAVE的810个缓存。1,442个实际文件共15,344,760,005字节，迁移后逐文件SHA通过。原数据、权重及AutoDL无卡实例均保留，未经过FlClash。

旧驱动510.54/CentOS7不直接复制AutoDL环境。建立Python3.10、PyTorch2.5.1+cu118及原nvdiffrast0.4.0源码编译环境。原模型和渲染Python源文件与checkpoint内训练SHA相同；原三个Full Last checkpoint SHA相同。

## 分析合同

1. Native 用精确恒等式拆分：`E_final²-E_coarse²=||delta||²-2 delta·(t_GT-t_coarse)`。只对原生Camera真值作方向归因；真实表面误差不冒充Camera真值。
2. 分开报告负收益中的反向、平行分量本身已过冲、正交分量抵消平行收益。保留所有帧，不能只比较数量不看损失幅度。
3. Native 固定半步与完美停手仅为离线算术反事实：后者使用真值在Coarse/Final中二选一，不是可部署Gate，不是全局最优定位上限。
4. Query 重放使用冻结模型实际local-MLP输入的观察Hook，记录 query/measured/residual/normal/ray/grid/observed、5×5邻域深度及max-pool通道归属，不修改参数。
5. 首批11条跨数据集/seed原样重放通过后启动三卡。全量发现两个边界例：小于微米量级的Coarse差异可改变离散可见Query。为恢复原Fine输入，另在独立目录固定历史Coarse中间值重放；这是诊断条件，不是新模型或新主分数。
6. 坐标重放误差阈值固定为0.0001m；法线特征值阈值0.0001为无量纲，二者分别记录。Query数不匹配或未达到数值标准的帧单列，不用于主要残差关联，不从原误差统计删除。原逐点mask没存，计数匹配不能单独证明历史逐点身份完全一致。
7. 统计为描述性、按数据/角色/seed分开。坏帧按误差选出，与起点误差存在数学耦合；组差异不是因果。禁止用Camera B拟合门控、调阈值或选checkpoint。
8. 为避免把Native Camera负收益误当表面负收益，补算固定Native VAL的可见表面对照：原始K、clean GT person mask、相同冻结身体与历史Coarse/Final平移；同时报告full-mask轴向Z median/P95、双方共同命中、命中率与轮廓IoU。无命中保持零深度并计入full-mask，不能只报有利交集。此为新增诊断指标，不能替换历史主分数，不读取真实Camera B。

## 结束条件

交付迁移回执、环境和GPU解析QA、完整分类、逐Query私有缓存、所有重放差异、逐域统计、HTML及Git目录；新输出备份回Windows。完成本轮诊断后停止，不自动训练或关闭服务器。
