# 复现入口与缓存核验

已有完整数据位置见 `BACKUP_RECEIPT.json`。渲染、打包、核验代码在 `code/`；原始扫描与摄影纹理只在受控数据存储中。全部过程不需要 SAM3D 权重，不训练模型。

## 在现有服务器检查缓存

```bash
ROOT=/raid5/xuhd/rgbd_sam3d/r5_controlled_camera_v2
PY="$ROOT/runtime/blender-3.3.21-linux-x64/3.3/python/bin/python3.10"
export PYTHONPATH="$ROOT/runtime/pack_deps"
"$PY" "$ROOT/code/verify_dataset.py" --root "$ROOT/dataset" --source "$ROOT/source" --plan "$ROOT/RENDER_PLAN.json"
"$PY" "$ROOT/code/verify_camera_factors.py" --root "$ROOT/dataset"
"$PY" "$ROOT/code/controlled_previews.py" --root "$ROOT/dataset" --out "$ROOT/previews" --plan "$ROOT/RENDER_PLAN.json"
```

指标与图片读取已保存数据，没有重新拟合人体。

## 在独立目录重新生成

准备新的工作根目录，不将原数据输出目录作为新的生成目标。目录包含 `source/`、`code/`、`assets/`、`runtime/`、`dataset/`、`logs/` 及本交付的 `RENDER_PLAN.json`。源48组 OBJ/MTL/texture 可从完整数据备份恢复；`make_controlled_plan.py` 也可从前一轮冻结计划重建本轮计划。

运行时使用 Blender **3.3.21 / e016c21db151**，归档下载地址：
`https://mirrors.ocf.berkeley.edu/blender/release/Blender3.3/blender-3.3.21-linux-x64.tar.xz`。
下载使用 `curl --noproxy '*'`；运行时与 HDRI SHA256 在 `ENVIRONMENT.json`。照明素材为 Poly Haven 的 `studio_small_03_1k.hdr`，下载地址：
`https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_03_1k.hdr`。

Blender Python 3.10 的独立打包依赖：numpy 1.24.4、numba 0.58.1、llvmlite 0.41.1、opencv-python-headless 4.8.1.78、Pillow 10.4.0。安装在 `runtime/pack_deps`，不更改系统 Python/驱动。

```bash
"$PY" "$ROOT/code/run_controlled_batch.py" --root "$ROOT" --workers 8
```

`ROOT`、`PY` 须先设置成新的工作目录及其运行时路径；八个 worker 分别使用 CUDA GPU 0–7。CPU / CUDA 64图试运行见 `PILOT_QA.json`，OptiX 崩溃案例未用于全量渲染。

## 本次执行的实际收尾

主批完成渲染、打包及全量哈希核验后，首次 camera-factor QA 在47图超过过严的1微米数值容差。修复 float32 容差后单独重做缓存 camera QA 与全量预览，使用 `finish_ledger.py` 收尾；最终又补齐 elevation 组的64/64相机覆盖检查。没有重新生成或变更任何样本。`EXECUTION_LEDGER.json` 与 `NUMERICAL_QA_FIX.json` 保留该过程。

`SERVER_CODE_RECEIPT.json` 核验11个生成/评价模块在工作区、交付和服务器之间逐字节一致；`CODE_SOURCE_SHA256.json` 另包含独立试运行核验与缓存收尾脚本的哈希。完整交付文件哈希见 `FILES_MANIFEST.json`。
