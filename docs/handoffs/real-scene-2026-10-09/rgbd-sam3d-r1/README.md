# RGB-D → 原生 MHR：GPU 可训练链实测 R1

状态：R1 真实 GPU 执行通过。R2 合成训练代码已写好，尚待实际训练结果；真实精度尚未验证。

## 已执行

- AutoDL 同一已租用实例恢复 GPU：RTX 6000D，85,651 MiB，25 核/120 GiB，数据盘剩余约 173 GiB。
- 真实 Official checkpoint + TorchScript MHR 加载；几何单位 cm→m、官方 Y/Z 翻转、公制透视 Z 渲染。
- RGB → 冻结官方 backbone → Depth Fusion → 官方 decoder/camera/MHR，真实 forward/loss/backward/AdamW，各 3 步。
- Cross-Attention 与空间残差各自通过；971 个官方参数逐值 SHA256 前后一致。
- 初始 MHR/camera 参数位级一致；缺失 Depth 回到 Official；改变 Depth 能影响位置、姿态、shape/scale。
- 零初始化 gate 在首步让 depth encoder 梯度为零；后续 gate 打开后梯度非零。这是预期行为，不是三个步骤都无梯度。

## 实际修复与限度

系统补装 libegl1 等 4 个小型依赖，未升级原有 Torch。初始严格零差异检查曾失败：Official 自身重复推理的顶点也有 2.38e-7 m 浮点差异。参数仍要求完全一致，几何等价容差改为 1e-6 m（0.001 mm），不是精度评价阈值；两种实测报告保存重复推理差异。

这些检查只使用一张简单材质原生 MHR 合成图。三步 loss 与深度扰动仅证明完整链可训练，不能据此声称新模型优于 Official，更不能声称真人/俯卧/穴位毫米精度。

官方加载提示的 missing keys 主要为独立 TorchScript MHR 资产内部缓冲及 hand_pose_comps_ori，日志保留；MHR 几何实际生成与反向传播已通过，不把加载成功等同于所有数据验证完成。

## 文件与入口

- `GPU_READY_R1.json`：实际硬件/环境与缺少 EGL 的首次失败。
- `R1_NATIVE_CHECK.json` / `R1_RESIDUAL_NATIVE_CHECK.json`：梯度、冻结参数哈希、Depth 扰动及显存。
- 代码：`research/rgbd_sam3d_mhr/check_native_r1.py`。
- 实际输出：`/root/autodl-tmp/rgbd_sam3d/runs/r1_cross_attention_checked`、`runs/r1_residual_checked`。
- 数据：`datasets/raw`（五个校验后的官方包）；`datasets/processed`（44 sequences 的 Kinect000/001 与相机配置）；身份 18 TRAIN / 4 VAL / 6 TEST 不变。

## 随后首轮训练

固定 32 个原生 MHR 合成身份：24 训练、4 开发、4 暂不读取的测试，8 视角/身份，含前后视角、小幅姿态和 shape/scale 变化。简单材质阶段没有衣物、床或临床穴位标签。统一 8 轮、同样样本顺序，比较 RGB-only 特征适配器、Depth residual、Depth Cross-Attention；冻结 Official，仅训练适配器。包含 native pose/shape/scale/camera/vertices/joints、可微透视 depth 和 silhouette 损失。末轮 checkpoint 固定，报告每轮开发误差及 Depth 消融，不挑最好测试结果。

首轮训练通过不等于 R3/R4 通过。真实 HuMMan 的独立身份及 Camera B 评价、俯卧适配仍须后续实际执行。
