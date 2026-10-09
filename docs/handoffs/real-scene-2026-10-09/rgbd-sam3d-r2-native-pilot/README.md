# 首轮原生 MHR RGB-D 合成训练：R2 pilot

**真实执行已完成；模型可训练，但这版 RGB-D 融合尚未胜过同数据 RGB-only 适配器。不能替换现有工程基线，也不能据此声称真人或俯卧收益。**

## 实际完成

- 同一 AutoDL RTX 6000D（约 84 GiB），完整 R1 native SAM→Fusion→MHR 前向/反向与冻结验证通过。
- 原生 MHR 32 个合成体型，24 TRAIN / 4 VAL / 4 TEST，每人 8 视角，共 256 张：192 训练、32 开发、32 测试暂不用于网络评价。身份的 shape/scale 在渲染前固定；全部视角跟随身份。
- 三个适配器：RGB-only、Depth spatial residual、Depth cross-attention；相同训练样本、顺序、seed=42、损失权重、8 轮、batch=1、AdamW。每组 1,536 步，总计 4,608 步。
- Official backbone/decoder/pose/camera/MHR 参数全部冻结，只训练新增适配器；每组结束逐值哈希核对 971 个官方参数未变。固定权重不意味着固定输出，融合改变输入后仍能改变 native pose/shape/scale/camera。
- 实际损失包含同拓扑顶点、关节、相机、pose/rotation、shape/scale/hand，以及可微透视 Z 和 silhouette。输出保持原生 18,439 顶点 / 36,874 面，没有自由顶点位移。
- 训练总耗时 1,161.59 秒（约 19.4 分钟），实际峰值显存见完整结果 JSON。统一交付末轮 checkpoint；全部轮次曲线保留，没有按开发/测试结果挑最好轮。

## 独立合成体型开发结果

先对每身份的 8 视角求平均，再对 4 身份等权平均。下表是 **native 对应顶点欧氏距离**，不是 PressurePose/BEHAVE 的点云→三角面距离，不能横向直接比较。

| 方法 | 相机坐标顶点平均误差 mm | 去整体平移后顶点误差 mm | Camera translation 误差 mm | Silhouette IoU |
|---|---:|---:|---:|---:|
| official | 110.02 | 38.06 | 124.67 | 93.07% |
| rgb_only | 43.97 | 25.84 | 43.23 | 94.37% |
| residual | 61.09 | 28.63 | 57.36 | 93.48% |
| cross_attention | 52.92 | 29.11 | 45.43 | 93.44% |

所有训练方法都改善了未适配 Official，但 RGB-only 更强。Cross-Attention 的绝对顶点误差为 52.92 mm，对照 43.97 mm；去平移后仍为 29.11 vs 25.84 mm。因此不能用相对 Official 的改善宣称融合结构优越。RGB-only、residual、cross-attention 分别有 656,897 / 863,873 / 1,454,977 个可训练参数，不声称参数量完全匹配；后续扩大对照要保留此差别或另做等容量对照。

## 最值得重视的 Depth 消融

| Cross-Attention 输入 | 绝对顶点平均误差 mm |
|---|---:|
| 正确 Depth | 52.92 |
| 循环错配 Depth（保留实际 RGB 相机 rays） | 51.79 |
| Depth 全部加 0.2 m | 52.93 |
| 缺失 Depth | 110.02（回到 Official） |

缺失 Depth 回到 Official 是设计保证，不能单独作为利用个体深度几何的证明。错配几乎不影响结果，+0.2 m 也几乎不影响误差，说明这版 Cross-Attention **尚未证明有效利用匹配的个体几何和绝对 Z**。非零梯度、输出受 Depth 影响是可训练证据，尚不等于学到了正确的几何。更像在学通用适配，但这只是当前消融支持的判断，不把内部原因说死。

轻量 residual 错配后从 61.09 变为 75.81 mm，说明配对内容在这一支更有影响；其正确输入仍未胜过 RGB-only。两个融合支路都不能算本轮方法成功。

## 相机、渲染与真值

- Native MHR raw cm→m 在官方 mhr_forward 内完成一次，然后采用官方 Y/Z 翻转。相机 translation 和 Depth 都是 m。
- 使用原始 640×480 RGB、K 与官方 crop affine；Depth/rays 复用同一 affine，得到 512×384 空间网格。没有把 Depth 每图压成 0–1。
- CV 像素中心采用整数坐标，在 OpenGL/Nvdiffrast viewport projection 中加半像素；RGB 渲染同样转换 principal point。合成 metric Depth 从 native 真值几何渲染，不用预测 Mesh 拟合相机。
- 斜三角面/平面透视 Z 解析检查最大差异 2.38e-7 m，反向梯度非零。与 pyrender 的独立光栅化检查共命中 median 0.594 mm、P95 2.814 mm，主要受边界/光栅化采样差异影响；这不是传感器精度证明。正式合成 Depth 来自已解析验证的统一 geometry renderer，RGB 采用简单材质 pyrender。
- 这批是几何训练阶段：小幅 pose、前/后视角与体型变化，没有衣物、床、遮挡、传感器噪声；不是“32 个真人”，更不是完整俯卧数据集。

