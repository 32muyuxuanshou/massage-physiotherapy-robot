# R5：HuMMan 摄影纹理 Mesh 多视角再合成

本轮根据 SURREAL、BEDLAM、BEDLAM2.0、SynBody 和 HuMMan 的方法与图，实际下载 HuMMan-Recon 的纹理扫描体，并在虚拟摄影棚重新渲染 RGB-D。旧 R3/R4 数据和模型保持原样，本轮没有启动新训练。

## 首批数据

|维度|数量/含义|
|---|---|
|源身份|12个真人源身份；9 TRAIN、3 VAL|
|源几何|48个不同动作帧 Mesh，来自23个源序列；每身份4帧|
|每个 Mesh|12个相机视角×2种光照=24图|
|实际完成|1152张；864 TRAIN、288 VAL；全量QA通过|
|图像|640×480，摄影 UV texture、衣物褶皱、头发与鞋；虚拟实体地面与 HDRI 光照|
|标签|RGB、公制 clean/noisy Depth、mask/bbox、虚拟相机 K/R/t、共享源几何|
|原生 MHR 参数标签|没有；不得按扫描顶点序号与 MHR 顶点对齐|

源身份排除了现有 HuMMan 28人及官方 Recon TEST 身份；本轮不读取封存 TEST 图像或目标。不能据此声称 Official 预训练从未见过这些来源。

最终实际数量和完整性以 [EXECUTION_LEDGER.json](EXECUTION_LEDGER.json)、[MANIFEST.json](MANIFEST.json) 和 [FINAL_DATASET_QA.json](FINAL_DATASET_QA.json) 为准。流程采用冻结的全部48帧，没有按生成后外观或模型误差挑选源帧。先看 [最终报告与全部预览入口](FINAL_REPORT.md)。

## 核查与修正

- 先验证一个扫描体的24图，再批量生成。RGB 人体 mask 与独立透视 rasterizer 对比；每图 Cycles Depth 与独立三角面 Z 计算对比。
- 源坐标采用 Kinect color_000 / OpenCV，+Y 向下；转成 Blender +Z 向上，再做居中和地面平移。几何不缩放、不形变。
- 初次预览发现人物倒置，立即停跑；错误输出隔离后重新渲染。另修正了 Cycles Depth 的定义：当前4.5版本实测为轴向 Z，不能再做一次射线距离换算。详见 [修正记录](GENERATOR_FIX_RECORD.json)。
- 射线解析例、大三角形、前后遮挡通过；全量1152帧 QA 及缓存文件 SHA 验证通过。
- 噪声输入与干净几何标签分开：2mm基础高斯噪声＋每米0.7mm、1mm量化、1%随机孔洞、15%边界孔洞；并非完整 Kinect 物理模拟。

## 文件在哪里

- AutoDL：`ssh -p 39846 root@connect.cqa1.seetacloud.com`。
- 数据根：`/root/autodl-tmp/rgbd_sam3d/datasets/synthetic/humman_recon_r5_v1`。
- 原扫描体：`source/<sequence>/textured_meshes`。
- 合成数据：`dataset/samples/*.npz`；共享几何：`dataset/geometry/*.npz`。
- 可直接看的图：`previews`，以及 `dataset/renders/*.png`。
- 本地制作目录：`E:/项目-按摩理疗机器人/output/r5_synthetic_enrichment_v1`。
- 持久备份：`172.18.6.218:/raid5/xuhd/rgbd_sam3d_backups/r5_textured_resynthesis_v1`，回执列出实际文件与 SHA。

下载显式禁用代理。HF 官方域名直连失败时，使用同一不可变 revision 的 HF 镜像；服务器直连206通过，144个源文件的服务器/本地 SHA 完全相同。没有经本地 FlClash 中转。见 [下载证据](DIRECT_DOWNLOAD_POLICY.json)、[服务器回执](SERVER_DOWNLOAD_RECEIPT.json)。

合成数据已完整上传并解压，服务器1152个样本 SHA 复核通过：[服务器数据核查](SERVER_DATASET_QA.json)、[生成数据传输回执](SERVER_GENERATED_RECEIPT.json)。源与生成数据压缩包均已备份并校验：[源备份](SOURCE_BACKUP_RECEIPT.json)、[生成备份](BACKUP_GENERATED_RECEIPT.json)。

## 阅读顺序

1. [论文启发与采用范围](LITERATURE_TO_IMPLEMENTATION.md)。
2. [训练接入：什么标签有、什么没有](TRAINING_INTEGRATION.md)。
3. [冻结源帧、身份、相机、光照](RENDER_PLAN.json)。
   逐图简明表：[SAMPLE_INDEX.csv](SAMPLE_INDEX.csv)；完整相机矩阵与记录仍在 MANIFEST.json。
4. [实际生成代码与命令](../../../../research/rgbd_sam3d_mhr/synthesis_r5/README.md)。
5. [来源与许可](SOURCE_LICENSES.md)。

## 这轮说明了什么

可以用已有真人 Mesh + texture 生成姿态固定、相机可控、RGB/Depth一致的新数据，避免继续依赖纯色条纹人体。但当前只是12人首批、一个摄影棚、两个仰角，并不覆盖最终俯卧裸背场景，也没有证明任何模型因它变准。

下一项应做固定预算的“旧数据／旧数据＋新再渲染”对照，再考虑扩源身份、动作、相机距离与场景。先接入扫描几何监督；保留原生 MHR 参数监督，不用不存在的参数标签启动训练。
