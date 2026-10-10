# 怎样进入现有 SAM3D/MHR 训练

本轮完成数据生成，不启动新的 GPU 训练。两种数据不能混用同一种真值字段。

|数据|可直接监督|不可直接监督|
|---|---|---|
|原 native_scale_v2|原生 MHR 对应顶点、Pose/Shape/Scale、body-camera translation、RGB-D|摄影纹理及真实衣物外观|
|本轮 HuMMan-Recon 再渲染|虚拟相机 K/R/t、公制可见衣物表面、mask、RGB-D 对应、多视角外观|原生 MHR face/vertex 对应、MHR Pose/Shape/Scale、解剖点、裸皮肤表面|

虚拟相机外参 **不是** MHR 的 pred_cam_t 标签。后者依赖人体模型的局部原点；扫描体的包围盒中心不能冒充 MHR 骨盆原点。禁止将扫描顶点按序号直接与 MHR 顶点计算误差，禁止填零人体参数伪装监督。

## 推荐的第一轮对照

1. 保留同一套原生 MHR 训练、开发划分及 Body 参数损失，作为可比基线。
2. 在 HuMMan 再渲染 TRAIN 上补充可见表面几何训练批次：从有效输入 Depth 反投影米制 XYZ，输入公制 Camera-only 分支；RGB Body 路径保持 Official，避免再次由 Depth 改坏人体参数。
3. 以可见表面的几何/深度残差提供弱几何监督，明确这是衣物外表面监督。对有明显宽松衣物的部位，不能把该监督解释为裸身体型或穴位精度。训练损失权重与 sampling 在后续实验执行前冻结。
4. 用新源身份 VAL 检查渲染域泛化，并保持既有 HuMMan 真实开发集及 Camera B 点集，只作独立开发评价。新数据已经排除了既有28个 HuMMan 身份和官方 Recon TEST 身份。
5. 比较“原数据”和“原数据＋摄影纹理扫描再渲染”，固定模型、训练预算和三个 seed，才可判断丰富外观是否真的有帮助。不要同时改网络、损失与数据后将改善全部归给纹理。

当前训练脚本 r3_common.py 的 TRUTH_KEYS 需要原生 MHR 参数；新样本没有这些字段，**不能直接塞进原参数监督 loader 并声称已可训练**。后续只需在有原生真值批次计算参数监督，在扫描批次计算几何监督；这是待实现的训练接入，未在本轮冒充完成。

## 样本格式

`samples/*.npz`：

- rgb：uint8，480×640×3。
- depth_clean_m：人体可见外表面的精确虚拟相机轴向 Z；背景0。
- depth_m：添加量化、高斯噪声、随机孔洞和边界孔洞的输入 Z；无效0。
- depth_scene_clean_m：人体＋地面的干净 Z；无有限表面的背景0。
- mask：人体可见 mask；bbox 从该 mask 计算。
- K、R_world_to_camera、T_world_to_camera：原图尺寸下的相机合同。
- source_asset_id：指向 geometry 中的共享扫描体。

`geometry/*.npz` 保存 vertices_scene_m、faces、source_to_scene_R/t。相机表面顶点按 `vertices_scene_m @ R.T + t` 得到。原摄影纹理仍由源 OBJ/MTL/PNG 提供。

噪声不是 Kinect 的完整物理模拟：本轮只有公制 Z 噪声、1mm量化与孔洞，没有 RGB-D 配准偏移、多径、材质相关深度缺失或完整相机畸变。后续升级应明确增加哪些因素，不能仅称“真实深度噪声”。
