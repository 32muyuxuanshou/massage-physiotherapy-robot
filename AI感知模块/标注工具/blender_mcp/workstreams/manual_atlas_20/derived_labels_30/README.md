# Atlas v5 派生 30 场景标签（不重渲染）

该工作流接收插件 `smpl-acupoint-annotation-v5` Atlas、冻结的 30 样本父交付和一个全新的输出目录。它逐个以独立后台 Blender 进程打开 snapshot，只调用共享核心的：

- `sample_surface_binding`
- `project_world_point`
- `evaluate_visibility`

不会调用 `render_scene_buffers` 或 `export_sample`。既有 `rgb.png`、`scene_depth_z.npy`、`depth_valid_mask.png`、`skin_mask.png`、`render_metadata.json` 只以硬链接或字节复制进入新目录，并记录父/子 SHA-256；新生成的只有 `labels.json`、`overlay.png`、QC 和清单。

## 预检

```powershell
& "E:\项目-按摩理疗机器人\AI感知模块\标注工具\blender_mcp\.venv\Scripts\python.exe" `
  .\derive_labels_30.py `
  --atlas "E:\path\to\atlas_v5.json" `
  --parent-delivery "E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-28_20-21-54" `
  --output "E:\unused-for-preflight" `
  --preflight-only
```

预检不会创建输出目录，也不会启动 Blender。

## 正式派生

```powershell
& "E:\项目-按摩理疗机器人\AI感知模块\标注工具\blender_mcp\.venv\Scripts\python.exe" `
  .\derive_labels_30.py `
  --atlas "E:\path\to\atlas_v5.json" `
  --parent-delivery "E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-28_20-21-54" `
  --output "E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\YYYY-MM-DD_HH-mm-ss" `
  --asset-mode auto `
  --truth-status engineering_reference `
  --supersedes "E:\\项目-按摩理疗机器人\\AI感知模块\\outputs\\交付文件\\older-derived-delivery"
```

输出目录必须不存在，且不得位于父交付目录内部。默认 `engineering_reference` 会写 `medical_truth=false`。只有 Atlas 确实经医生确认时，才允许显式使用 `--truth-status doctor_confirmed`。

QC 不假设 20/20 可见。可见点检查既有 Depth/Valid/Skin Mask 与当前 `Zc`、反投影是否一致；不可见点保留 `BEHIND_CAMERA / OUT_OF_FRAME / BACK_FACING / SELF_OCCLUDED / EXTERNAL_OCCLUDED` 的真实分支。

`--supersedes` 可选。它仅将一个仍保留不动的旧派生目录记录为已被本轮更正 Atlas 结果取代；新交付的 README 和 QC 会把本目录声明为当前结果。
