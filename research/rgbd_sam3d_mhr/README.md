# RGB-D SAM3D / native MHR

新主线：校准 RGB-D → RGB backbone + metric Depth encoder → 空间融合 → 原 SAM3D decoder → 原生 MHR 与 Camera。标准 MHR 的固定拓扑穴位传播仍是后续工程接口，本目录不训练穴位检测器。

## 当前执行范围

2026-10-09 正在完成 R0 无卡准备。`check_fusion.py` 与 `check_geometry.py` 是小模块/解析几何检查，**不是完整 SAM/MHR 训练**。`check_native_r1.py` 是待 GPU 模式运行的实际模型入口；它生成一个简单材质的原生 MHR 几何 fixture，并验证三次 loss/backward/optimizer step。这不等于 R2 数据集或真人效果。

CT、Reference-Anchored 与旧九模型路线暂停大规模运行；保留旧代码与结果。历史“RGB + 深度监督微调”没有 Depth 网络输入，不能作为本模型已经训练的证据。

## 资源位置

- 计算：`ssh -p 39846 root@connect.cqa1.seetacloud.com`
- 根目录：`/root/autodl-tmp/rgbd_sam3d`
- Python：`envs/rgbd/bin/python`，隔离 venv 复用实例已有 PyTorch，不替换 base。
- 官方代码：`external/sam-3d-body`，固定版本见 `EXPERIMENT_START_V1.json`。
- 官方权重：`checkpoints/official/sam-3d-body-vith/{model.ckpt,model_config.yaml,assets/mhr_model.pt}`。
- 原始 HuMMan 压缩包：`datasets/raw`；仅按相机/身份选择性解压。
- 备份：`ssh -p 436 xuhd@172.18.6.218`，`/raid5/xuhd/rgbd_sam3d_backups`。
- 密码、Token、临时签名下载地址不进入代码、Git 或公开报告。

## 几何与模型合同

ViT-H 的 RGB：512×512 官方 crop 再裁左右各64列 → 512×384；backbone 输出1280×32×24，即768空间位置。Depth 使用**同一实际 affine**，不重新裁图/估计 K。原始 Depth 先依官方相机参数注册到 RGB camera Z；注册空洞保持缺失，不用插值冒充观测。

Depth 五通道：米制 Z、相对人体中位 Z、有效掩码、x/z 与 y/z 射线。两级 stride-4 Conv 得到 stride-16空间特征。主模型 RGB query 与 Depth key/value 交叉注意力；轻对照为直接空间残差。融合位于 backbone 之后、mask prompt 与 decoder 之前，因此通过原 pose/camera 查询路径输出 MHR。

残差 gate 从零开始：初始输出保持 Official；第一次 encoder 梯度为零是预期，gate 更新后必须测得非零梯度。全缺 Depth 返回 Official 特征。阶段一仅训练 fusion，原模型全部参数冻结。GPU 检查将逐参数重算冻结值哈希，不能只相信 `requires_grad=False` 的声明。

原 MHRHead 将 raw asset **cm÷100→m**，随后翻转 Y/Z 轴；相机 translation 单独相加。`check_native_r1.py` 复用此转换，不再次换单位。HuMMan SMPL 仅作参考，不能冒充原生 MHR 真值。

## 第一批数据与划分

真实数据选择官方 HuMMan-Point 的 cameras、SMPL、Mask、Depth part11、RGB part02，压缩总量23,929,760,223 bytes。目录实读：共同44序列/28人物，Kinect000/001的Mask均存在，两相机RGB/Depth选择性解压约2.22 GB。**不是340人/907序列已完整下载，也不是训练样本已经处理完成**。

`HISTORICAL_IDENTITY_EXPOSURE.json` 保守列出旧 TRAIN/VAL/SEALED/DEV/QA 身份。28个人与记录中的已消费身份无交集，在可读历史handoff中仅见归档元数据；不据此声称Official预训练从未见过。`INITIAL_IDENTITY_SPLIT_V1.json` 在读取图像/模型结果之前冻结18 TRAIN / 4 VAL / 6 TEST，全部动作、相机、帧跟随身份。输入 Kinect000；Kinect001 仅评价。逐帧同步/有效Depth QA与最终帧索引仍待准备，不能用模型结果挑样本。

HuMMan 采用 [S-Lab License 1.0](https://caizhongang.com/projects/HuMMan/point.html)，本轮非商业研究、受控服务器使用；原始真人图像和权重不公开上传。商业部署许可另行处理。

## 执行命令

小模块检查，可在无卡模式执行：

```bash
envs/rgbd/bin/python project_snapshot/research/rgbd_sam3d_mhr/check_fusion.py --out runs/FUSION_CPU_MODULE_CHECK.json
envs/rgbd/bin/python project_snapshot/research/rgbd_sam3d_mhr/check_geometry.py --out runs/GEOMETRY_CPU_CHECK.json
```

GPU 模式检查（**尚未执行**，先检查实际 GPU/显存/CUDA，再运行）：

```bash
MOMENTUM_ENABLED=0 PYOPENGL_PLATFORM=egl envs/rgbd/bin/python project_snapshot/research/rgbd_sam3d_mhr/check_native_r1.py \
  --sam-source external/sam-3d-body \
  --checkpoint checkpoints/official/sam-3d-body-vith/model.ckpt \
  --mhr checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt \
  --out runs/r1_cross_attention
```

R1 检查输出实际原生 vertices/joints/parameters、相机位置、参数冻结哈希、梯度、峰值显存、Depth 改变及缺失消融。当前不包含可微 rendered-depth/silhouette loss；R2 实现这些损失后才称完整训练配置。

## 后续阶段

R1 全模型实跑通过 → R2 扩展原生 MHR 合成身份/姿态监督及公平 RGB-only/residual/attention 对照 → R3 HuMMan 跨身份、独立相机评价 → R4 已消费 PressurePose 俯卧诊断与新的可靠俯卧验证。先分开绝对位置、去平移形状、后背表面和工程点对应，不能仅凭输入 Depth 拟合误差宣布模型成功。

共同对照与存储预算在 `EXPERIMENT_START_V1.json`；实际版本/资源/下载回执与阻塞见 R0 handoff。**GPU 切换由项目负责人在数据、权重、代码、环境准备完后操作。**
