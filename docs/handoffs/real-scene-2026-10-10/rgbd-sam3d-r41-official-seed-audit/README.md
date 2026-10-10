# Official＋Txyz：11/23/37 三种子重复检查

2026-10-10。基于已交付的 R4.1，在本地 CPU 实际重新运行三组 **232 帧 Txyz＋Camera B 精确评价**，合计 696 条重复评价，耗时 55.33 秒。没有重训、没有重新运行 Official GPU 网络，也没有重新抽取点云。

**结果：三个 seed 的全部平移、六步迭代、fallback、最终网格和 2,048 个逐点距离与 R4.1 原记录完全相同。此固定缓存几何合同下，seed 波动为 0。**

## seed 控制的是什么

- G0/G1 的 11/23/37 是**训练 seed**：影响模块初始化、训练顺序等，最终是三个不同 Best checkpoint。它们的结果波动确实存在，应保留并报告。
- Official 是**同一份冻结官方 checkpoint**，没有在本项目中进行三种子训练。
- 本次给每次任务实际设置 Python/NumPy 的 11/23/37；Txyz 直接复用既有函数，固定 16,384 Anchor、最多 5,000 个 A 点及 2,048 个 B 评价点。该函数不调用随机采样，所以改变全局 seed 不改变输出。
- 这证明的是**缓存几何算法的重复性**，不证明重新运行 GPU 的网络一定逐位一致，也不证明更换点云采样后没有波动。三次重复不能当作三份独立训练模型或扩大样本量。

## 实际结果

保持 frame → sequence → identity 等权汇总；没有重新选择帧或移除失败。

|Official＋Txyz 重复 seed|TRAIN median / P95 mm|VAL median / P95 mm|fallback TRAIN / VAL|
|---|---:|---:|---:|
|11|24.645038 / 80.316764|11.226247 / 41.604292|11 / 0|
|23|24.645038 / 80.316764|11.226247 / 41.604292|11 / 0|
|37|24.645038 / 80.316764|11.226247 / 41.604292|11 / 0|
|重复样本 SD|0 / 0|0 / 0|—|

|seed|Official＋Txyz VAL median / P95 mm|G0＋Txyz VAL median / P95 mm|G1＋Txyz VAL median / P95 mm|
|---|---:|---:|---:|
|11|11.23 / 41.60|12.12 / 43.06|19.26 / 97.27|
|23|11.23 / 41.60|14.61 / 51.77|12.47 / 47.70|
|37|11.23 / 41.60|20.53 / 58.99|14.98 / 60.95|

每组 seed 都与同一个稳定的 Official 基线配对。**补充重复检查后，G1 在 VAL 未稳定超过 Official＋Txyz 的结论不变。**训练波动与点云采样波动必须分开：若以后研究后者，所有方法应共享每个采样 seed 的 A 点和 Anchor，B 评价点继续固定，并作为独立采样稳健性实验报告；本轮没有改动历史固定采样合同。

## 可审查文件与重放

- [全部 seed 的逐帧 trace、距离与网格一致性](PER_FRAME_SEED_CHECK.json)：696 条；所有最大误差均为 0。
- [汇总、22 身份逐人结果、源码 SHA 与 seed 波动](SEED_REPEAT_RESULTS.json)。
- [每个 seed 的 Official/G0/G1 TRAIN/VAL 对照表](COMPARISON_BY_SEED.csv)：18 行，明确区分重复 seed 与训练 seed。
- [执行脚本](check_r41_official_seeds.py)、[增量备份回执](BACKUP_RECEIPT.json)。
- 依赖：[原 R4.1 完整交付](../rgbd-sam3d-r41-fair-txyz/README.md)，源 commit `97afeae585528edfa0fd80d399bd0b9493c4ee54`。原始几何包与恢复步骤见其中 `REPRODUCE.md`，原报告、网格和点集未覆盖。

恢复原 R4.1 工作目录后，使用 Python 3.11、NumPy 2.4.6、SciPy 1.17.1：

```text
python check_r41_official_seeds.py --work R41_WORK --out NEW_OUTPUT --workers 6
```

脚本旁同时放置原交付 `code/run_r41_txyz.py`，供导入不变的历史数值函数。新输出目录必须不存在；结果与原 R4.1 每帧缓存精确比较，任一差异即中止。仅 Camera A 拟合，Camera B 在修正完成后才进入评价；TEST 未读。此次在本地完成，AutoDL 保持关机。
