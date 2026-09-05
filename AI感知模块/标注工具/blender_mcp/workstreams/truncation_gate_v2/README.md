# TRUNCATION_GATE_V2

在17个已冻结 Cross-qualified Shape×Pose 上，仅改变 Camera 横向位置，验证四个严格镜像截断 Profile：

- `TRUNC_LEFT_MILD` / `TRUNC_RIGHT_MILD`：相对 baseline Camera X 偏移 ±1.00 m；
- `TRUNC_LEFT_MODERATE` / `TRUNC_RIGHT_MODERATE`：偏移 ±1.050365525 m，保留原 C2 强度并镜像。

Gate 共17×4=68格。每格记录20点 visibility reason、投影人体 BBox 截断比例、投影顶点在画比例、Skin Mask
面积相对 baseline、Depth/Mask/反投影 QC 和固定表面绑定。全新 Blender 进程重放必须保持资格、几何、
Depth、Depth Valid Mask 与 Skin Mask 一致；RGB 哈希仍非硬门。

本阶段不含 Severe、不训练、不生成 Failure-driven Pilot V2。E01–E20 是非医学工程点，SKEL 不是患者 CT。
