# SKEL 穴位 Blender MCP v0.2.1

这是项目内部的受控 Blender MCP，不是通用 Blender 遥控器。它复用正式穴位插件的模型识别、拓扑
指纹和表面采样，并调用唯一的 `training_export_core` 生成训练样本。

## 边界

- Blender 端只监听 `127.0.0.1:9877`。
- 不提供任意 Python、终端或任意路径写入工具。
- 只读取 `AI感知模块` 内的 `.json/.blend` 资产。
- 新结果只写入 `AI感知模块/outputs/BlenderMCP/`，拒绝覆盖已有目录。
- 可以改变临时 Camera，但不会自动保存 `.blend`。
- 正式 Atlas 只绑定 SKEL 原生皮肤；当前 E01–E20 和 `ENG_*` 都是非医学工程点。

## 工具

1. `blender_status`
2. `start_skel_session`
3. `inspect_scene`
4. `validate_atlas`
5. `get_acupoint_3d`
6. `list_cameras`
7. `set_camera_view`
8. `export_training_sample`

`export_training_sample` 输出同一相机、同一帧、同一分辨率下的：

- `rgb.png`
- `scene_depth_z.npy`：OpenCV 相机坐标第一可见场景表面的 `Zc`，`float32` 米，背景 0
- `depth_valid_mask.png`
- `skin_mask.png`
- `labels.json`
- `overlay.png`
- `manifest.json`

导出场景必须使用公制且 `scale_length=1.0`。核心源码位于
`../blender_addons/modules/training_export_core/`，医生插件不得复制训练导出实现。

## 在 Codex 中使用

项目 MCP 配置位于 `E:/项目-按摩理疗机器人/.codex/config.toml`。Codex 只在任务启动时读取配置，
安装或更新后需要新建任务或重启 Codex。

正常路径：

1. `blender_status` 检查会话。
2. 必要时 `start_skel_session(gender="female" 或 "male")`。
3. `validate_atlas(atlas_path=...)` 校验模型、性别和拓扑。
4. `get_acupoint_3d(...)` 验证当前三维坐标。
5. `set_camera_view(...)` 设置临时相机。
6. 确认场景为公制且 `scale_length=1.0`。
7. `export_training_sample(...)` 导出，并检查 `overlay.png`。

## 代码与运行状态

- 服务：`server.py`，版本 0.2.1。
- Blender 桥接：`../blender_addons/acupoint_blender_mcp_bridge/`，版本 0.2.1。
- Python 环境：`.venv`，`mcp==2.1.1`、`Pillow==12.1.1`。
- 正式 v2.3 ZIP 未包含 MCP；这里只属于本机内部研究环境。

几何、俯卧场景、Shape/Pose、Camera、Pilot、训练与可靠性阶段的现役结论统一见
`E:/项目-按摩理疗机器人/AI感知模块/README.md`；各次实现和历史结论见 `workstreams/` 与
`outputs/内部工程证据/`，不在本工具说明中重复维护。
