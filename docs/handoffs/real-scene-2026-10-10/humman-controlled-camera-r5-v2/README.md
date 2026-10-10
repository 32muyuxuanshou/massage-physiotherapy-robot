# R5 V2：带纹理人体的受控相机 RGB-D 合成

承接 [首批 1,152 图](../humman-textured-resynthesis-r5-v1/FINAL_REPORT.md)。本轮专门增加独立距离、视角、俯仰、相机 roll 和画面偏心变化，生成目标为 **12 身份 × 4 源 Mesh × 64 相机 × 1 固定光照 = 3,072 图**。实际完成数量、QA 和保存回执以 FINAL_REPORT.md 为准。

输入为已有官方 HuMMan-Recon 的 OBJ/MTL/摄影纹理；保持 9 TRAIN / 3 VAL 身份划分及全部 48 源帧，不读取 TEST。扫描 Mesh 不形变、不缩放；每个固定 Mesh 单独改变物理相机。重复视角不算新的真人或动作。

旧生成器根据人体大小和焦距自动移动相机以容纳全身。V2 改为显式公制距离，主组焦距固定为 400 px。近距离或高焦距产生的截断保留并标记；灯光固定在场景坐标，避免随相机移动。RGB、Depth、mask、内外参共同生成；相机 roll 不是单独旋转 RGB 图片。

## 本轮文件

- `RENDER_PLAN.json`：冻结源身份、姿态、64 相机和光照。
- `CAMERA_CONFIGS.csv`、`SAMPLE_INDEX.csv`：可读的配置与全部样本索引。
- `MANIFEST.json`：每个 NPZ 的路径、SHA256、坐标、标签与截断标志。
- `PILOT_QA.json`：CPU / CUDA 64 图比较，几何字段逐数组 exact，实际渲染几何检查。
- `GEOMETRY_QA.json`：全部样本的独立透视三角面 Z 与 Blender pass 对照。
- `CAMERA_FACTOR_QA.json`：根据实际保存的 R/t 检查距离、偏心和固定 K/R 合同。
- `FINAL_DATASET_QA.json`：全部样本哈希、源→场景坐标、身份划分和 normals 检查。
- `ENVIRONMENT.json`、`EXECUTION_LEDGER.json`、`CODE_SOURCE_SHA256.json`、`BACKUP_RECEIPT.json`：环境、执行、代码与备份证据。
- `previews/`：因素对照图；全量 JPEG、48 张联系图和可筛选离线网页在私有可视化包中。
- `REPRODUCE.md`：运行时、依赖、重新生成与缓存核验的具体入口，以及本次实际收尾过程。

## 数据位置与重跑

主机 `ssh -p 436 xuhd@172.18.6.218`。

工作根目录：`/raid5/xuhd/rgbd_sam3d/r5_controlled_camera_v2`。

NPZ：`dataset/samples/`；实际 RGB PNG：`dataset/renders/`；共享扫描几何：`dataset/geometry/`；JPEG 与网页：`previews/rgb/`、`previews/index.html`。

```bash
ROOT=/raid5/xuhd/rgbd_sam3d/r5_controlled_camera_v2
$ROOT/runtime/blender-3.3.21-linux-x64/3.3/python/bin/python3.10 \
  $ROOT/code/run_controlled_batch.py --root $ROOT --workers 8
```

八个 worker 各处理 6 个 Mesh，使用不同 CUDA GPU，渲染后只打包自己的样本，再合并核验。已生成文件必须沿用对应冻结计划和代码，不应把它作为修改配置后覆盖历史输出的命令。

## 标签与证据边界

每图保存 RGB、clean/noisy 人体轴向 Z、clean 场景 Z、mask/bbox、K/R/t、可见三角面 ID、相机朝向的几何法线和扫描包围盒中心的相机坐标。完整 Mesh 共享存储。

**扫描包围盒中心不是 MHR 根节点。** 本批有虚拟相机和扫描表面几何，但没有原生 MHR pose/shape/scale 或对应顶点真值，不能直接填入旧参数监督 loader。当作摄影外观与可见表面监督数据使用；原生 MHR 数据仍提供其真实参数标签。

几何 QA 说明同一虚拟表面在 RGB、Depth、相机之间一致；不等同扫描人体精度、真实传感器精度或临床穴位准确率。本批主要是既有直立/动作扫描，不把相机倾斜称作俯卧姿态。

## 采用的公开方法

[BLADE / BEDLAM-CC](https://github.com/NVlabs/blade/blob/main/docs/BEDLAMCC_GENERATION.md) 提供独立近距离和透视变化的启发；[BEDLAM2 相机生成](https://github.com/PerceivingSystems/bedlam2_render/tree/main/tools/sequence_generation) 提供人体/相机因素分开设计的启发。复用本项目 Blender 管线，未声称复现其整个数据生成系统。

源扫描和 HDRI 的授权、引用见 [SOURCE_LICENSES.md](SOURCE_LICENSES.md)。原始数据、完整生成数据、权重和论文全文不进入 Git；Git 保留代码、配置、索引、QA、报告与有限预览。
