# R5 Camera-only 夜间执行计划

时间：2026-10-10 夜间 → **2026-10-11 09:00（北京时间）**。实际开始准备23:54；00:22确认218 CUDA可用。状态与运行日志以 `EXECUTION_LEDGER.json` 为准，本文不是已完成结果。

## 目标

回答：**保持 Official 的全部人体输出，单独学习公制 Camera，能否比原来的耦合 G1 更稳？新带纹理、多距离/视角的数据，是否提供额外几何价值？**今晚不重新训练SAM3D全部权重，不增加fine/gating、不进入穴位模型。

## 连续队列及优先级

|北京时间（预计窗口）|执行内容|必须留下的证据|
|---|---|---|
|23:54–00:45|218环境、已有数据/权重核实；旧TRAIN/VAL缓存压缩迁移；Camera头能力范围与正向QA|CUDA实测、迁移SHA、范围审计、Body精确保持、缺Depth回退|
|00:45–02:00|Camera-only原生GT训练；三个头各seeds11/23/37，先检查首个epoch再继续30epochs|9个best/last、逐seed曲线、400张VAL逐身份指标|
|同时，约00:45–03:00|3,072张新scan只做冻结Official RGB初始化；5卡分片；所有视角/截断保留|完整MHR输出、K、原始/更新Camera、输入SHA、无伪root标签|
|02:00–06:30|若scan初始化和梯度检查完成：以同一native预训练状态比较继续native-only vs加入scan表面弱监督；各3seeds，追加20epochs；先冻结TRAIN梯度量级校准|native曝光/更新次数一致、额外scan计算单列、固定权重回执、逐seed曲线|
|06:30–08:15|冻结checkpoint后Depth消融、scan条件分组和真实232帧评价；保留Official＋Txyz强基线|正确/扰乱/缺失Depth、独立B表面评价、P95失败、实际耗时|
|08:15–09:00|不启动新训练；已运行训练在完整epoch边界保存；生成图表、结果包、本地备份与Git交付|完成/部分/失败分别记录、SHA回执、最终目录及commit|

窗口是排程上限，不是承诺每阶段耗满。提前完成即推进下一项；到截止仍未完成就保存实际进度，不补造结果。依赖任务失败时只修具体执行问题，不悄悄换合同。

## 数据与边界

- 原生MHR：400 TRAIN身份×8＝3,200张；50 VAL×8＝400张；TEST400张封存，缓存导出也不读取TEST。
- 新带纹理scan：9 TRAIN/2,304张，3 VAL/768张；48个固定扫描Mesh×64个物理相机；464张截断图保留。扫描中心/世界外参不是MHR root，绝不充当Camera GT。
- 真实HuMMan：原232帧开发数据；A输入与拟合，B仅在checkpoint冻结后评价。复用固定B2048点、历史标定/精确三角面距离和frame→sequence→identity等权聚合。已消费开发集，不称新泛化。
- 新scan身份排除了旧R3全部身份；不把同源Mesh的多相机图当独立人物。
- 原始数据、官方权重、私人预测大包不入Git；代码/合同/报告/索引/代表性图入Git。

## 本轮最小模型与损失

```text
RGB → Frozen Official 完整解码 → 固定Body、t0、冻结RGB特征
Depth + rays + K + 固定Body统计 → 小Camera头 → t_final
输出：原Body + t_final；重新生成相机空间顶点和投影
```

为了复用现有缓存，本轮读取1280维backbone空间池化特征，**不是**R4的1024维最终pose token。因此是明确标识的Camera-only pilot，不能把与旧G1的所有差异归因为单一hook位置。

三项小对照共用同样的固定Body、数据、seed、优化器及Camera GT loss：

1. `raw_bounded`：恢复旧raw Camera残差范围，接入改为最终输出；审计真值是否超范围。
2. `metric_xyz`：最终公制XYZ残差；不使用177mm训练输出上限，该上限只属于历史Txyz。
3. `rgb_only_xyz`：小头不读取几何统计，检查Depth是否提供实际收益；不冒充R3的RGB-only完整模型。

原生监督只用逐图、逐轴Smooth-L1 Camera，beta=0.05m；AdamW lr3e-4、weight decay1e-4、有效batch16、clip1、cosine/2epoch warm-up。沿用历史可对账起点，不称最优。Body固定时局部/去平移误差应不变；不能声称Pose/Shape改善。

扫描弱监督必须另记监督来源。优先检验实际可微几何链；如本机无法完成原渲染器编译，允许预先独立命名的**点到固定表面Anchor的3D弱监督替代实验**，仅训练Camera，不把它称为渲染深度loss或精确三角面loss。权重只能由固定TRAIN批次的输出平移梯度比冻结；不能使用真实B或scan VAL调权重。native-only与mixed必须从同一预训练last状态起步，native批次和更新数完全一致。无法通过梯度QA则不运行混训。

checkpoint选择只用原生合成VAL的Camera L2等权均值；scan/真实结果不回流选模型。scan的衣物表面仅为弱几何监督，不是MHR解剖对应真值。新旧架构和监督变化分别披露。

## 并行与稳定运行

- 218：172.18.6.218:436，8×2080Ti；0/1/2用于三个训练seed并行；3–7用于扫描初始化。按实际显存/吞吐调整并发，不假设显存空闲等于算力空闲。
- 工作目录：`/raid5/xuhd/rgbd_sam3d/r5_camera_overnight_v1`。
- 每个epoch保存best/last、optimizer、scheduler和随机状态。服务器队列由独立进程运行，断开SSH/聊天不停止；禁止关闭服务器。
- 停止新科学任务时间08:15；09:00是本轮收尾目标，不是服务器关机时间。

## Codex低额度等待

- 每阶段交接及定时监控读取真实额度；适用窗口remaining=`100-usedPercent`，低于5%记录对应resetsAt。
- **只暂停Codex的新编排/研究，训练进程和既有队列不随额度停止。**不购买额度、不使用账户手动重置。
- 长跑稳定：preflight PASS、进程/epoch确实前进、best/last正常保存、离开聊天队列仍独立运行。达到后可以减少人工持续操作。
- 本会话已设置30分钟定时续接；额度恢复后检查原进程再继续，避免重复启动。定时续接依赖桌面电脑与Codex保持运行；它不能修改服务端额度，不能保证被额度限制阻止的那次触发仍运行。[官方定时任务说明](https://learn.chatgpt.com/docs/automations?surface=app)
- 00:22读取：5小时窗剩余67%、周窗剩余95%；前者重置时间03:06:51。后续以重新读取为准。

## 明早交付应回答

1. 硬隔离Camera头是否有实际优势，三个seed是否一致？
2. 深度究竟贡献公制位置还是只是mask/身体大小信息？
3. 新scan弱监督是否超过同曝光native-only，还是衣物/Body误差引入偏置？
4. 是否稳定超过Official＋Txyz，或只是减少fallback？
5. 下一步该扩大数据、改几何表示，还是保留工程强基线？不能根据单个均值宣布成功。

依据：[前一轮完整训练设计](../../../research/2026-10-10-rgbd-training-loss-audit/TRAINING_DESIGN.md)、[论文证据](../../../research/2026-10-10-rgbd-training-loss-audit/PAPER_EVIDENCE.md)。本轮代码位于 `research/rgbd_sam3d_mhr/r5_camera_only/`。
