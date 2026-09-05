# training_export_core

Blender 4.5 内部训练数据核心。该包与医生穴位标注 UI、MCP bridge/server 和批量生成器解耦。

主要接口：

```python
from training_export_core import export_sample

result = export_sample(
    scene=bpy.context.scene,
    depsgraph=bpy.context.evaluated_depsgraph_get(),
    camera=bpy.data.objects["ACU_TRAIN_CAMERA"],
    skin_object=bpy.data.objects["SKEL-skin-female"],
    bindings=[
        {
            "point_id": "engineering-test-only",
            "face_index": 13745,
            "vertex_indices": [6332, 3506, 6498],
            "barycentric": [0.3889733, 0.5540136, 0.0570130],
        }
    ],
    output_dir=r"E:\...\sample_000001",
)
```

正式输出：

- `rgb.png`
- `scene_depth_z.npy`：float32 米，第一可见场景表面的 OpenCV camera Z；背景 0。
- `depth_valid_mask.png`：0/255。
- `skin_mask.png`：0/255；仅第一可见表面是 SKEL 皮肤时为 255。
- `render_metadata.json`

实现约束：

- evaluated mesh 必须通过 `to_mesh()` 取得，并在 `finally` 调用 `to_mesh_clear()`。
- 渲染使用临时 Scene 和临时 compositor node tree，不修改源 Scene 节点。
- 临时 Scene 使用 `source_scene.copy()`，保留 collection、view-layer exclusion 和 holdout 语义；若 node tree 不是独立副本则拒绝导出。
- `CENTER_RAY_DEPTH_V2`：RGB 为 Eevee 单采样无滤波渲染；Depth/Valid/Skin Mask 来自同 Camera、帧、分辨率与 evaluated 几何的像素中心场景射线。Skin Mask 按首个命中对象归属生成，不再通过两张 Z 的近似相等推断。
- GPU Z/Position 和 body-only Z 仍为诊断中间产物，不作为最终深度真值。`rgb_and_scene_z_same_render=false`，但相机、帧、几何相同。RGB 光栅覆盖与中心射线可能在极少数轮廓像素有归属差异，数量写入 `raster_diagnostic`；不能宣称每个 RGB 像素的表面归属与射线完全一致。
- 对共享对象做的临时 `hide_render` 修改无论成功或异常都会在 `finally` 恢复。
- 单通道 PNG 按 `HxWx1` 写入，避免 OpenImageIO 行步长错位。
- 输出目录可以由调用方预先创建，但必须为空；核心拒绝覆盖任何已有文件。
- 默认不保留 EXR 和 body-only depth 中间产物；仅 `debug_keep_intermediates=True` 时保留。
- 射线有效深度满足 `clip_start <= Zc < clip_end`；未命中为 0。Eevee 原始 Z 的远平面保护带仅用于诊断，不影响最终射线深度。
- 正式字段使用米，因此第一版严格要求 `METRIC` 且 `scale_length == 1.0`。
- `export_sample(frame=...)` 要求调用方已把 `scene.frame_current` 设置为同一帧，确保 evaluated mesh、射线与渲染描述同一时刻。
- 本包不负责医学正确性、最终 Atlas schema、真实 RGB-D 畸变/噪声或机器人坐标。

2026-08-28 的 30 样本预检揭示旧默认 Eevee 64 samples 在一个脚部轮廓像素输出皮肤深度，但中心射线命中床面，误差 0.250223 m。单采样移除 jitter 后仍有少数 GPU 轮廓覆盖差异，因此最终几何缓冲改用中心射线，未放宽 QC 阈值。此前少量射线抽检通过不等于旧渲染具有严格逐像素中心深度合同。

中心射线仅验证了当前不透明、视口/渲染几何一致的 SKEL/床/遮挡网格。透明材质、体积、同位面竞争、holdout 与渲染专用细分不在已验收范围；景深和运动模糊开启时拒绝导出。
