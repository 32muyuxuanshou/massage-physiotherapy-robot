# Track B 只读资产审计

本目录只记录现有资产和桥接能力，不放行 MHR 原生 DMD37 Atlas。审计结论为 `BRIDGE_UNCERTAINTY_REQUIRES_REVIEW`。

用户复核的当前 37 点资产确实存在，`.blend` 与上一 handoff 记录的 SHA-256 完全一致。它包含 `ENG_D01–ENG_D37`，绑定在 male SKEL 1.1.1 的 6,890 顶点、13,776 三角面皮肤上；它仍是工程参考，`medical_truth=false`。旧的 female-SKEL E01–E20 是另一套资产，不能混用。

服务器实际 SAM 3D Body runtime 使用 MHR LOD 1。TorchScript 实测为 18,439 顶点、36,874 三角面，face hash 是 `f6748e…eacd6`，MHR asset hash 是 `352e27…77bc`。TorchScript 本身没有可读的 LOD/version 字段，LOD 1 由 SAM wrapper 源码、固定输出维度和官方 LOD1 转换 mesh 的精确 face-array 一致性共同确认。

仓库中的官方 MHR 工具不只有 MHR→SMPL-X，还包含 MHR↔SMPL 和 MHR↔SMPL-X 四套双向重心映射。现有共享草稿只走了项目自制的 SKEL→SMPL-X 规范近邻，再接官方 MHR→SMPL-X，漏掉了与当前 6,890 拓扑直接相关的官方 MHR→SMPL 候选。两条路线尚未做同口径差异、测地距离、左右/中线/对称和背部区域检查，因此当前 `PASS_DMD37_MHR_ENGINEERING_ASSET` 证据不足。

完整哈希、路径、数值检查和下一步见 [TRACK_B_READONLY_ASSET_AUDIT_V1.json](TRACK_B_READONLY_ASSET_AUDIT_V1.json)。
