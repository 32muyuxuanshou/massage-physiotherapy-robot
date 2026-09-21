# 三个可研究的论文 Idea：RGB-D Mesh 与穴位定位

日期：2026-09-21  
用途：研究选题比较，不代表已完成实验。

## 写作依据

本轮使用 `oral-paper-skill` 的三个做法：

1. 把研究张力写成一个具体的未满足要求，而不是泛泛说“现有方法不够好”；
2. 明确贡献改变了什么表示、操作或输出；
3. 每个结论旁边指定真正能支持它的实验，区分代理指标、训练尝试和最终能力。

这些做法来自对 Oral 论文摘要的归纳，不是录用定律，也不代表完整阅读了所有 Oral 论文。可参照 [Probabilistic Learning to Defer](https://iclr.cc/virtual/2025/oral/31728) 的“缺失专家标注—可控人工负担”张力、[Return of Unconditional Generation](https://neurips.cc/virtual/2024/oral/97963) 对表示改变的贡献表达、[RedTeamCUA](https://iclr.cc/virtual/2026/oral/10006549) 对不同失败量的分开报告，以及 [Training on the Test Task Confounds Evaluation and Emergence](https://iclr.cc/virtual/2025/oral/31791) 对比较条件和数据暴露的控制。

## Idea 1：Observability-Gated RGB-D Mesh Completion

### 研究张力

SAM3D 能在完整 RGB 场景和复杂姿态中产生视觉上合理的 Mesh，但我们的 BEHAVE 结果显示，输入被裁成局部躯干后，K0 上的优化改善不一定转化为 K1/K2/K3 held-out 相机的改善。全局 Txyz/T+Pose 只能修正整体偏移或姿态，不能判断哪些身体部位有传感器证据、哪些部位只能依赖人体先验。

因此问题不是“再增加一次后处理优化”，而是：

> 在局部可见、遮挡和截断条件下，模型能否显式区分观测到的身体表面与需要结构补全的身体区域，并保持 held-out 视角的几何一致性？

### 核心贡献

1. 定义 partial-observation RGB-D MHR completion 任务：K0 RGB-D 是输入，K1/K2/K3 sensor depth 是跨相机几何证据。
2. 提出 observability-gated routing：由有效 Depth、mask 和身体部位覆盖率形成确定性的 support map；可见表面 token 进入对应部位节点，缺失部位由运动学图补全。
3. 将 SAM3D 作为 RGB/MHR 初始化，而不是输出后的修补器；最终模型一次前向输出 MHR、Mesh 和 support map。
4. 建立 FULL/UPPER/LOCAL_TORSO、跨相机、跨主体和部位级评价协议。

### 与已有工作的区别

- 相对于 SAM3D：新增的是在 MHR 回归前的 RGB-D 可见性和结构路由，不是 Txyz/T+Pose 后处理。
- 相对于 RGB-D HMR：不仅融合 RGB 与 Depth，还要求部位级可见性与 held-out sensor evidence 一致。
- 相对于 JOTR、VoteHMR：把遮挡/部分点云的思想扩展为度量深度支持的身体表面补全，并使用跨相机几何验证。
- 相对于 OSX：不是把身体拆成手脸等组件，而是围绕“观测部位—缺失部位”定义结构解码。

### 关键实验

1. SAM3D Official、SAM3D + Txyz/T+Pose、RGB-only adapter、RGB-D adapter、RGB-D + visibility、完整模型。
2. BEHAVE K0 输入、K1/K2/K3 只评价，subject-disjoint。
3. FULL、UPPER、LOCAL_TORSO；分别报告可见区域、补全区域、躯干、四肢和头部。
4. 去掉 support map、去掉 graph、去掉 cross-view surface loss 的消融。
5. 合成数据预训练，BEHAVE 真实域适配，另留一个未参与调参的自然场景测试集。

### 主要风险

- 审稿人可能认为这是 RGB-D、visibility 和 graph 的组合，创新增量不够大。必须让“support-gated routing”成为明确操作，并展示它单独解决的失败类型。
- BEHAVE 的 fitted mesh 不是绝对皮肤真值。主指标必须使用 held-out sensor depth，fitted SMPL 只能作为辅助证据。
- 如果只在 K0 变好、held-out 相机不变好，方法假设就不成立，不能用更漂亮的叠图掩盖。

### 适合定位

这是最适合当前工程基础、最适合先做的主线。它有清晰的 Mesh 方法问题，也能自然接入穴位作为下游验证。

## Idea 2：Cross-View Evidence Distillation for Single-View Mesh Recovery

### 研究张力

训练完整人体 Mesh 需要可靠三维监督，但自然场景中很难获得逐顶点医学真值。BEHAVE 拥有同步多视角 RGB-D 和相机标定；然而部署时机器人通常只需要一个视角。直接使用 fitted SMPL 会把拟合偏差当成真值，完全不使用多视角又浪费了真实传感器证据。

研究问题是：

> 能否在训练时使用所有同步视角的真实 Depth 形成一个证据教师，而在测试时只使用一个局部 RGB-D 视角，从而减少对 fitted SMPL 标签的依赖？

### 核心贡献

1. 构造 cross-view surface teacher：训练阶段使用 K0–K3 的传感器点云和标定生成一致的可见表面证据；不把 person_fit.ply 当绝对真值。
2. 训练 single-view student：学生只看 K0 RGB-D、mask 和 prompt，学习预测完整 MHR 和部位 support map。
3. distill 的对象不是最终顶点复制，而是可见表面 token、部位几何关系和跨视角一致性；测试时不访问 K1/K2/K3。
4. 研究“真实多视角证据如何弥补稀缺三维标签”这一数据/训练问题。

### 与已有工作的区别

- 相对于普通多视角 Mesh 重建：多视角只在训练端作为教师，部署端仍然是单视角模型。
- 相对于 fitted-SMPL supervision：主监督来自实际 sensor depth 和跨视角几何，而不是把拟合 Mesh 当 ground truth。
- 相对于 SAM3D：SAM3D 可作为学生初始化或 RGB teacher，但本方法的核心是证据蒸馏合同，不是对 SAM3D 输出做测试时优化。

### 关键实验

1. 只用 fitted SMPL 监督、只用 K0 sensor、cross-view surface teacher、两者联合。
2. 训练时使用 4、3、2 个相机，测试始终只用 K0。
3. 留出整台相机做评价，防止教师和测试证据泄漏。
4. 比较有无 SAM3D 初始化，比较有无 visibility token。
5. 跨 BEHAVE subject、跨动作、跨遮挡程度和额外 RGB-D 数据测试。

### 主要风险

- 如果教师由相同输入直接构造，可能只是把几何计算包装成蒸馏，缺少真正学习贡献。
- 多相机标定和同步错误会污染监督，必须保留 calibration QA 和 point-cloud overlap QA。
- 训练教师看到了 held-out 视角，论文必须明确这是训练监督，不是测试输入；正式测试时学生只能访问 K0。

### 适合定位

这是比“再设计一个 decoder”更像数据/学习策略论文的方向。如果真实 Mesh 标签不足，它可能比 Idea 1 更稳；但需要严谨实现防泄漏。

## Idea 3：Anatomy-Constrained Mesh-to-Acupoint Surface Coordinates

### 研究张力

人体 Mesh 误差和穴位误差不是同一个量：一个 Mesh 视觉上合理，不代表穴位表面位置正确；二维穴位标注又不能直接给机器人三维坐标；骨度分寸法和体表标志法还可能产生差异。

研究问题是：

> 如何把图像中的解剖标志、标准化穴位规则和预测 Mesh 表面坐标连接起来，使穴位输出可追溯、可交叉核验，而不是由网络直接猜一个 2D 点？

### 核心贡献

1. 采用 landmark-first、formula-second、surface-third 的分层接口：网络检测解剖标志，规则引擎计算候选穴位，几何模块把候选点放到 Mesh 表面。
2. 用 surface-coordinate atlas 表示穴位：保存三角面索引、重心坐标、局部躯干坐标和 RGB 重投影，而不是只保存一对像素坐标。
3. 对满足条件的点同时运行骨度分寸法和体表标志法，报告两者差异并交给医生复核。
4. 将最终指标从“2D 点是否落在热图峰值”扩展到表面三维误差、跨姿态稳定性和机器人坐标误差。

已有 CT 三维研究支持“解剖标志/骨度分寸/三维表面”的规则链；Fengshi 研究提醒我们两种定位方法可能不一致；结构引导背部穴位工作说明标志和比例可以进入学习模型。但这些工作不等于我们的 Mesh-到-机器人验证已经成立。

### 与已有工作的区别

- 相对于 2D 背部穴位检测：输出的是 Mesh 表面坐标和机器人坐标接口，不停留在图像像素。
- 相对于 CT 公式方法：输入可以是真实 RGB-D 场景，并把人体姿态、遮挡和预测 Mesh 纳入流程。
- 相对于直接把 Atlas 传播到 Mesh：不再默认 Atlas 是医学真值，而是记录公式来源、体表证据和医生复核状态。

### 关键实验

1. 5–8 个规则最清楚的背部点起步，暂不直接放行全部 DMD37。
2. 比较直接 2D detector、公式-only、Mesh atlas-only、双路径系统。
3. 报告 2D 重投影误差、Mesh 表面距离、双路径分歧、医生间一致性和机器人坐标误差。
4. 比较 Mesh 使用官方 SAM3D、Txyz/T+Pose 和新 RGB-D 模型时，穴位误差如何变化。
5. 按 FULL、局部躯干、遮挡和姿态分别评价。

### 主要风险

- 医学标注和标准公式不足时，不能声称临床准确性。
- 规则冲突可能来自标准版本、标志检测或 Mesh 误差，不能简单平均。
- 如果只拿 DMD37 或合成 Atlas 当标签，论文会被质疑医学有效性。
- 这个方向需要医生复核，因此工程速度慢于前两个方向。

### 适合定位

这是最有医学和机器人意义的方向，但不建议作为第一阶段唯一主贡献。更适合在 Idea 1 或 Idea 2 的 Mesh 稳定后作为下游任务，或者单独写成医学工程应用论文。

## 最终建议

不要把三个 Idea 同时写成三个主贡献。建议采用：

```text
主方法：Idea 1
训练/数据创新：吸收 Idea 2
下游医学验证：Idea 3
```

这样论文只有一条主线：

> 局部可见 RGB-D 证据如何通过结构补全恢复可靠 Mesh，并进一步支持可审计的三维穴位定位。

如果 Idea 1 的 held-out 几何结果不成立，就不要硬写 Idea 3 来挽救 Mesh；如果 Idea 3 没有医生标签，就把它写成几何接口和工程验证，不写成临床准确性。