## 真实数据准备进度

HuMMan-Point 的五个官方包已下载并核对 LFS SHA256；选取 28 身份 / 44 动作序列，Kinect000 输入、001 留出。身份 18 TRAIN / 4 VAL / 6 TEST 在查看模型结果前冻结。

已完成 352 个同步索引的纯数据读取/有效 Depth/官方标定注册准备，双相机共 704 个观察缓存。取共同 depth/mask frame IDs 的 5%–95% 时间分位数，每序列 8 帧。沒有按模型效果筛帧，没有丢弃失败的模型案例。

**目前仅完成数据 QA，没有对这些真人运行新模型推理、训练或最终测试。** 读取与注册成功不等于独立验证了相机/传感器的毫米精度。Depth 与 Mask 保持原始 depth domain，通过释放的相机 R/T 注册到 RGB；像素孔洞保持零，不用膨胀深度伪造观测。真人 RGB/Depth/点云只在服务器，不提交公开 Git。

## 复现、缓存、备份

训练源码冻结：`2366ca5ba95bc70561c6bc027872d1b490f52557`；LF Git archive SHA256 `b3cc0d88dcb1cd21d13c3618df3b6e5a9c60e12f251cd78322db2332d94268b3`。`R2_PILOT_RESULTS.json` 内原始 CLI 身份使用其短 SHA。

```bash
cd /root/autodl-tmp/rgbd_sam3d
MOMENTUM_ENABLED=0 PYOPENGL_PLATFORM=egl \
CUDA_HOME=/usr/local/cuda-13.0 PATH=/usr/local/cuda-13.0/bin:$PATH \
OMP_NUM_THREADS=4 envs/rgbd/bin/python -u \
  project_snapshot/research/rgbd_sam3d_mhr/train_native_pilot.py \
  --root /root/autodl-tmp/rgbd_sam3d \
  --config project_snapshot/research/rgbd_sam3d_mhr/SYNTHETIC_PILOT_CONFIG_V1.json \
  --source-commit 2366ca5b \
  --out runs/r2_native_pilot_v1 \
  --data datasets/synthetic/native_pilot_v1
```

输出目录保留历史，重跑使用新的 --out；数据不重新生成。恢复须使用 R0 对应 Official checkpoint/MHR 资产和此 run 的 fusion checkpoint，不包含官方模型的大型参数副本。

- 运行及全部 mesh/pose/camera 缓存：`/root/autodl-tmp/rgbd_sam3d/runs/r2_native_pilot_v1`。
- native 数据/冻结身份与逐样本 SHA：`datasets/synthetic/native_pilot_v1`。
- 真实输入观察：`datasets/registered_v1`；原始压缩包 `datasets/raw`；解压文件 `datasets/processed`。
- 备份：`172.18.6.218:436` 的 `/raid5/xuhd/rgbd_sam3d_backups/2026-10-09_r2_native_pilot_v1/r2_native_pilot_v1.tar.gz`，235,791,501 bytes，SHA256 `9e1eb86f51f5ff07c8679bf20f414a776effd3000a38f25978f0137d589204e7`，两端逐字节哈希一致。含全部 checkpoints/optimizer/logs/cache/native 数据与配置。官方模型/资产另在 R0 备份目录。

交付中的三份 `.jsonl.gz` 包含全部训练步骤的 loss 分量与梯度范数；`CHECKPOINTS.json` 保存末轮状态大小/参数量/SHA；`BACKUP_COMPLETE.json` 保存备份回执。完整逐身份、逐样本、Depth 消融在 `R2_PILOT_RESULTS.json`；精简结果在 `COMPARISON_SUMMARY.json`。

可视化来自最终缓存，未重新拟合：4 个 VAL 身份，各取预定 view0/1，共 8 张对照、8 张真实透视 Z 剖面、训练曲线。全部 32 个 VAL 案例和 6 组 Depth 消融 cache 保存在服务器/备份中；不是只保存好看的 8 张。

Nvdiffrast 原始来源和精确 commit 见 `NVDIFFRAST_SOURCE.json`，安装方法与坐标依据见 [官方文档](https://nvlabs.github.io/nvdiffrast/)。

## 下一步判断

先让 Depth 配对信息在模型内真正起作用：针对空间位置/metric geometry 编码和本地融合做最小改造，保持当前身份与测试封存，重复正确/错配/缺失消融，再用现成 HuMMan TRAIN/VAL 观察做开发验证。避免只增加轮次后依靠通用偏置改善。

当前 E0/E2/E3/E4 synthetic pilot 已执行；E1 Cheap Txyz、E5 native 参数优化强基线和真实 Camera B 效果尚未完成，不宣称本轮已覆盖全部最终实验矩阵。R3 真实适配与独立测试、R4 俯卧局部结果、模板穴位传播验证仍未完成。
