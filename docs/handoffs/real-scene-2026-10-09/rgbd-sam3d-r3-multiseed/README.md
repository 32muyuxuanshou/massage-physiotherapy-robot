# R3：扩大合成数据与三种融合模型的多 seed 对照

状态：执行中；本文件是执行合同，不是完成报告。R2 单次实验不用于否定 Cross-Attention。

## 数据

- 500 个随机采样的 MHR 参数身份，每身份 2 个固定 body pose，每姿态 4 个物理相机，共 4,000 张。它们是合成身份，不是 500 名真实受试者。
- TRAIN / VAL / TEST = 400 / 50 / 50 身份，对应 3,200 / 400 / 400 图像。数据 seed `2026101001`，三种模型使用完全相同的文件和划分。
- Shape PCA 标准差 1.0，Scale 标准差 0.3；原生姿态角标准差 0.10 / 0.24 rad。手部参数与六个 body translation 参数不随机扰动。相机覆盖前、侧、后、侧，含俯仰与轻微滚转；同身份的两个姿态共享相机 K/R/T。
- 固定 posed world mesh 后改变相机；MHR 原生根旋转实际为 `xyz`，绕骨架根点旋转。将根点平移补偿明确计入 `pred_cam_t`，使 `X_camera = R @ X_world + T` 真正成立。
- 640×480，焦距 320–1,000 px，距离由两姿态的共同几何边界决定，覆盖 HuMMan 已准备数据约 2–3 m 的距离以及更远距离，不使用模型预测反调相机。
- 程序化体表色彩/条纹、光照变化；输入深度加 2–6 mm 高斯噪声、1 mm 量化、约 1–3% 缺测。`depth_m` 是带噪输入，`depth_clean_m` 是几何真值与监督目标。没有照片级衣物、床铺或接触形变。
- TEST 仅生成/保存。训练、缓存、消融、图片导出和真实评价都不读取 TEST 像素。
- Git 审查版 manifest 保留 TEST 身份/划分/样本 SHA，省略 TEST 的 Shape/Scale 真值参数；原始完整 manifest 留在服务器。审查版记录原文件 SHA，缓存合同仍绑定原始文件。

## 几何和执行验证

32 张小样本先验证根旋转、固定姿态刚体关系、完整前向/特征缓存与 Batch 8/16 backward。

几何主检查为内部像素的原始 K 与公制 Z 反投影后，到冻结 CPU 精确三角面的距离；median <0.01 mm、P95 <0.1 mm，max 完整报告。投影计算还沿用已通过的斜平面解析验证。GPU 边缘/浮点采样不适合用 0.01 mm 的单点最大值阻塞，故在正式训练前固定为上述分位数合同。Pyrender/OpenGL 与 nvdiffrast 的差异另行报告；OpenGL MSAA 采样差异不作为真值误差门槛。准备阶段曾遇到根旋转/pivot 误用及过严的跨渲染器中位数条件，均在正式训练前处理，初始数据目录保留，不混入正式数据。

缓存保持官方原生 backbone 输出 dtype，不压缩/量化特征。前向数值等价允许参数绝对差 ≤2e-6、顶点 ≤0.001 mm；不声称 bitwise equality。32 张检查中顶点最大差约 0.00054 mm。正式缓存首帧的 Scale 差为 1.073e-6，略超初始 1e-6 条件，顶点差仍为 0.00054 mm；因此在任何正式训练前将参数容差明确修正为 2e-6，顶点门槛保持不变，失败日志单独保留。Batch 16 预热后约 0.384 s/update，峰值约 6 GB；这是吞吐检查，不是科学结果。

同卡独立进程吞吐检查（每进程 60 个 Batch 16 updates，排除前 4 步预热）：1 / 2 / 3 进程分别约 55.05 / 75.30 / 86.77 images/s，合计峰值 allocated memory 6.27 / 12.39 / 18.23 GB。按这三档中实测最高总吞吐，使用三个独立 Python 进程。三进程包含 RGB-only、Residual、Cross-Attention；这不是相同模型的纯 scaling 定律。每进程独立模型、优化器、seed、输出目录，数据只读共享；缓存 LRU 限制 1,024 条，避免三进程各缓存全量数据超过实例 120 GiB RAM。正式全数据 I/O 会影响速度，以运行日志为准。

## 训练

