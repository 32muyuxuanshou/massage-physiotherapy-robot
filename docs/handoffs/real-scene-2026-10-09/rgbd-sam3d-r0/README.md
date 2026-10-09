## Material Passport

- 模式：工程执行 / R0 环境、资产和网络接口准备。
- 日期：2026-10-09；项目起点 `e737849e7f7df9c70c51149dd46e6ddbe0918ded`。
- 实际读取：新任务全文、CURRENT_STATUS、历史环境状态、HuMMan几何接口、旧微调复盘/训练源码、Cheap Txyz与Camera B评价代码、官方SAM/MHR接口与安装文档。
- 实际执行：SSH资源探测、官方资产SHA、HuMMan下载/目录检查、隔离环境安装/import、CPU融合梯度与几何检查、218备份。
- 未执行：新实例完整SAM/MHR前向、原生MHR渲染、完整模型backward、R2训练、R3/R4真实评价。
- 状态：**R0准备完成；等待用户将既有实例切回GPU，随后开始R1。**

# 本轮完成了什么

新研究代码已部署到 AutoDL。主网络直接使用米制Depth：官方RGB backbone之后，接Depth encoder及空间残差/交叉注意力，再使用原decoder/MHR/Camera heads。保留原生MHR，不用自由顶点偏移作为网络输出。当前只能确认实现与小模块执行，**不能说RGB-D新模型已经训练成功**。

## 1. 实际资源与服务器角色

| 角色 | 入口 | 目录/资源 |
|---|---|---|
| 计算 | `ssh -p 39846 root@connect.cqa1.seetacloud.com` | `/root/autodl-tmp/rgbd_sam3d` |
| 当前无卡配额 | cgroup实测 | 0.5 CPU核、2 GiB内存、CUDA不可用 |
| 数据盘 | df实测 | 200 GiB容量，收尾剩187,260,227,584 bytes，约174.4 GiB |
| 隔离环境 | `envs/rgbd/bin/python` | Python3.12.3；复用base Torch2.12.1+cu130、torchvision0.27.1+cu130、numpy2.4.6，版本保持不变 |
| 持久备份 | `ssh -p 436 xuhd@172.18.6.218` | `/raid5/xuhd/rgbd_sam3d_backups/2026-10-09_r0`，weights/source SHA全部通过 |

任务提供的RTX6000D/84GB、25核/120GB是拟启用GPU模式的配置，**本轮没有实际检测到这些资源**；切换后重新核实。没有新增实例或扩容，没有等待/连接旧151。

证据：[初始资源](SERVER_ENVIRONMENT_R0.json)、[cgroup/模块状态](ACCESS_AND_RESOURCES.json)、[环境完成](ENVIRONMENT_READY_R0.json)、[版本冻结](environment_freeze.txt)、[备份回执](BACKUP_R0.json)。

## 2. 官方资产与来源

| 资产 | 实际字节数 | 结论 |
|---|---:|---|
| ViT-H model.ckpt | 1,691,205,237 | 复用先前合法获取的本地官方文件；传到AutoDL后重新SHA，与当前官方LFS SHA完全一致 |
| assets/mhr_model.pt | 696,110,248 | 同上，已在AutoDL和218分别重新SHA |
| 官方SAM源码 | 23,460,103压缩字节 | 从本地干净Git的`b5c765a0d89d789985e186d396315e7590887b94`导出；传输SHA一致；官方文件未修改 |
| model_config.yaml | 1,466 | 复用历史已运行的许可配置；当前HF元数据为1,486字节，**不声称原文件字节相同**。本地/服务器/备份SHA一致，GPU阶段核对实际模型加载与输出 |

不依赖151，不使用第三方重打包权重。AutoDL到huggingface.co网络不可达，不能把这个误报成401或权限未获批。HuMMan的官方CDN可达，因此采用本地取得公开重定向、数据本体直接在服务器下载的方法；没有绕过gated权限。

项目完整Git clone先超时、稀疏clone又发生TLS错误。采用**本地已核实Git版本的选定项目文件/SHA快照**部署到`project_snapshot`；不声称服务器存在完整Git checkout。最终快照按交付commit和逐文件哈希绑定。官方SAM另用固定commit的Git archive。

证据：[官方与本地SHA](OFFICIAL_ASSET_ACCESS.json)、[实际服务器SHA](SERVER_ASSET_HASHES_R0.json)、[权重传输](WEIGHT_TRANSFER.json)。

## 3. 数据准备与容量

官方HuMMan数据revision：`56a2a9a12e21abe10744580f96989534cdbdff76`。以下五包均**实际下载完成且SHA匹配官方LFS**：

| 包 | 字节数 |
|---|---:|
| point_cameras.7z | 58,953 |
| smpl_params.7z | 23,118,862 |
| point_kinect_mask.7z | 1,376,700,892 |
| point_kinect_depth_part_11.7z | 8,637,312,381 |
| point_kinect_color_part_02.7z | 13,892,569,135 |
| 总量 | **23,929,760,223** |

目录解析得到44个共同序列、28个人物，均存在Kinect000/001的RGB、Depth与Mask文件。两相机RGB/Depth选择性解压约2,222,575,731 bytes；Mask另计。44份对应camera metadata已实际解压并核对K/R维度、R正交性。

**这不等于逐帧可用性通过。**尚未解压全部选定Depth/视频，没有完成帧同步、非平面RGB/Depth注册和有效深度QA。GPU模式的CPU配额恢复后再做这些，不在0.5核模式下解压整个数据集。

