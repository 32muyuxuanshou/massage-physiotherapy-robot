# SKEL 训练样本独立验收器

## 独立性边界

本验收器不导入、调用或复制 `training_export_core`、Blender MCP bridge、穴位标注插件中的生成函数。普通 Python 独立完成相机矩阵、投影、图像/Depth/Mask 和哈希检查；第二个全新 Blender 进程只负责 evaluated mesh 与 `scene.ray_cast` 复算。

它不会保存 Blend，也不会修改插件、模板、Atlas 或正式 ZIP。所有报告必须写入 `outputs/BlenderMCP/workstreams/independent_verifier` 或本目录。

## 运行方法

使用 MCP 虚拟环境中的 Python（含 Pillow）与 v2.3 便携 Blender：

```powershell
& 'E:\项目-按摩理疗机器人\AI感知模块\标注工具\blender_mcp\.venv\Scripts\python.exe' `
  'E:\项目-按摩理疗机器人\AI感知模块\标注工具\blender_mcp\workstreams\independent_verifier\verify_sample.py' `
  --sample 'E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-27_19-10-16\sample_000001' `
  --scene-blend 'E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-27_19-10-16\verification_scene_snapshot.blend' `
  --blender-exe 'E:\项目-按摩理疗机器人\AI感知模块\发布\医生穴位标注工作台_v2.3.0_完整版\医生穴位标注工作台_v2.3.0_完整版\runtime\blender\blender.exe' `
  --compare-sample '<第二次独立重导出的样本目录>' `
  --require-rgbd `
  --output '<独立验收报告.json>'
```

若要验证生成器“重新打开后再次导出”的一致性，必须提供生成器独立产生的第二份样本：

```text
--compare-sample <第二份样本目录>
```

## RGB-D 文件契约

完整样本必须至少包含：

```text
rgb.png
scene_depth_z.npy       # H×W、C-order、严格 float32、米、OpenCV camera Zc
depth_valid_mask.png    # 单通道语义，像素只能是 0 或 255
skin_mask.png           # 当前场景可见的 SKEL 皮肤，像素只能是 0 或 255
labels.json
```

编码规则：无首个场景交点的像素 `depth=0, valid=0, skin=0`；首个交点是 SKEL 皮肤时 `valid=255, skin=255`；首个交点是床、骨架或外部遮挡物时 `valid=255, skin=0`。Depth 始终记录场景首个表面的 `Zc`，不能用 body-only depth 冒充。

严格模式同时要求 `labels.json` 包含如下固定契约，字段值必须逐字一致：

```json
{
  "buffers": {
    "scene_depth_z": {
      "file": "scene_depth_z.npy",
      "dtype": "float32",
      "unit": "m",
      "meaning": "OPENCV_CAMERA_Z_FIRST_VISIBLE_SCENE_SURFACE",
      "background_value": 0.0
    },
    "depth_valid_mask": {
      "file": "depth_valid_mask.png",
      "dtype": "uint8",
      "values": [0, 255]
    },
    "skin_mask": {
      "file": "skin_mask.png",
      "dtype": "uint8",
      "meaning": "VISIBLE_SKEL_SKIN_FIRST_SURFACE",
      "values": [0, 255]
    }
  }
}
```

若提供 `--compare-sample`，两个样本除允许忽略的时间/临时路径字段外，labels 和 RGB 解码像素必须相同；严格 RGB-D 模式下 Depth 必须逐元素完全相同，两个 Mask 必须逐像素完全相同。

在发布核心或变更渲染管线时进行的严格验收，还必须另附一份只读 `verification_scene_snapshot.blend`，并在 `labels.json` 写入 `source_scene_snapshot_sha256`（或 `scene.snapshot_sha256`）；二者必须完全一致。它只属于内部验收交付，不要求复制进未来的每一个训练样本，也严禁超出模型许可范围外发。只记录一个已消失的临时 `source_blend` 路径不能作为严格验收的可复现证据。

## 阈值

- world→camera 三维坐标：`1e-6 m`
- 相机投影：`1e-3 px`
- 重心坐标和：`1e-6`
- 法向长度/方向复算：`1e-5`
- scene depth 与独立射线：`max(2 mm, 0.1% × Zc)`
- 可见穴位所在像素深度与穴位 Zc：`10 mm`（像素中心不等于连续穴位位置，因此它只是辅助检查）
- 背景 Depth：绝对值不超过 `1e-7 m`

## PASS/FAIL 能力边界

可以证明：样本内部矩阵/投影一致、固定三角面绑定在指定场景中可恢复、RGB/Depth/Mask 尺寸一致、Depth/Mask 与场景首个射线命中语义一致、受保护正式文件未变化。

不能单独证明：医学穴位正确、未保存场景的真实渲染状态、真实 RGB-D 畸变/噪声、机器人坐标、没有被该样本实际覆盖的外部遮挡分支。

尤其是：若导出时的外部遮挡物没有保存在一份只读场景快照中，事后无法独立重建该遮挡场景。此时外遮挡只能标为 `NOT_EVALUATED`，不能判定 PASS。普通床面、骨架或其他非皮肤命中也不能冒充外部遮挡盒测试；只有标为 `EXTERNAL_OCCLUDED` 的点同时命中声明的前景对象、读取到更近的 Zc 且 `skin_mask=0` 才算通过。
