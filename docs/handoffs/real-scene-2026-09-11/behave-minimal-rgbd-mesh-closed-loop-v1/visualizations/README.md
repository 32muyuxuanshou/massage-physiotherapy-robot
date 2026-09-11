# Server-only visualizations

BEHAVE 许可禁止公开再分发数据。本目录因此不包含真人 RGB 或 overlay。

完整逐帧可视化位于服务器：

`/raid5/xuhd/behave_rgbd_mesh_v1/output/visualizations`

目录含：

- `inference/<sample>/`：Camera A 原图、Official overlay、Txyz overlay、triptych；
- `evaluation/<sample>/`：Camera B 原图、Official-from-A overlay、Txyz-from-A overlay、triptych；
- `montages/`：推理与考试总览。

逐文件大小和 SHA256 见 [`../report/server_visualization_manifest.json`](../report/server_visualization_manifest.json)。
