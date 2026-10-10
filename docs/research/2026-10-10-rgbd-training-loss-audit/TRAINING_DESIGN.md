# R5 从数据到损失、训练和评价的完整设计

## 1. 先给判断

当前最值得检验的是：**SAM3D 保持它原来预测的人体，用 RGB-D 学习把这个人体放到正确的相机坐标位置。**第一轮只训练 Camera 平移，不同时训练 Pose、Shape、Scale、global rotation 或自由顶点位移。

这个选择来自 R4.1/R4.2 的实际诊断，以及 MoGe-2、UniDepth 对公制量/相对几何和梯度路径的分析；不是已经证明 Camera-only 一定优于 Official＋Txyz。BLADE 还提醒我们，近距离人体本身可能预测错，纯平移存在能力上限。

上一条给出的四项损失及 `0.5/0.1` 系数没有实验依据，撤回。**论文可以支持监督原则，不能替我们选出损失权重。**本文区分历史实现、推荐设计和仍需实际测量的配置；不宣称新方案已经实现或训练。

## 2. 以前到底用了什么

### 2.1 原生 RGB-D 训练

|阶段|实际目标|用途|
|---|---|---|
|R1|7 个输出字段的等权 MSE：vertices、3D keypoints、Camera、global rotation、body pose、shape、scale|单 fixture、3 次 optimizer step，证明梯度链，不是充分训练|
|R2|下面的十项加权损失|32 合成身份，24 TRAIN / 4 VAL / 4 TEST；pilot 8 epochs、seed42、batch1、lr1e-3|
|R3|同十项损失|500 身份、4,000 图；400 TRAIN / 50 VAL / 50 TEST；30 epochs、batch16、seeds11/23/37|
|R3.1|实际训练调用 R3 trainer，仍是十项损失|`qa-only` 中的输出平方只是梯度 QA，不能算训练目标|
|R4|直接读取 R3 配置并调用同一 `loss_components`|正式训练 lr3e-4；新 fusion / Camera 分支，未另换一套科学损失|
|R4.2|39 系数 ridge 回归，拟合 Camera A 的 Txyz 伪目标|确定性 CPU 机制 pilot；不是原生 GT Camera 训练，λ=100 来自 TRAIN 内留一身份验证|

R2–R4 的十项如下，数值由实际配置核对，不是从论文猜测：

|项|代码中的定义|历史权重|
|---|---|---:|
|局部顶点|Smooth-L1，beta=0.02 m|5|
|局部关节|Smooth-L1，beta=0.02 m|5|
|Camera 平移|Smooth-L1，beta=0.05 m|2|
|Body pose|所有 133 分量的 `mean(1−cos(差值))`|0.1|
|Global rotation|Euler 转旋转矩阵后的 MSE|0.2|
|Shape|参数 MSE|0.01|
|Scale|参数 MSE|0.01|
|Hand|参数 MSE|0.0001|
|渲染深度|GT 人体 mask 内，预测 Z 与目标 Z 的 Smooth-L1，beta=0.02 m|0.2|
|轮廓|整个 batch 的 soft IoU loss|0.2|

数据/预处理主路径：

- `native_data_r3.py` 生成原生 MHR 与公制 Camera 标签；身体固定后改变物理相机，并显式处理骨架 root pivot。
- `prepare_r3_cache.py` 使用 noisy Depth 输入、clean Depth 目标，缓存原生 Official 输出及 backbone；它不是“拿同一带噪深度直接当干净真值”。
- `render_losses.py` 计算十项；`train_r3_multiseed.py`、`train_r31_pilot.py`、`train_r4.py` 负责训练。
- `r3_common.py` 的评价另外报告局部/相机空间顶点、去平移顶点、Camera、关节、Shape、Scale、渲染 Depth 和命中率。

