# BEHAVE：MHR / SMPL 指标桥接核验

日期：2026-10-13。状态：**对应顶点指标可运行；M³ 完整评价协议仍未确认。**

本轮实现评价工具并做 CPU 核验，没有下载 BEHAVE 大包、运行模型推理或训练。AutoDL 保持无卡模式，没有关机。

## 1. 解决了什么

M³ 输出 SMPL 拓扑，我们输出 MHR。Meta 官方提供 `mhr2smpl_mapping.npz`，可将 MHR LOD1 的 18,439 个顶点固定采样为 6,890 个 SMPL 编号顶点。SAM3D 原论文本身也说明，在 SMPL 数据集上先进行此类映射再评价。

本轮采用官方转换工具中的**固定重心插值步骤**，不进行 SMPL 参数重新拟合，不读取参考人体改变预测，不做最近表面匹配冒充对应顶点。

\[
\widehat V^{SMPL}_i=\sum_{j=1}^{3}b_{ij}\widehat V^{MHR}_{F_{ij}}.
\]

映射的 MHR 面片顺序与现有 `mhr_faces.npy` 完全一致。映射 SHA256：
`4bfe2fd6abb598f38ba3a3aa5506ac45b4efb3cdaed7fe4757cfbbf20bbe6ac7`。

**它是近似的跨模型表面对应，不是严格双射，也不是解剖点真值。**数字实现吻合不能证明医学对应准确。

## 2. 固定报告哪些误差

统一使用米作为输入，输出毫米。全体 6,890 个顶点均保留。

|字段|计算|解释|
|---|---|---|
|`pve_absolute_mm`|同编号预测与参考顶点的欧氏距离，先逐顶点求均值|同时包含位置、旋转、尺度、姿态和形状误差；本项目主指标|
|`pve_centroid_centered_mm`|分别减去预测和参考的顶点质心，再计算相同均值|去除质心位移后的诊断；**不是 pelvis/root-aligned PVE**|
|`pa_pve_similarity_mm`|仅为诊断，把预测做最佳整体平移＋旋转＋统一缩放后算均值|检查可消除的整体几何差异；不能解释成绝对定位精度|

PVE 是**对应顶点平均 L2**，不是顶点中位数、点云到最近三角面的距离、Chamfer 或轮廓 IoU。不能用历史 BEHAVE 的 17.80 mm 表面距离替代本轮 PVE。

中心化/PA 只生成评价诊断，不改变任何模型输出。PA 用平方误差求整体变换，因此不保证每个样本的“平均欧氏距离”都单调下降。

代码另支持传入明确的 SMPL 关节回归器，计算 pelvis-centered PVE 和对应关节 MPJPE。本轮未找到可核验的 6,890 顶点 SMPL 关节回归器资产，也未确认 M³ 使用的关节集合，所以**没有把此功能标为已完成真人验证或把 centroid 指标冒充 root 指标**。

## 3. 坐标合同

- SAM3D 的 `pred_vertices` 是已按相机轴约定转换的米制局部顶点；加 `pred_cam_t` **一次**得到相机顶点，不再翻 Y/Z。
- 原生 MHR rest asset 是 cm；只有读取这个原生资产时才先乘 0.01，并显式按 SAM3D 约定翻 Y/Z。不能把这种处理重复用到 SAM3D 缓存。
- BEHAVE 参考文件是 `sequences/<sequence>/<timestamp>/person/fit02/person_fit.ply`。不能用 `person/person.ply` 点云或 FrankMocap 预测替代。
- BEHAVE 官方 demo 加载 fitting mesh 后先调用 `world2local_meshes`，再投影到各相机。我们的世界→相机实现为 `(V_world - t_local_to_world) @ R_local_to_world`。
- 正式评价必须使用对应 sequence / DateXX / 输入 camera 的标定。本轮没有实际 BEHAVE fitting mesh 的坐标核验帧；这是后续数据准备的检查，不是已完成证据。
- CLI 要求显式指定 `--reference-space camera` 或 `behave-world`；后者必须同时指定对应相机的 `config.json`。不通过让 Mesh 更贴合来重新估计外参。

## 4. 已经实际通过的核验

