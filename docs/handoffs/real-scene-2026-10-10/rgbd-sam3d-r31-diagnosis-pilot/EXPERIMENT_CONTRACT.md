# R3.1 执行合同与证据边界

## 诊断与小规模验证，分别回答问题

1. 历史 R3 三 seed 诊断：已有 400 TRAIN 合成身份×30 epochs 的 Cross-Attention，固定 RGB/Valid Mask/rays，分析 Depth 信息来源。
2. 强基线：同一批 HuMMan 232 TRAIN/VAL timestamps，Official、历史 RGB-only/Cross 三 seed 各自增加历史 Cheap Txyz。
3. 公平候选 pilot：四种模型重新从 Official 零 residual/head 初始化，100 TRAIN 身份/800 张、50 VAL 身份/400 张、seed 11、8 epochs、batch 16、LR 3e−4。真实数据仅评价，没有真实训练。

这三条证据不可混成同训练预算排名。合成 TEST 50 身份/400 张、真实 TEST 6 身份/120 timestamps 均封存。

## 相机与评价

输入只有 `kinect_000`（Camera A）。`kinect_001`（Camera B）2048 点/帧在 R3 模型比较前固定，R3.1 全部沿用同一索引与文件。Camera B 不进入 attention、几何对应、Txyz、loss、LR 选择或 checkpoint 选择。

真实主指标为 Camera B 测量点到预测 Mesh **精确三角面**的单向距离。每帧 median/P95/≤50 mm coverage，先在 sequence 内取 frame 均值，再 subject 内 sequence 等权，最后 subject 等权；TRAIN/VAL 分开。表中“median”实际是逐帧 median 经此聚合的均值，不能称全部点的 pooled median。

真实 supporting rendered-depth 提供共同命中误差和命中率；公开 distortion 信息缺失，不能把它当独立绝对毫米精度结论。主三维距离不需要像素渲染，但仍依赖公开 K/R/T 和传感器配准。点云是衣物/可见表面，不是穴位、骨骼或精确人体 Mesh GT。

合成指标使用对应 MHR 顶点真值：camera/body/去平移顶点、关节、Camera、shape/scale、root rotation、pose、rendered depth/hit/silhouette。合成对应顶点误差不能与真实单向 surface distance 或文献 PVE 混用。

## Cheap Txyz

16384 surface anchors，以历史 seed 20260910 再生，face-index/barycentric 数组 SHA 与历史合同一致。每帧 Camera A 5000 点（不足则全部）在任何分支计算前固定，同帧各模型相同。6 次迭代；抛弃上侧20%对应距离；每轴单步±0.05 m；最终总平移范数超过 **0.17788820176363325 m** 则应用零平移。记录 raw/applied/fallback 和完整 trace。

它只修正整体平移，不改变 pose/shape/scale、mesh topology 或 Camera B 点。真实 Txyz 的结果是工程强基线，不是新网络贡献。

## Depth 干预

历史 R3 seed11：15 条条件，合成400 +真实232；seed23/37：correct、mask/rays-only、absolute-only、relative-only、+0.2 m 五条确认条件。全部保持原 Mask/rays，不把换 Mask 的结果解释成公制 Depth 的收益。

absolute/relative 通道归零是通道依赖诊断，可能是分布外输入。保持 RGB/rays 时整体 Z 改变也产生不一致输入；预期不是严格输出同幅度平移。local shuffle 在每个16×16 patch 的有效像素内打乱，不改变有效性，也基本保留 patch 平均。

历史诊断的 wrong-depth donor 仅约束不同身份，可能同时换 pose/view，因此不叫“孤立身份效应”。候选合成消融改为**相同 pose、相同 physical camera、下一个 VAL 身份**，填补 donor 无效位置后施加原 Valid Mask/rays；两份结果分别保留。

候选消融将变换后的 Z 同时输入 Depth CNN 与显式 XYZ 路径；不能只改 CNN 通道而让 geometry 模块偷偷读取正确 Z。缺失 Depth 是另一个条件（Valid 全零），与 fixed-mask numerical ablation 区分。

## 保存、执行与比较

best/last checkpoint、每 epoch 曲线、合成400张 best/last 的完整原生输出、真实232帧顶点/Camera/Pose/Shape/Scale、固定点索引、训练/推理代码 hash 均保存。Official 参数前后 hash 不变。

训练来源 commit 为 `16e161489fafbc041765c5ec0d80ced944fca8f1`。机制消融代码在独立 `r31_inference_code` 快照中；新增旗标仅在推理干预中开启，训练代码没有覆盖。CPU线程数调整用于避免实测并发争用，不改 split/seed/loss/batch/模型，旧部分消融记录保留。

预先固定的失败样本是 p001196 全部8 timestamps，以及历史 seed11 Cross−Official P95 恶化最大的6帧，共14张。它们用于解释失败，不是评价总体的抽样；最终报告保留全232帧结果。camera-only 与 Kabsch counterfactual 只交换预测参数或对齐预测 Mesh，绝不拟合 Camera B 点；不是解剖因果归因。

本轮未做：新大规模训练、正式候选多 seed、解冻 decoder、自由顶点偏移、真实 TEST 调参、临床穴位准确性验证。
