# BEHAVE / R5 备份收尾

2026-10-14（北京时间）。状态：**两卷备份完成，Windows 与 218 实际文件 SHA 一致；6 项运行资产和 24 个 checkpoint 的归档内容与冻结哈希完全相同。**

科学实验保持原结果：270 帧、30 个组合、8,100 条评价、1,620 张对照图与 1,620 组三维查看数据。没有追加训练、重选样本、过滤评价点或修改指标。

## 实际保存位置

|备份卷|实际字节数|内容|
|---|---:|---|
|`BEHAVE_R5_PRIVATE_DELIVERY.tar.gz`|8,561,981,134|所选原始序列、输入/参考/留出点、缓存预测与参数、残差、全部私有图及三维数据、执行代码/报告和冻结源码|
|`BEHAVE_R5_FROZEN_ASSETS.tar.gz`|1,634,457,508|6 项运行资产和 24 个 Best/Last checkpoint|

- Windows：`E:/项目-按摩理疗机器人/output/behave_model_comparison_v1/final/`。
- 218：`/raid5/xuhd/rgbd_sam3d/behave_model_comparison_v1/`。
- AutoDL 原始实验目录：`/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1/`，原始数据、权重和实验输出仍保留。

实验卷 SHA256：`82c89647a5daeb6d128e68d51119d9c709bde25f8adea62dc04d7612c5bad627`。

资产卷 SHA256：`44c8a2169506197af8d78d5c5fe8c75f6375c5777a51ca8e4bcc0d2ffc31bc3d`。

[传输回执](results/BACKUP_RECEIPT.json) · [独立实际文件核验](results/FINAL_BACKUP_VERIFICATION.json) · [归档内 30 个资产逐文件核验](results/FINAL_BACKUP_ASSET_INTEGRITY.json)。

## 备份范围与恢复说明

实验卷不保存可由原输入和 Official 重建的 `cache/**/*.pt` 特征缓存；核心权重单独位于资产卷，不能把实验卷当作已经包含权重。资产卷成员 `frozen_assets/<编号>_<文件名>` 与 `MODEL_ASSET_FREEZE.json` 中 assets、checkpoints 顺序对应，实际字节数及 SHA 已逐项验证。

实验卷在后续报告注释定稿之前生成；归档内报告不是最新 Git 文档的替代。恢复时同时保留本次 Git 交付的报告、回执和索引。代码、数值与回执进入 Git；原始图像、权重及大型 NPZ 不入库。

服务器关机曾中断实验卷下载，已从 4,282,384,384 字节续传；全卷 SHA 验证通过。随后修复 Windows `Path` 转换 Linux 路径的问题，复用已完成卷进入资产备份。这些仅是备份调度修复，没有重跑科学实验。

为腾出资产卷打包空间，仅在 Windows 和 218 的实验卷实际 SHA 均通过后，移除了 AutoDL 上重复生成的实验 tar.gz。原始数据、模型权重和实验目录没有删除。

私有查看入口保持 localhost + SSH：`http://127.0.0.1:8779/`；本轮没有关闭服务器或启动下一阶段研究。监控在本次 Git 补交成功后暂停。

结果解释仍以 [最终报告](FINAL_REPORT.md) 为准：R5 Last PVE 61.06 mm、Official+Txyz 56.24 mm；M³ 协议尚未匹配，污染观测支撑不能当作裸背或穴位精度。
