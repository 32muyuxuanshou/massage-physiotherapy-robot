# HuMMan textured RGB-D resynthesis

Source: HuMMan-Recon textured OBJ/MTL/PNG, retained unchanged. Native MHR GT is **not** available for these scan vertices. This is a separate corpus from `native_scale_v2`.

1. Download only the 48 frozen assets from the immutable ZIP revision. No proxy inheritance:

```powershell
python fetch_assets.py --plan RENDER_PLAN.json --out source --download-url "https://hf-mirror.com/datasets/caizhongang/HuMMan/resolve/56a2a9a12e21abe10744580f96989534cdbdff76/humman_release_v1.0_recon/recon_textured_meshes.zip?download=true"
```

`requests.Session.trust_env=False` bypasses environment and system HTTP proxies. Server-side direct HTTPS was tested with HTTP 206. If transparent network tunnelling is enabled on a different host, this flag alone does not override its routing; use the documented server route.

2. Render in Blender 4.5.12. Use absolute paths:

```text
blender --background --factory-startup --python-exit-code 1 --python render_blender.py -- --plan RENDER_PLAN.json --source source --out dataset --hdri studio_small_03_1k.hdr
```

`--offset`, `--limit-assets`, `--threads` allow two disjoint CPU chunks. They do not change source poses, texture, camera or depth noise. Geometry uses metres, source OpenCV +Y down → scene +Z up. Source geometry is only rigidly centred/placed on the studio floor, never rescaled.

3. Package and verify:

```text
python geometry_sanity.py
python pack_dataset.py --root dataset --plan RENDER_PLAN.json
python make_previews.py --root dataset --plan RENDER_PLAN.json --out previews
```

Blender Cycles Depth in the tested version is **axial Z**, not radial distance. An independent triangle rasterizer verifies the object mask and eroded-interior Z for every frame. `geometry_sanity.py` verifies perspective interpolation, large-triangle coverage and foreground occlusion.

Dependencies for ordinary Python: numpy, numba, OpenCV, Pillow, requests, remotezip. Rendering uses Blender's bundled bpy/numpy. Version evidence is in the delivery `ENVIRONMENT.json`.

Scientific notes, frozen plan, source hashes, QA and previews: [R5 delivery](../../../docs/handoffs/real-scene-2026-10-10/humman-textured-resynthesis-r5-v1/README.md).

## Controlled camera V2

`make_controlled_plan.py` preserves the 48 source scans and 9 TRAIN / 3 VAL identities,
but replaces auto-fit cameras with 64 explicit configurations per scan (3,072 images).
Main groups use fixed focal length: independent distance, yaw, elevation, optical-axis roll
and off-centre placement. Separate focal and matched-angular-size groups expose image-size shortcuts.
Near views can truncate the body; these are retained and flagged, never silently re-centred.
Lighting stays in world coordinates. Scan bounding-box midpoint Z is a documented reference,
not an MHR root label. No native MHR body/Camera parameter GT is inferred from these scans.

The renderer supports `--device CUDA --device-index N` and disjoint asset slices.
The current CentOS 7 / NVIDIA 510 host uses an isolated Blender 3.3.21 runtime, Filmic,
16 Cycles samples, CPU denoising, and RGB-channel EXR passes. Axial depth is independently
verified, not assumed from Blender version. OptiX crashed during sequential pilot rendering;
CUDA completed the full 64-camera pilot and is the batch device. The previous V1 results remain intact.

`run_controlled_batch.py --root /absolute/task/root --workers 8` launches eight disjoint
render/pack lanes, merges all sample manifests and runs `verify_dataset.py`,
`verify_camera_factors.py` and `controlled_previews.py`. Complete JPEGs and an offline HTML
gallery allow reviewing every image without opening NPZ files. Geometry/camera QA establishes
simulator consistency only; it does not validate source anatomy, actual sensors or model accuracy.
