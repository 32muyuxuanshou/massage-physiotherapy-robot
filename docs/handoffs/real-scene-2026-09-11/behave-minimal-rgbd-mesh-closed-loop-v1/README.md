# BEHAVE 最小真实 RGB-D Mesh 闭环 V1

## 结论

最终 Gate：`PASS_BEHAVE_MINIMAL_RGBD_MESH_CLOSED_LOOP_WITH_LIMITATIONS`。

本次在服务器直接下载 BEHAVE 官方 Date01 数据，用 3 个不同交互序列各 1 帧跑通完整闭环：Camera A RGB 只运行一次冻结 Official SAM 3D Body，Camera A 人体 Depth 只估计全局 `Txyz`，随后把同一份 Official/Txyz mesh 通过官方标定变换到 Camera B 独立考试。Camera B 没有参与 A 上的推理或修正，也没有重新推理 mesh。

3 帧 Camera B 中位点到三角面误差分别为：

| 样本 | Official | Txyz | 变化 |
|---|---:|---:|---:|
| backpack_back | 36.1 mm | 26.2 mm | -9.8 mm |
| stool_sit | 38.4 mm | 25.8 mm | -12.6 mm |
| yogaball_play | 19.1 mm | 13.6 mm | -5.4 mm |

本次 3/3 改善，但只有 1 个 subject、3 个经过可见面积筛选的帧，不能据此声称在 BEHAVE 总体上稳定。改善来自整体绝对平移；pose、shape、尺度、手部和人体—物体接触形状完全没有改变。可视化仍能看到背包遮挡、手部、脚部和物体接触处的局部形状误差。

## 推理与考试

推理使用 Camera A（Kinect 0）：

1. Camera A RGB + 人体 mask 得到 ROI；
2. Official SAM3D 输出 `official_camA.obj`；
3. Camera A 人体 mask 内的注册 Depth 生成点云；
4. 16,384 个固定 MHR 表面锚点通过 6 次截尾最近邻只求全局 `Txyz`；
5. 输出 Camera A 原图、Official overlay、Txyz overlay 和三联图。

考试使用 Camera B（Kinect 1）：

1. 用 Date01 官方外参把 Camera A 的同一份 mesh 变换到 Camera B；
2. Camera B RGB 只用于显示，人体 Depth 只用于独立评价；
3. 输出 Camera B 原图、Official overlay、Txyz overlay 和三联图；
4. 指标是固定抽样 5,000 个观察点到精确 mesh 三角面的单向距离。

只用两个机位，是为了把“生成/修正”和“独立考试”分开。其余两个 Kinect 没有用于这个最小闭环，避免在首轮验证中扩大变量；后续可以作为额外 held-out views。

## 数据与运行位置

- 服务器：`172.18.18.151:436`
- 工作根目录：`/raid5/xuhd/behave_rgbd_mesh_v1`
- 下载：`/raid5/xuhd/behave_rgbd_mesh_v1/downloads`
- 解压子集：`/raid5/xuhd/behave_rgbd_mesh_v1/data/sequences`
- 报告：`/raid5/xuhd/behave_rgbd_mesh_v1/output/report`
- 完整可视化：`/raid5/xuhd/behave_rgbd_mesh_v1/output/visualizations`
- Mesh：`/raid5/xuhd/behave_rgbd_mesh_v1/output/meshes`
- 原始日志：`/raid5/xuhd/behave_rgbd_mesh_v1/logs`

下载了官方 `calibs.zip`（395,854,758 bytes）、`split.json`（10,555 bytes）和 `Date01.zip`（15,019,046,742 bytes），并通过 ZIP 完整性检查。下载地址、SHA256、所选输入文件和标定文件哈希见 [`report/download_audit.json`](report/download_audit.json) 与 [`report/dataset_manifest.json`](report/dataset_manifest.json)。

## 可视化交付边界

服务器为每个实际运行帧完整保存了推理侧和考试侧各 4 张 PNG，共 24 张逐帧图，并另有 2 张 montage；数量和 SHA256 见 [`report/server_visualization_manifest.json`](report/server_visualization_manifest.json)。

BEHAVE 官方数据许可限定非商业科研用途，禁止向第三方再分发数据，并要求公开展示时模糊人脸。因此本公开 Git handoff 不提交原图及其 overlay，只提交可复现代码、逐帧指标、服务器文件清单与哈希。完整图像留在授权服务器目录中。

## 审计结果

- Step 1 下载与数据审计：`PASS`
- Step 2 推理/考试定义：`PASS`
- Step 3 Official SAM3D：3/3 `PASS`
- Step 4 Camera-A-only Cheap Txyz：3/3 `PASS`，无 fallback
- Step 5 Camera B 独立考试：3/3 `PASS`
- Step 6 逐帧指标、耗时、显存与文件审计：`PASS`

第一次加载模型为 3.66 秒，后两帧 Official 推理约 0.32–0.34 秒；Txyz 为 0.12–0.16 秒，峰值 CUDA 已分配显存约 3.04 GB。极端 `max` 距离达到米级，来自 mask/depth 边界离群点，因此不能用 max 代表主体贴合；中位数、P90/P95 和可视化更适合这次小试验。

## 当前回答

1. BEHAVE 能直接支持 RGB → Official mesh、Depth → Txyz correction、Camera B 独立考试。
2. 当前筛选的 3 帧全部改善，但样本不足以证明总体稳定。
3. 改善是 absolute position；它没有修复更深层的 pose/shape 几何。
4. 本轮没有退化帧，扩大测试后仍需专门检查原本准确的样本。
5. 下一步应先修正 ROI/person-depth 边界与评价离群点处理，再做一个 subject/sequence 平衡的小型 BEHAVE dev 集；完成后再转产品域 RGB-D。这里没有擅自开启该任务。

## 文件入口

- [`report/final_decision.json`](report/final_decision.json)
- [`report/verification.json`](report/verification.json)
- [`report/system_summary.json`](report/system_summary.json)
- [`report/per_frame_metrics.csv`](report/per_frame_metrics.csv)
- [`report/per_frame_metrics.json`](report/per_frame_metrics.json)
- [`report/run_config.json`](report/run_config.json)
- [`raw_logs/run.log`](raw_logs/run.log)
- [`code/run_behave_minimal.py`](code/run_behave_minimal.py)