|检查|结果|
|---|---|
|相同网格绝对 PVE|0 mm|
|纯 Z 移动 100 mm|绝对 PVE = 100 mm；中心化误差接近 0|
|固定映射保留整体平移|最大坐标差约 5.55e-17 m|
|旋转＋尺度＋位置变化|绝对与中心化指标检测到变化；PA 误差接近 0|
|局部形状扰动|中心化与 PA 后仍有非零误差|
|已有 B1 预测缓存|18,439 → 6,890，输出有限且保持公制体量|
|PLY 读写正常路径|顶点顺序保留，PVE 约 2.71e-5 mm，仅来自 float32 写入|
|无卡服务器与本地|CPU 解析核验均 PASS|
|与官方 `_compute_target_vertices` 数值对照|平均顶点差约 1.785e-5 mm；最大坐标差 7.487e-8 m|

最后一项是**我们的实现与官方映射函数的数值差**，不是 MHR→SMPL 的真实几何/语义转换误差。B1 是已有预测缓存的结构核验，不是 BEHAVE 科学精度结果。

附带的已知 cm/m 错误演示显示：单位错误可被 PA 的缩放掩盖，因此绝对指标与输入单位声明必须一起保留。该演示不进入任何模型比较。

## 5. 与 M³ 的比较边界

M³ 的 70.9 mm 是 AMASS 预训练＋BEHAVE TRAIN 微调后的 BEHAVE TEST PVE；仅 AMASS 时为 93.1 mm。M³ 正文/补充没有明确公开其 PVE 的根节点/整体对齐、测试时间戳、相机采样及汇总方式。本轮网页检索没有找到能补齐这些细节的可核查评测代码。

因此，现在已经具备**同数据集、同顶点布局、同距离公式**的评价能力。不能宣称已经获得“与 M³ 完全一致的协议”，也不能在三种对齐指标中挑一个最好值与 70.9 比。

后续表格应将 M³ 标成“论文报告、对齐/样本协议未确认”，我们标成“本次实测、固定映射、明确对齐”。先报告三种指标，再解释位置与身体几何的差异。

正式数据采用官方 TEST 序列；官方 split 是 sequence split，不等同于未见身份 split。历史 45 帧中 Date05/Sub06 和 Date06/Sub07 属于官方 TRAIN，不能并入 TEST 后仍称官方测试。

每帧先对 6,890 顶点求均值；新对照主表采用 frame-equal mean，同时保留 sequence→identity 等权表和逐帧记录。M³ 的汇总权重未公开，不把两个汇总口径混为一个数字。当前没有选择或执行正式测试时间戳。

## 6. 使用与服务器位置

代码真身：[research/behave_metric_alignment](../../../research/behave_metric_alignment)。只依赖 NumPy；读取 PLY 时需要 trimesh；官方函数数值核对额外需要 CPU PyTorch。

```bash
python metrics.py \
  --prediction vertices_camera_m.npy \
  --reference person_fit.ply --reference-space behave-world \
  --local-to-world-config calibs/Date03/config/0/config.json \
  --mapping mhr2smpl_mapping.npz --mhr-faces mhr_faces.npy \
  --output per_frame_pve.json
```

预测必须已经在所选相机坐标，单位 m；参数里的 Date03/K0 仅为路径示例，不能对其它日期硬编码复用。若输入 reference 已经被转换到该相机，应改成 `--reference-space camera`，不再传重复变换。

AutoDL 已部署并完成 CPU 核验：
`/root/autodl-tmp/rgbd_sam3d/evaluations/behave_metric_alignment_v1/`。
本地完整核验：`output/behave_metric_alignment_v1/`。公开 Git 文档不包含原始人体资产、模型权重或 SSH 凭据。

## 7. 可核查来源

- [M³ v2：方法、数据与表 3/4](https://arxiv.org/html/2508.08178v2)
- [SAM3D §8：MHR 映射到 SMPL 后评价](https://arxiv.org/html/2602.15989v1#S8)
- [Meta 官方转换工具](https://github.com/facebookresearch/MHR/tree/d96fafa33bbf018647c70c3525e91f53e79d2a14/tools/mhr_smpl_conversion)
- [BEHAVE 官方 demo 的世界→相机处理](https://github.com/xiexh20/behave-dataset/blob/main/behave_demo.py)
- [BEHAVE 官方 frame reader 的拟合文件路径](https://github.com/xiexh20/behave-dataset/blob/main/data/frame_data.py)
- [BEHAVE 官方 train/test split](https://datasets.d2.mpi-inf.mpg.de/cvpr22behave/split.json)
