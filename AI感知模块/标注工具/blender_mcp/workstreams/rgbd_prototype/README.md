# RGB-D / Mask 隔离原型

本目录只用于验证 Blender 4.5 的 Z Pass、Position Pass、对象索引和 canonical SKEL 的可见皮肤 Mask。它不是正式插件代码，也不会保存 canonical Blend。

主脚本：`run_rgbd_prototype_blender.py`  
隔离核心：`rgbd_core_experimental.py`

运行方式由根任务统一控制。输出只能写入：

`AI感知模块/outputs/BlenderMCP/workstreams/rgbd_prototype/`

严禁把本原型直接复制进医生主界面；正式集成应迁入独立 `training_export_core` 并重新做独立验收。