- 原有 RGB-only / Spatial Residual / Cross-Attention 不改架构。只训练各自 feature adapter；官方 backbone、Decoder、MHR、Camera heads 全部冻结。沿用 R2 loss 及权重。
- 真 Batch 16，AdamW，weight decay 1e-4，梯度裁剪 1.0，前两轮 warmup，之后 cosine 至初始学习率的 10%。
- `1e-4 / 3e-4 × 三模型` 各用 seed 7 跑 5 轮开发对照。用第 5 轮三个模型的合成 VAL 身份等权 camera-frame vertex mean 的平均数，选统一学习率；相等时选较小值。这个短对照不替代充分训练。
- 正式每模型 seeds 11/23/37，各 30 轮，共 9 次。从统一 Official 起点重新初始化 adapter，不延续短学习率对照的权重。
- 保存 `best.pt`、`last.pt`、optimizer/scheduler、训练日志、每轮曲线、全部 VAL 最佳/末轮原生 Mesh 与参数。最佳 checkpoint 仅由合成 VAL 的 camera-frame vertex mean 选出。
- 评价顶点、去平移顶点、camera、关节、Shape、Scale、实际 root rotation、Pose 角度、深度 common-hit median/P95、命中率及 silhouette IoU。Pose 角度报告排除六个平移参数。
- 相同 seed 成对比较 RGB-D 与 RGB；报告每 seed、均值、样本标准差（ddof=1）。三个 seed 不是接受率或统计显著性的保证。

## 深度消融

对每个 RGB-D 模型的三个最佳 checkpoint，使用全部 400 张合成 VAL：正确输入、跨身份错配、同身份另一姿态（相同相机）、中心区域 16×16 depth/mask patch 扰乱、缺失深度、±50 / ±200 mm 公制偏移。RGB、bbox、K、camera rays 均保持原样。

保存真值误差及相对正确输入的 Mesh、Camera 三轴、Pose、Shape、Scale 输出变化。不能仅凭梯度非零或缺失深度退化宣布成功；当前结构在缺失 Depth 时回退 Official，因此该消融必须和错配/局部扰乱/公制偏移一起解释。

## HuMMan 真实迁移

- 只用已准备的 TRAIN 192、VAL 40 个时间点，共 232 帧；TEST 120 帧不读。
- Camera A = Kinect 000，为唯一输入；Camera B = Kinect 001，只用于独立传感器评价。没有任何真实数据训练。
- 在新模型评价前冻结每帧 B 的 2,048 个原始点索引，各模型、各 seed 完全相同。精确 observed-point→predicted-triangle 距离为主指标；共同命中像素深度残差与命中率辅助报告。
- 单独报告 TRAIN 与 VAL，按 frame→sequence→identity 等权汇总。使用原始公开 K/R/T 和现有标定配准；不调整相机让预测 Mesh 更贴合。
- 公共发布未提供畸变系数，配准 QA 不等于独立毫米级精度证明。测得的是衣物/人体可见表面，不是背部穴位真值；Official 预训练是否包含这些人未知。
- 新模型各 cell 完成后进行真实推理；释放 GPU 后 CPU 精确三角面评价可与其它 cell 训练并行。

## 路径和交付

AutoDL 根目录 `/root/autodl-tmp/rgbd_sam3d`：

| 内容 | 相对路径 |
|---|---|
| 正式合成数据 | `datasets/synthetic/native_scale_v2` |
| 合成 TRAIN/VAL 缓存 | `datasets/cache/native_scale_v2` |
| 真实 TRAIN/VAL 缓存 | `datasets/cache/humman_development_v1` |
| 固定 Camera B 点样本 | `datasets/heldout/humman_r3_k1_v1` |
| 阶段日志、ledger、QA | `runs/r3_multiseed_v1` |
| 正式训练与消融 | `runs/r3_multiseed_v1/formal` |
| 合成训练/开发集图片 | `datasets/previews/native_scale_v2` |

源码位于 `research/rgbd_sam3d_mhr`，总入口 `run_r3_pipeline.py`，并发队列 `run_r3_queue.py`，合同 `R3_SCALE_CONFIG_V1.json`。三进程并发暂估 4–6 小时，以正式运行速度更新。原始真人数据、权重和 checkpoint 不入 Git；源码、配置、QA、结果表、曲线、合成可视化和备份回执进入审查交付。R2 输出保持原样。正式结论等待 9 次训练及对应消融/真实迁移完成。
