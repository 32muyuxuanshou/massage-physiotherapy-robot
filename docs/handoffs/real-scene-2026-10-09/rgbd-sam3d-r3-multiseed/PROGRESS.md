# R3 执行进度（2026-10-09 20:07，中国时间）

当前代码执行版本：`521b42ba`。本文件记录已完成的准备和运行状态，不是多 seed 最终结论。

| 阶段 | 当前事实 |
|---|---|
| 合成数据 | 已生成 500 个 MHR 参数身份 × 2 固定姿态 × 4 共享物理相机，共 4,000 张，NPZ 约 1.08 GiB |
| 身份划分 | TRAIN 400 / VAL 50 / TEST 50；TEST 像素未进入缓存、训练、评价或预览 |
| 几何 QA | 原生根旋转、固定姿态刚体关系通过；独立 K/Z 射线到三角面检查通过 |
| 合成特征缓存 | 3,600 张 TRAIN/VAL 已完成，保持官方 bfloat16 特征 |
| 真实特征缓存 | HuMMan TRAIN 192 / VAL 40 帧已完成，18 / 4 身份 |
| 独立相机点样本 | 232 帧 Camera B 各最多 2,048 点，索引提前固定并共享 |
| Official 真实起点 | 232 帧已完成推理与独立 Camera B 三角面评价 |
| 学习率对照 | 三个模型以 1e-4 并发运行，各已完成第 2 轮；之后对照 3e-4 |
| 正式多 seed | 学习率选择后自动启动：三模型 × seeds 11/23/37 × 30 轮，目前尚未开始 |
| 备份与结果归档 | 本地后台进程等待正式 checkpoint，执行本地 E 盘与 172.18.6.218 的复制/哈希核对；结果收集等待全轮完成 |

## 已可审查的文件

- `SYNTHETIC_DATA_MANIFEST.json`：全部 4,000 张数据的身份、姿态、相机与 SHA256；只含元数据。
- `preflight/IDENTITY_SPLIT_500.json`、`GEOMETRY_QA_4000_IMAGES.json`：身份参数与几何记录。
- `preflight/SYNTHETIC_CACHE_QA.json`、`REAL_CACHE_QA.json`：缓存前向数值等价与磁盘大小。
- `preflight/HELDOUT_POINTS_MANIFEST.json`、`SOURCE_POINT_INDICES.json.gz`：真实独立相机的来源 hash 与点索引，不含原始点坐标。
- `preflight/HUMMAN_OFFICIAL_DEVELOPMENT_BASELINE.json`：完整逐帧起点评价；TRAIN / VAL 分开，frame→sequence→identity 等权汇总。
- `data_preview/contact_01.jpg`、`contact_02.jpg`：预先固定的两个 TRAIN、两个 VAL 合成身份；没有 TEST 图。

## 真实起点的范围

Official 的 Camera B point→triangle：TRAIN 身份等权 frame-median 均值为 53.97 mm，VAL 为 30.59 mm。它们是这批开发帧、这套公共标定和固定点样本下的观测表面距离，不能称为穴位/皮肤的绝对精度，也不与先前不同样本的数字直接对比。

训练优化、共同学习率和最佳 checkpoint 都只使用合成 TRAIN/VAL。上述真实结果不参与学习率或 checkpoint 选择。三种模型谁更好、是否稳定利用 Depth，等待九次充分训练、Depth 消融和真实迁移结果一起回答。
