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
