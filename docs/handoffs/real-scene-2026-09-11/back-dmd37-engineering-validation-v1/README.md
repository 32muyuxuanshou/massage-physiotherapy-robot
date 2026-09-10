# Back / DMD37 工程验证 V1

这轮停止继续训练 SAM，因为当前全身 Mesh 已经从 Official 的约 63.6 mm absolute error 改善到 C 的 22.5 mm、G 的 23.9 mm，但这些数字仍是 HuMMan 穿衣全身外表面，不能回答后背或 37 个工程点是否更准。本轮把全身 Mesh 与背部工程点真正接起来，并在证据不足时保持 Gate 关闭。

## 已完成什么

### 1. 后躯干真实数据盘点

只使用已经消费的 SYSTEM_SEALED 池，没有打开 15 人 Final Deep Reserve。池内共 4 人、10 个动作、36 帧；根据冻结元数据初筛出 24 帧后背可见候选，12 帧非后背或不确定候选。

当前没有独立 Camera-B 后躯干 polygon/mask。动作名和历史 view 标签只能筛选，不能当像素真值，更不能从 O/A/C/G Mesh 反推区域再评价自身。因此 Posterior Torso Gate 是 `POSTERIOR_GEOMETRY_NOT_READY`，O/A/C/G 的 posterior absolute、aligned、P90/P95、coverage 都不报告。这里准确术语是 **posterior clothed torso outer surface**，不是裸背皮肤。

### 2. MHR topology 与 DMD37 Atlas 候选

运行时已实测为 MHR `lod=1`，18,439 顶点、36,874 面；faces SHA256（int32 C-order）为 `f6748e290ef37fbb6877c4cc5bd7287105db9e98252b0ba170ae9ac3c45eacd6`，MHR asset SHA256 为 `352e271a6c42729c68554ceaea0c955e866970160c31e35506d782dc0f7377bc`。

复核后的 37 点来自 male SKEL 1.1.1 / 6,890 顶点 / 13,776 面，它的皮肤面拓扑与 SMPL 相同。我们比较了两条桥：

- 新候选：37 点的 SMPL 支撑顶点通过官方 `mhr2smpl_mapping.npz` 落到 MHR，再投影到唯一最近的 MHR 三角面。
- 历史链：SKEL→SMPL-X 最近规范顶点，再通过官方 MHR→SMPL-X 映射。

新候选到最终单一 MHR 三角面的最大投影间隙为 0.7565 mm，37/37 点重放误差为 0，左右符号和中线检查通过。历史链与直接链平均相差 19.92 mm、P95 29.03 mm，说明历史桥不应继续默认使用。

Atlas Gate 仍是 `BRIDGE_UNCERTAINTY_REQUIRES_REVIEW`。原因不是数值无法重放，而是“组合三个官方对应点后投影到单一最近 MHR 面”的规则没有在看结果前冻结，且两条桥差异较大。需要一次独立工程复核后，才能把候选标成正式 MHR-native 工程资产。它始终是 `medical_truth=false`。

### 3. 参数误差如何传到 37 点

在服务器上使用 14 个此前已消费/复核的真实图像 SAM MHR 状态，完成 196,840 条逐点敏感性观测。它不经过 RGB 网络，只回答 MHR 参数变化会怎样移动当前 Atlas 候选。

| 扰动 | 37点3D中位 | P95 | 解释 |
|---|---:|---:|---|
| Translation 10/20/50/100 mm | 10/20/50/100 mm | 同左 | 平移一比一传到全部点，aligned 后为 0 |
| Global rotation 1°/3°/5° | 4.16/12.48/20.79 mm | 8.90/26.69/44.48 mm | 上背、颈肩最敏感 |
| Spine pose 1°/3°/5° | 1.24/3.71/6.19 mm | 7.22/21.65/36.08 mm | ENG_D01–D04 等上背点最脆弱 |
| Shoulder pose 1°/3°/5° | 0.03/0.09/0.15 mm | 0.74/2.21/3.68 mm | 总体中位被不受该参数影响的点稀释；肩外侧单点 P95 可约 12 mm |
| Shape 0.25/0.5/1.0 PCA | 0.58/1.16/2.32 mm | 6.40/12.79/25.58 mm | 腰背下段 ENG_D32–D35 最敏感，且主要表现为法向变化 |
| Scale 1%/3%/5% 参数增量 | 0/0/0 mm | 0.47/1.41/2.35 mm | 单个 scale 参数只影响局部；上背最坏约 3.9 mm |

Normal/tangential 使用基准 MHR anchor 三角面的几何法向。它是 Mesh 几何分解，不是组织法向。详细总体和逐点结果在 `DMD37_PARAMETER_SENSITIVITY_V1.json` 与 `DMD37_NORMAL_TANGENTIAL_SENSITIVITY_V1.json`。

## 为什么没有继续做 Synthetic 和选 Teacher

Synthetic 的 GT 可以精确，但必须先接受 Atlas 规则，否则只会精确评价一个尚未固定的工程定义。当前已冻结 smoke/clean/stress 协议草案，没有越过 Gate 生成图片或训练数据。

因此当前不能根据全身结果直接选 Teacher。C 仍是更快、absolute placement 更强的候选；G 仍是 aligned、P95、coverage 和困难样本更强的候选。哪一个更适合 DMD37，必须由同一批独立 posterior pixels 与 synthetic exact DMD37 GT 决定。当前状态为 `NO_SYSTEM_READY_FOR_DMD37_TEACHING`。

## 当前决定

- Posterior Torso Gate：`POSTERIOR_GEOMETRY_NOT_READY`
- MHR DMD37 Atlas Gate：`BRIDGE_UNCERTAINTY_REQUIRES_REVIEW`
- Atlas replay：37/37，100%，最大重放误差 0 mm
- Synthetic DMD37 Gate：`NOT_READY`
- Final Engineering Gate：`PASS_MESH_SYSTEM_BUT_DMD37_NEEDS_MORE_WORK`
- DMD37 engineering pseudo-label：`NOT_READY`
- RTMPose engineering training：`NOT_READY`
- 医学穴位更准：不能声称

当前最大缺口仍是真实产品域：没有治疗床裸背 RGB-D、医生真人穴位、机器人遮挡/接触与产品相机噪声。Synthetic 不能关闭这个风险。

下一步唯一建议是：在不显示 O/A/C/G overlay 的界面里，对已经消费的 36 帧 Camera-B RGB、Depth 与 person mask 独立标注 posterior clothed torso；完成后立刻跑冻结的 O/A/C/G posterior benchmark。这样才能知道全身 Mesh 改善是否真的服务背部工程点。
