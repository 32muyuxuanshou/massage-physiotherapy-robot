# 218迁移与Fine负收益诊断

状态：**迁移和本轮诊断完成；没有新训练。** 接续已推送的 `acb9f0a61195a0a7a7b5a45db513fe53432a9384`，本轮不修改原正式分数、模型、数据划分或评价阈值。

## 先看什么

- [中文HTML与完整表格](218迁移与Fine负收益诊断.html)
- [简明结论](FINAL_REPORT.md)
- [迁移逐文件回执](MIGRATION_RECEIPT.json)
- [新输出备份回执](BACKUP_RECEIPT.json)
- [结束时实际SHA检查](POST_INTEGRITY.json)
- [自审与限制](SELF_AUDIT.md)

## 迁到哪里，迁了什么

SSH：`xuhd@172.18.6.218:436`，8张2080Ti。本轮实际使用GPU 0/1/2，按seed 11/23/37并行。原AutoDL数据保留，两个服务器均未关闭，没有新租付费实例，没有经过FlClash。

工作根：`/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1`。

独立Python：`/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`。

|本轮输入|逻辑帧数|218实际缓存数|来源与用途|
|---|---:|---:|---|
|Native MHR VAL|400|400|已冻结合成VAL；Camera真值与clean深度诊断|
|HuMMan TRAIN/VAL|192/40|232|原开发集；原Camera B评价只用于结果标签，不进模型或拟合|
|BEHAVE|270|810|既有已消费子集，每seed一套实际缓存；不是全新泛化集|
|合计|902×3seed评价|1,442|实际文件15,344,760,005字节，逐个重新SHA通过|

此前已备份到218的Native/HuMMan缓存和原预测几何在218恢复；BEHAVE 810个缓存从AutoDL直连SFTP传入。三个原Full Last权重直接使用218已有备份，实际SHA匹配；不重新下载模型、不重新生成数据。

这次迁移的是**本轮需要的缓存、原预测、源码和权重依赖**，不是声明所有原始训练数据集均已搬完。完整Official RGB→Backbone→MHR原始输入链尚未在218验收。本轮验证范围是缓存Official Body/Backbone→原R5 Camera/Fine及原渲染器。

## 环境与重放

CentOS7/glibc2.17、驱动510.54；独立安装Python3.10、PyTorch2.5.1+cu118、原nvdiffrast0.4.0源码和CUDA11.8编译工具。不能直接复制AutoDL运行环境。[环境记录](ENVIRONMENT.json)、[包清单](ENVIRONMENT_PACKAGES.txt)、[四点透视深度解析QA](RENDERER_GPU_QA.json)均已保存。解析QA最大Z误差约1.22e-7m。

首批固定11条跨域/seed重放通过。全量原样重放发现浮点微差可改变少数离散可见Query，另在独立目录固定**历史Coarse中间值**恢复Fine上下文。原模型权重、模型/渲染源码未改；这是诊断条件，不是新架构或新主结果。

2,706条坐标重放均通过0.0001m标准；2,705条同时满足Query计数与无量纲法线特征值标准。一条BEHAVE seed23帧 `Date03_Sub03_tablesmall_move_t0025.000` 可见Query为44而历史为43，位置差0.0828mm，单列在[差异清单](ALL_REPLAY_MISMATCHES.json)。它没有从原分数/负收益数量中删掉，只不进入主要Query关联。原逐点mask未保存，因此通过计数/数值检查不能独立证明原逐点身份完全一致。

## 核心结果

1. Native每seed的67/68/72个Camera负收益，不主要等于“步子太大”：其中方向相反38/40/29，正交分量抵消Camera平行收益20/25/38，仅平行分量已过冲9/3/5。数学分解通过1,200条恒等式核查，**不是网络错误原因的因果证明**。
2. 当前Fine Native Camera三seed均值20.61mm；固定半步31.28mm。使用GT逐帧在Coarse/Final中二选一仅降到19.30mm。后者不是可部署门控，也不是可达到的表面精度上限。
3. **Camera变差不等于可见表面变差。** 同一批Native Camera负收益中，46/49/48帧的full-mask轴向深度median反而改善；40/43/45帧同时改善full-mask和共同命中median；其中34/40/41帧命中率和轮廓IoU也不下降。不能按Camera标签一律拦截。
4. HuMMan VAL与BEHAVE的坏更新组通常已经有较小的Query轴向残差；Native坏/未坏组都约61–62mm。残差方差、5×5局部深度跳变和max-pool通道集中度没有跨域统一规律。未证明飞点/衣褶/物体遮挡是共同主因。

详见[2706条分类](UPDATE_CLASSIFICATION.csv)、[逐Query特征与分域分seed统计](QUERY_AUDIT.json)、[1200条Native Camera/表面对照](NATIVE_CAMERA_SURFACE_TRADEOFF.json)。没有把Native Camera、HuMMan点到三角面距离、BEHAVE拟合参考PVE混成一个误差；Query残差也不是最终评价误差。

新增Native表面检查保留GT全mask，并同时报告共同命中误差、命中率和IoU。未命中渲染为零，full-mask P95因此含数米漏覆盖惩罚，**不能读成命中表面的毫米精度**。这是可见全身合成诊断，不是俯卧背部或穴位精度。

## 如何复查

`code/`含完整本轮脚本和两个实际冻结历史模块。原几何、输入来源与各自SHA见迁移/完整性回执；大型输入和权重不入Git。

实际GPU重放入口（分别设置GPU 0/1/2及seed 11/23/37）：

```bash
export LD_LIBRARY_PATH=/raid5/xuhd/rgbd_sam3d/runtime218/env/lib:${LD_LIBRARY_PATH:-}
export CUDA_VISIBLE_DEVICES=0
/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python -u \
  /raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1/code/replay_queries218.py \
  --seed 11 --frozen-coarse
```

Native表面对照入口：`code/native_surface_tradeoff218.py --seed 11`；另两seed相同。聚合与HTML入口分别为`code/summarize_surface_tradeoff.py --root <本轮输出根>`、`code/build_report.py --root <本轮输出根>`。这些命令说明已执行路径，当前任务已完成，不需要重新启动。

私有新输出包：218工作根下 `FINE_QUERY_DIAGNOSTICS.tar.gz`，109,478,494字节，SHA256 `95527cdba8e78047543ecf4d3eb50b0de0e788c08b2291ef2d7ec9f388696f3f`。Windows副本位于 `E:/项目-按摩理疗机器人/output/r5_fine_negative_update_audit_v1/`，实际SHA一致。包含2,706组主要Query NPZ、所有先前重放尝试、Native表面对照、代码、日志与回执；不重复打包15.34GB原缓存、环境和已有权重。

## 当前决策

本轮结束，不自动训练R5.1或增加旋转/展开模块。下一项应分别验证Camera参数监督与可见表面目标的取舍；现有结果不支持直接靠“残差方差大就关闭Fine”解决问题。完整SAM3D端到端速度/显存、封存TEST、真实俯卧裸背和穴位验证均未由本轮完成。