这些是我们自己设计的实验损失，不是 SAM3D 官方训练配方。原论文使用关键点、MHR 参数和手检测等监督，数值权重没有全部公开。当前没有查到上述十项权重的完整逐项消融，因此不能说这些权重已经最优。[SAM3D 作者论文 §4](https://arxiv.org/html/2602.15989v1#S4)

### 2.2 推理时的优化要另列

- **Cheap Txyz**：固定表面 Anchor 与 Camera A 观测点做最近邻对应、丢弃最远 20%、中位平移更新，6 轮；每轴每轮 50 mm，总范数上限 177.88820176363325 mm，超限按历史规则 fallback。它不是网络训练 loss。
- **T+Pose / O2**：每个样本重新优化 translation、global rotation、body pose；使用 trimmed 表面残差的 Smooth-L1（beta=0.02 m）及 translation/pose 初始化先验，历史权重各 0.01，lrT=0.003 / lrPose=0.001、1,024 点、anchor stride2。
- **Rigid+D**：历史 PressurePose 表面形变诊断，不是本轮 RGB-D Camera 网络训练，也不与上述网络 loss 混为一项方法。

## 3. 旧实现里需要公开说明的细节

1. **冻结权重不等于冻结人体输出。**G1 的前置 Depth fusion 改变 Decoder 输入；Camera hook 还在中间迭代生效。新的硬解耦必须在原始 RGB 解码完成后修正最终 Camera，不能只给旧 Depth fusion 加 `detach()`。
2. **轮廓按 batch 求一个 IoU。**近距离 mask 更大，天然占更高权重。下一实现应先每图求 loss，再按样本/身份规则汇总；历史数字不回写。
3. **Depth 漏命中并非被旧代码忽略。**旧 loss 在整个 GT mask 上计算，未命中为渲染 Z=0，因此有惩罚；但该像素没有有效面片时，不一定有把 Mesh 拉回的深度梯度。nvdiffrast 的边界梯度来自 antialias。不能把“loss 大”或“参数梯度不为零”当作定位成功。[渲染器官方说明](https://nvlabs.github.io/nvdiffrast/)
4. **不能只因 Euler 名称不同就判定旋转 loss 有错。**训练矩阵 MSE用 `ZYX`，原生生成/评价用物理约定 `xyz`。两者同一角度的物理旋转不同，但在预测/标签均采用同一约定、各矩阵元素等权的 Frobenius MSE中，这个特定两种转换具有等距关系，标量 loss可相同。本轮独立SciPy数值核查支持这一点；不是已确认的历史训练误差来源。物理投影仍须用真实原生约定，Camera-only不训练该字段。[核查记录](CONVENTION_AND_REDUCTION_CHECK.json)
5. **Body pose 并非全为角度。**评价器明确把 124–129 排除于角度统计，训练却对全部 133 分量使用 cosine。其线性分量需按类型处理；新 Camera-only 不沿用该项，也不因此宣布既有真实几何结果无效。
6. **单位与权重相互关联。**Smooth-L1 在米上算，参数 MSE 和 IoU 无量纲。20/50 mm 的 beta 是二次区到线性区的转折，不是临床容忍误差，也不是“除以 20/50 mm”的归一化。改成毫米却保持旧权重会改变训练。

本轮仅审计和设计，未修改这些历史训练源码。

旋转核查的具体范围：RoMa源码定义大小写分别为 intrinsic / extrinsic，与SciPy约定对应。取 `P` 为交换x/z轴的正交矩阵，有 `R_ZYX(a)=P·R_xyz(a)ᵀ·P`，所以预测/标签矩阵的等权Frobenius差不变。100组独立角度的标量差最大为1.11e-16，有限差分梯度差最大为1.67e-10；这是CPU数学例，未运行历史Torch模型。物理矩阵不能直接互换，只有这个特定标量目标具有等距关系。[RoMa原始实现](https://raw.githubusercontent.com/naver/roma/master/roma/euler.py)

## 4. 现在的数据到底可以监督什么

|数据|已具备|没有/不能冒充|本轮用途|
|---|---|---|---|
|旧 native MHR：500 身份 ×2 固定姿态 ×4 相机＝4,000 图|MHR 局部顶点/关节、参数、`pred_cam_t`、K/R/t、clean/noisy Z|摄影衣物、真实床面接触、临床穴位标签|直接监督原生 Camera；保留 Body 误差作为诊断|
|R5 scan V2：12 身份、48 固定扫描 Mesh ×64 相机＝3,072 图|摄影纹理、扫描表面、准确虚拟 K/R/t、person mask、clean/noisy Z、法线、可见扫描 face id|MHR root/参数/对应顶点；临床骨性标志|表面/投影弱监督、距离/视角受控诊断|
|真实 HuMMan：232 开发帧|Camera A 输入和观测；独立 Camera B 固定评价点|原生 MHR 对应顶点、人体内部解剖 GT、穴位 GT|模型冻结后的迁移核查；B 不用于训练或选超参数|
|历史 PressurePose 俯卧缓存|实际床上图像和观测、历史工程结果|完整独立毫米级相机验证、裸背/穴位 GT|目标域外部工程复核，单独标注坐标合同限制|

SCAN split 仍为 9 TRAIN / 2,304 图、3 VAL / 768 图；464 截断样本保留。64 视角不是64个新身体。同一源 Mesh 的所有视角必须与其身份同角色。

**关键：**`reference_point_camera_m` 是扫描参考中心；`T_world_to_camera` 是虚拟世界原点的外参。两者都不是 MHR root 的 `pred_cam_t`。不得把扫描中心当 pelvis/root，不得为扫描补零 Pose/Shape，不得用最近点建立伪“对应顶点 GT”。[本轮数据交付](../../handoffs/real-scene-2026-10-10/humman-controlled-camera-r5-v2/FINAL_REPORT.md)

扫描表面含衣物，MHR 表示参数身体。二者几何损失是**弱监督**，会混入衣物偏差和 Official Body 错误，不是真实 root 标签。[DoubleFusion 的内外层表面设计](https://arxiv.org/abs/1804.06023)

## 5. 首先确定要学的输出和梯度路径

```text
RGB + 数据集 bbox/mask + 原始 K
    → Frozen Official，按原始 RGB 路径完成全部解码
    → 固定 V0、Pose、Shape、Scale、Hand、global rotation、t0
                                      ↓ 只读/stop-gradient
Depth + Valid + 原始射线 → 公制几何 → Camera 分支 → t_final
                                      ↓
                        V_camera = V0 + t_final
                                      ↓
                     官方 Camera/2D 投影同步更新
```

- 保持的是**全部 Body 输出**，不只 model weights；global rotation 也固定。因此第一阶段只能修位置，不能修错姿态或错朝向。
- 第一候选把已有 MetricCamera 的接入移动到最终输出，保留其结构作受控比较；同时去掉人体前面的 Depth fusion。读取最终 RGB token 时只采集，不改 Decoder。
- 先检查旧 raw-camera bounded residual 能否表示 native GT。若所需修正超出其输出范围，单独比较“最终公制 XYZ 输出头”，不要加训50轮来掩盖容量范围不足。改变参数化须明确记录。
- 公制 XYZ 版本可用观测质心/中位位置 `c_obs` 加可学习 surface-to-root 偏置：`t_coarse=c_obs+bφ(相对XYZ、绝对公制统计、RGB token、固定Body特征、K/bbox)`。这是建议参数化，尚未证明能把起点拉到30mm以内。
- R4.2 的 39 系数统计头已经失败；新非线性头不能因“有 XYZ 输入”就预先称有效。先复用现有小头，再由固定对照决定是否需要更细的几何编码器。
- 不按每图人体尺寸把 XYZ/Z 归一成无尺度数据。允许减质心，但质心和原公制尺度必须另外输入。
- Depth 缺失时走原 Official 输出，记录为缺失输入；不编造默认深度。一个完全旁路的缺失样本不会训练 Camera 头，应当用于行为验证。

**暂不必同时实现粗＋细两头。**先证明粗定位有价值；细头若加入，读取粗位置下的渲染残差并输出 Δt，最终 t=t_coarse+Δt，仍不回馈 Body。训练渲染与推理渲染的完整耗时必须统计，不能预称毫秒级。

## 6. 损失按标签选择，不按名字堆叠

以下都是候选设计，尚无新训练实测。坐标/残差使用米，每图独立平均。定义 Smooth-L1：

\[
\rho_\beta(e)=\begin{cases}e^2/(2\beta),&|e|<\beta\\ |e|-\beta/2,&\text{otherwise}.\end{cases}
\]

### 6.1 必需的主损失：原生 Camera GT

\[
L_{cam}(t)=\tfrac13\sum_{a\in\{x,y,z\}}\rho_{0.05}(t_a-t^*_a).
\]

`t*` 直接读取原生数据的 `pred_cam_t`，不是扫描中心。先沿用历史 beta=0.05 m 作为可对账起点，不声称是最优噪声模型。报告 Tx/Ty/Tz 和三维范数，主评价保留绝对毫米误差。

只用这一项先训练/验证 final-only 分支，回答“是否真的学会位置”。不先对预测与标签做平移、尺度或 Procrustes 对齐后再算主损失，因为那会删掉本轮要学的误差。BLADE 的逆距离加权可以另作近远距 trade-off 消融，不默认采用。[BLADE 的公制距离与监督](https://arxiv.org/abs/2412.08640)

Body 硬冻结时，局部 vertices/joints、Pose、Shape、Scale、Hand loss 对该头没有训练作用；保留它们的评价即可。Camera-space 对应顶点 loss 虽有 Camera 梯度，但会把 Body 误差也推给平移，不能与纯 root loss不加区别地相加。

### 6.2 摄影扫描候选：可见 Z + 轮廓

设 `D*(u)` 为 clean axial-Z，`M*` 为干净人体 mask，`(D_t,S_t)=Render(V0+t,K)`。推荐先检验：

\[
L_Z=\frac{1}{|M^*|}\sum_{u\in M^*}\rho_{0.02}(D_t(u)-D^*(u)),
\qquad
L_{sil}=1-\frac{\sum_u S_t(u)M^*(u)}{\sum_u[S_t(u)+M^*(u)-S_t(u)M^*(u)]}.
\]

- 未命中渲染 Z 保持0，并在全 GT 前景集合中算，不只用好匹配像素重新归一。额外报告命中率/完全未命中数量；仅从低 Depth loss 不判成功。
- 已知合成 clean 标签可监督 noisy 输入中的空洞位置；不能反过来把空洞0当表面 Z。真实数据没有 clean GT时，不能照此补造标签。
- mask loss 要**每图算再平均**；否则近距大 mask 主导梯度。截断场景只评价图内可见轮廓，不能罚图外不存在的 GT mask。
- 轮廓约束补充图像平面位置，但衣物和 Body 不匹配时也可能推歪 Camera。记录 depth/IoU/root 指标间的冲突，不认为 IoU 高就3D准。
- 粗位置完全不重叠时，仅有这两个 raster loss 不保证可靠收敛。先通过 Camera GT 粗定位检查再尝试扫描混训；无命中失败仍需交付，不悄悄删除。

这是我们根据可见几何与实现特性提出的实验，不是某篇论文已替我们证明的配方。保留旧 beta=0.02 m 便于对账；扫描衣物厚度不等同于此 beta，也未在这里估计医学误差。

### 6.3 3D 表面项作为替代/消融，暂不与 Z 无条件重复相加

可见观测点到预测**可见三角面**的鲁棒距离、或有效对应下的点到平面残差，可以作为 `L_Z` 的替代。对应、遮挡、法线方向必须固定实现合同；不能让背部观测随便匹配到腿/背面。DoubleFusion 提供鲁棒几何项的依据，但不是我们的系数依据。

首轮使用 `Lcam` → `Lcam + scan(LZ + w_sil Lsil)` 的递进；下一独立消融以表面项替换 LZ，检验是否更稳。点到表面和 Z 大量复用同一几何证据，因此不默认同时加上来“增强监督”。精确 CPU 点到三角面评价器不是自动可微的训练模块。

3D loss 在近似平坦后背可能主要约束法向，无法凭空确定切向对应。`Σnnᵀ` 条件数大不代表三轴均无信息；不应整段把 fine Δt 清零，也不因此新增不确定性头。观测退化是需检验的几何属性，先报告分轴结果和轮廓证据。

### 6.4 暂不加入的项

无对应 MHR 标签的扫描不使用 vertices/joints/Pose/Shape/Scale GT loss；无同一 UV/材质的 MHR 不使用 RGB 光度重建 loss。首轮不增加 learned confidence、不确定性、自由顶点偏移、解冻完整 Decoder或复杂新 Attention。

多视角先作为丰富输入和分组评价；不直接对不同视角的 Camera 坐标 t 求相等。若以后做 world consistency，必须使用真实 R/t 转到共同世界坐标，且要承认不同 RGB 视角的固定 Body 也可能不同，不能拿一致性结果代替 MHR 解剖 GT。

## 7. 权重怎样确定，才不是凭空给数

历史十项权重只用于原 baseline 对账。新的 Camera-only 不能照搬它们，上一条四项总和不再作为预注册。

推荐方法是：

1. `Lcam` 单项先跑通，不需要多任务权重，保存逐轴梯度与误差。
2. 固定一小批 TRAIN 样本与 Camera 头状态，分别测候选 `LZ/Lsil` 对**米制输出 t**的梯度范数和各轴响应。
3. 为混合项采用一次性的固定梯度量级校准，例如 `w_sil=median‖∂LZ/∂t‖ / median‖∂Lsil/∂t‖`；域间也可用 `Lcam` 与 scan 几何的 TRAIN 梯度比作初值。完整记录校准样本、状态、原始梯度、结果权重。
4. 若有效梯度为0，先查对应/可见性，不用放大权重掩盖。校准只平衡数值量级，不证明各项可靠、方向正确或权重最优。
5. 首轮固定校准后的权重，比较扫描弱监督开/关，以及轮廓开/关。若确有必要搜索，事先列小候选集，只用合成 VAL 挑选；不看 Camera B 后改权重。

所有量均在新科学结果前冻结。这里**没有已经测到的 w_sil 或域权重**，因此不能写成已有最优系数。这是工程校准方案，不是声称复现了上述论文的权重学习方法。

将来若加入 fine head，native GT 同时约束 coarse 和 final，并报告 fine 额外收益，防止 coarse 任意漂移而 final 全部救回；扫描没有 coarse root GT时不伪造该项。

## 8. 输入、相机和缓存合同

- 原始 RGB、原始 K、固定 dataset-mask-derived bbox/prompt；首轮不混入 detector 错误。
- noisy Depth 是输入；clean Depth/扫描表面是标签。scan 的 clean scene floor 与 person depth 分开，背景床/地面不混成人体监督。
- 已有 `crop_registered_depth` 通过 Official 实际 crop affine 反映射到原图像素，nearest 采样公制 Z和对应射线；沿用这条逻辑，不再次猜 bbox resize / K。
- HuMMan 原始 Depth 不在 RGB 坐标内，须先经过既有已核查标定注册与前表面 z-buffer；注册空洞保留。
- 相机输入用 axial Z，非射线径向长度。Blender depth pass 的转换已有 R5 QA，不能再转换一次。
- native MHR 模型原始单位与最终 `pred_vertices` 的米制输出区分；训练、投影、Surface 全部以最终米制 Camera 坐标运算。
- 当前权重是实际使用的 vith 配置。论文含其他 backbone variant 不意味着本实验已经改用了它。
- native cache 已有 frozen Official 输出，可复用；scan 需建立自己的标签分支，旧 `prepare_r3_cache.py` 的 native `TRUTH_KEYS` 路径不能直接处理无参数 GT的扫描。
- 保存每个预测的 Body、t、K、原始/更新 Camera、最终 vertices、source/sample SHA、输入/目标 Depth 区分。图片从缓存画，不为好看重新拟合。

## 9. 怎样用 4,000 + 3,072 图，而不被重复视角支配

1. native 用原来的身份角色，TRAIN 3,200 / VAL400，TEST400封存；scan 用9TRAIN/3VAL，现有全部64视角保留。不创建混合域的假新身份。
2. native 按身份→固定姿态→相机采样；scan 按身份→源扫描→相机组→组内配置采样。七相机组均衡，避免24张 multiview 组天然压过4张 focal 组。
3. native-only 与 mixed 比较时，固定每步 native 样本/曝光与 optimizer 更新数；mixed 额外加入扫描梯度，单独报告额外计算和图像数。不能同时声称新增数据、native曝光一致且完全等算力。
4. 先以 native-only 和 mixed 成对小验证决定是否保留扫描监督。上一条“8 native+8 scan”的数值是候选 batch 构成，不是已实验选择；实际 microbatch由显存 benchmark决定。
5. 464 截断图保留并分层报告；不依据模型分数筛掉。身份外推仅有3个扫描VAL身份，置信范围有限。
6. 先统计 native GT实际 Camera 距离/角度覆盖。旧 native 按身体/焦距自动选距离，不保证覆盖新scan的0.8–4m全合同。若有缺口，补**原生 MHR同相机合同**的小桥接组，沿用已有身份角色与root/pivot处理；不把新scan中心补成root标签。

混训是一个“监督来源变化”的实验，需要保留 native-only 的强对照。[BEDLAM 对衣物/标签与损失的消融](https://arxiv.org/abs/2306.16940)支持分别验证数据和监督设计，但不能替我们保证12身份足够。

## 10. 一次改变一个问题的实验顺序

### Step A：基线和表示检查

在已有 native 与新 scan 的固定 TRAIN/VAL上检查 Official、Official＋历史 Txyz；按距离、仰角、roll、焦距、偏心、截断报告。核验数据合同、Camera 单位、实际 projection。查看 native GT是否处于旧 MetricCamera可输出范围。

四件事分别标清：代码/接口通过、训练跑通、实验完成、科学优势成立。现阶段前两项的新方案也未在本轮验证。

### Step B：仅 Camera GT的小验证

final-only分支，原生 Camera loss；保存相同 seeds11/23/37、初始化与更新预算。继承已有 AdamW / lr3e-4 / weight decay1e-4 / clip1作为对账起点，不因论文用了48张A100而照搬其batch。

先固定短跑预算和更新数，保存 best/last及曲线；是否扩到30epochs根据合成VAL收敛判断。microbatch和有效batch先测；单头不能利用 Body loss 假装输出变好。若 raw-camera参数化范围不足，单独公制输出参数化消融。

### Step C：同结构加扫描弱监督

在 Step B 结构、seeds及native曝光不变的条件下加入扫描几何，做几何开/关与轮廓开/关。保留新旧监督定义和固定权重回执。没有稳定增益就不继续扩大这项损失。

历史 G1 checkpoint仍是工程参考，但其十项监督与新Camera-only不同，**不能直接称为等预算架构对照**。若要比较早期耦合与final-only架构，必须额外重训匹配目标、输入、数据/预算的 G1-MATCHED版本；原G1保留，不覆盖。不能把旧G1历史结果与新数据＋新损失同时变化后的结果归因成单独架构贡献。

### Step D：仅有明确剩余位置问题才加 fine

coarse-only与coarse+fine用同数据/预算对比，逐轴检查收益、命中率、负面样本和实际耗时。单次神经前向不天然比Txyz准确；是否摆脱Txyz须由独立评价和成本证明。

不先把整套几何 attention、条件数门控及多个损失一并加进去。MoGe-2和UniDepth给出解耦的依据，不能替我们证明此处每个模块都必要。[MoGe-2](https://arxiv.org/abs/2507.02546)、[UniDepth](https://arxiv.org/abs/2403.18913)

## 11. 必须怎样评价

### 原生合成

Camera XYZ/L2、camera-space顶点/关节、局部和去平移顶点/关节、Pose/Shape/Scale变化、深度残差＋命中率、silhouette IoU。按 camera条件→固定姿态→身份汇总，分别报告near/far、roll/俯仰、截断和全部失败。

Body固定时，局部/去平移顶点误差应保持原Official水平；Camera改善不能被写成Pose/Shape恢复更好。检查固定Body字段精确保持，geometry只容许既有浮点舍入。

### 扫描重渲染

只报告可见表面/投影与虚拟相机条件下的结果，不能报告不存在的 MHR Camera root或Pose/Shape GT。按图→固定扫描Mesh→身份等权，另分七camera组；共同命中点与全GT命中率一起给。

可额外在同一固定源Mesh的另一渲染视角检查表面，但它来自同一合成资产，不叫独立真实传感器真值。

### 真实 HuMMan

复用232开发帧、固定Camera B每帧2,048点、精确point-to-triangle、原 frame→sequence→identity 等权合同；A输入/定位，B只评价。报告逐seed、逐身份、P95/coverage和所有fallback；不根据B结果筛样或改loss/超参数。

强基线 Official＋Txyz的既有VAL median/P95为11.23/41.60mm。G1＋Txyz三个seed为19.26/97.27、12.47/47.70、14.98/60.95mm；硬Body机械组合降低尾部但未稳定超过强基线。新Camera方案必须真正证明价值，不只超过较弱Official起点。[R4.2原始交付报告](../../handoffs/real-scene-2026-10-10/rgbd-sam3d-r42-camera-body-decoupling/FINAL_REPORT.md)

与/不与同一Txyz的两组结果、Txyz raw/applied delta和fallback均保留；每个seed，不只总平均。Official固定checkpoint不因复制三seed标签变成三个独立训练模型。当前232帧已经历史分析过，不能称全新泛化集。

### Depth 的真实价值

固定RGB、mask、valid、rays，比较正确公制Z、相对Z-only、绝对统计-only、局部形状扰动、错身份Depth、同身份错姿态、缺失Depth、数值偏移；记录t和完整Body变化。错配或偏移必须与物理重渲染的真正distance变化分开标注。

正确Depth须改善实际公制误差或独立表面评价。梯度非零、输出对±200mm发生变化、或输入mask很好，都不能单独证明几何价值。

合成VAL可用于预先定义的选模，真实B不能用来反复试到好分。先冻结模型与选择记录再一次正式评价真实开发集；封存TEST继续不读。

## 12. 资源、交付与工程衔接

优先使用218既有8×2080Ti。已验证的是Blender CUDA生成；Torch/官方权重/nvdiffrast训练环境仍要实际核验，不能从“渲染成功”推定训练已就绪。先做一份缓存样本和一个Camera backward，再测batch、吞吐、峰值显存，之后决定并发seed或DDP。有效batch跨方案一致，不靠改变batch抢速度来破坏对照。

CPU可做数据索引、缓存指标、代码审计、报告；新Official前向和可微渲染通常需要GPU。服务器不自动关闭；原始数据/权重不入Git，checkpoint备份到既有持久化路径并核对SHA。

交付必须包含：数据/身份角色、标签可用性、相机/单位、完整代码与loss公式、实际权重校准/选模回执、每seed曲线和checkpoint、逐图/逐身份指标、Body保持检查、全部失败图、训练/推理耗时、缓存mesh、Git和备份回执。

这轮若成功，输出仍是原生MHR，同拓扑工程点能继续传播；Camera修正使点的绝对xyz一起移动，**不自动修正穴位的解剖对应误差**。俯卧接触变形、裸背皮肤精度和临床定位需要后续独立证据。

下一步的明确顺序：**建立scan标签/Official缓存并完成基线 → 原生Camera GT的final-only短跑 → 扫描弱监督开/关 → 独立B评价 → 决定fine/扩大训练。**当前不直接启动旧十项loss的扫描混训，也不提前认定论文贡献成立。