28个人与历史暴露身份无交集；历史文件中它们仅出现在归档目录/未读身份元数据。已在看图/模型输出前冻结18 TRAIN / 4 VAL / 6 TEST，所有动作/视图/帧跟随人物。这里只声明与**可核查项目历史记录**无交集，不保证SAM官方预训练从未使用这些人物。

输入Kinect000；Kinect001传感器观测只评价，不进入网络输入或优化器。帧索引待纯数据同步/有效性QA后固定。SMPL为支持参考，不能作为原生MHR真值。

证据：[下载回执](HUMMAN_DOWNLOAD_LEDGER.json)、[RGB/Depth共同目录](HUMMAN_CATALOG_R0.json)、[历史身份审计](IDENTITY_CATALOG_AUDIT_R0.json)、[calibration元数据QA](CALIBRATION_METADATA_QA_R0.json)、[身份合同](../../../../research/rgbd_sam3d_mhr/INITIAL_IDENTITY_SPLIT_V1.json)。

[HuMMan官方项目](https://caizhongang.com/projects/HuMMan/point.html)采用S-Lab License1.0；本阶段为非商业研究、受控云端使用。原始真人图像、原始相机矩阵、数据包和权重不进公开Git。本地约173MB Linux依赖包仅用于安装转运，不是把HuMMan下载到了本地。

## 4. RGB-D接入点与已执行检查

- Official RGB：512×512 crop裁左右64列 → 512×384，backbone特征1280×32×24（768空间位置）。
- Depth：先用官方标定注册为RGB-camera米制Z，再复用同一实际affine；不把原始Depth直接当RGB像素，不独立resize或重新估计K。
- 五通道：绝对Z、相对人体中位Z、有效掩码、相机x/z与y/z射线。
- 两级stride4 Depth encoder → 与RGB同stride16空间网格；RGB query/Depth key-value交叉注意力，另有空间残差对照。
- 接入位置：backbone输出后、mask prompt/decoder前；沿用原MHR与Camera查询路径。
- 阶段一冻结整个Official，只训练fusion。gate从零开始，第一次encoder梯度为零是预期；gate打开后检查非零梯度。全缺Depth保留Official特征。

实际PASS：两种融合的小网格与**生产尺寸1280×32×24 / Depth512×384**CPU检查、初始RGB等价、缺Depth等价、训练后三次step梯度和Depth改变输出；同RGB affine解析例米制Depth与相机射线误差为0。**均为模块检查，不是完整SAM/MHR链。**

证据：[小网格服务器检查](FUSION_SERVER_CPU_CHECK.json)、[实际尺寸服务器检查](FUSION_FULL_GRID_CPU_CHECK.json)、[裁剪几何检查](GEOMETRY_SERVER_CPU_CHECK.json)。

旧微调复盘已采纳：它只用Depth监督，RGB输入不变；整体translation贡献很大，不能当RGB-D架构训练。新阶段需要分别报告camera、去平移形状、pose/shape/scale与后背表面收益。

## 5. GPU切换后的第一项实际执行

不直接启动大训练。预计先用约10–20分钟完成GPU/驱动实测及第一轮完整模型检查，实际以运行/报错为准：

1. 重新检查GPU、CUDA和实际CPU/RAM；核实权重/配置加载。
2. 用官方MHRHead生成一个简单材质、原生MHR参数/顶点/骨架/米制Depth的几何fixture。该fixture只是R1检查，不是正式R2训练库。
3. Official RGB推理 → 零gate RGB-D一致性。
4. 三次实际native MHR loss/backward/optimizer step；检测Depth梯度与camera/pose/shape/vertices输出影响。
5. 全部Official参数值的前后SHA一致；保存实际vertices、参数、梯度、模型及峰值显存。
6. R1通过后再扩充合成身份/姿态、可微Depth/silhouette损失和正式训练。当前R1入口还没有这些完整R2损失，不将“一次backward”写成有效模型。

准确命令：[代码README](../../../../research/rgbd_sam3d_mhr/README.md)。执行入口：[check_native_r1.py](../../../../research/rgbd_sam3d_mhr/check_native_r1.py)。

## 6. 实际命令、异常与存储边界

资源探测：`nvidia-smi / df / free / python / nvcc`及cgroup；源码/权重：`git archive`、SFTP、`sha256sum`；数据：`download_humman.py`与服务器`download_one.py`；目录：官方7-Zip26.04 `l -slt`；安装：`setup_offline_r0.py`；检查：`check_fusion.py`、`check_geometry.py`。

原HTTP镜像安装超时、PyPI直连大wheel很慢。实际从官方PyPI下载匹配Linux/Python3.12的包，逐个按PyPI SHA验证后传到AutoDL，离线安装成功；base Torch/torchvision/numpy未变。详见[安装回执](OFFLINE_INSTALL_R0.json)、[83包来源哈希](PYPI_WHEELHOUSE_RECEIPT.json)。

压缩包23GiB、选择性解压预留35、合成5、权重/源码5、环境8、缓存15、checkpoint40、报告4、空余40：预算175GiB，不代表这些空间已使用。当前约25.6GiB使用、174.4GiB可用；不下载CT/全量HuMMan/无关大包。

后续只根据独立真实相机证据决定学习模型是否改善形状。PressurePose继续保留“已消费、近似标定、衣物表面”的诊断身份。人体表面贴合、工程点拓扑稳定性、真人解剖/穴位精度分别验收。

[机器可读执行Ledger](R0_EXECUTION_LEDGER.json)是本轮执行事实入口。代码、文档及索引进入Git；原始数据和权重只留服务器/已授权备份。
