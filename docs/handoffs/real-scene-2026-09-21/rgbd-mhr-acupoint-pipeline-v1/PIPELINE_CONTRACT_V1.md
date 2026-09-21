# RGB-D Mesh 与穴位定位的实际流程合同 V1

日期：2026-09-21  
状态：研究设计合同；尚未开始新模型训练。

## 1. 四个对象必须分开

| 对象 | 它是什么 | 它不是什么 |
|---|---|---|
| SAM 3D Body | 从 RGB 图像、人体提示和模型先验预测 MHR 参数、相机和 Mesh 的上游人体重建器 | 穴位检测器；真实皮肤三维扫描仪；医生标签生成器 |
| 新的 RGB-D Mesh 模型 | 在 SAM3D 的 RGB 表征/MHR 先验上加入 Depth、可见性和身体结构，直接输出更可靠的完整 Mesh | 运行后再用 Txyz/T+Pose 修补的脚本 |
| 解剖标志模块 | 检测脊柱、肩峰、肩胛、骶部等体表/骨性标志 | 直接预测所有穴位真值 |
| 穴位几何模块 | 使用标准公式和 Mesh 表面坐标把已定义的穴位规则转换成三维目标点 | 训练 Mesh 主干的替代标签 |

## 2. SAM3D 在新方法中的准确位置

当前路线有两个层次，不能混成一个方法：

### 工程基线

```text
RGB + 人体 mask/prompt
        ↓
官方 SAM 3D Body
        ↓
MHR 参数、Mesh、相机
        ↓
可选 Txyz / T+Pose
        ↓
工程定位与可视化
```

这条链继续保留，用于部署兜底和论文 baseline。Txyz/T+Pose 是测试时优化，不能被写成新模型。

### 论文模型

```text
RGB ── SAM3D RGB encoder / pretrained initialization ──┐
                                                        │
Depth ── depth encoder ─────────────────────────────────┤
                                                        ↓
mask + prompt ── visibility encoder ── body-part tokens
                                                        ↓
             cross-modal surface evidence fusion
                                                        ↓
             kinematic / body-part graph decoder
                                                        ↓
             MHR parameter head + mesh decoder
                                                        ↓
             full Mesh + visibility/support map
```

这里 SAM3D 的角色是 **RGB 表征和人体 MHR 先验的初始化**，不是最终输出后再修正。Depth 和 visibility 在参数回归之前参与前向计算。部署时一次前向直接给出新 Mesh；Txyz/T+Pose 只作为 baseline、训练教师或故障诊断，不作为主方法步骤。

第一阶段实现策略：冻结 SAM3D 的大部分 RGB encoder，只训练 Depth encoder、visibility encoder、fusion 和 MHR head；如果 held-out 结果证明有收益，再解冻最后一个 body decoder block。这样保留官方能力，又能明确验证新增模块的作用。

## 3. 数据从哪里来

### 3.1 训练数据 A：MHR 合成 RGB-D（有完整真值）

使用官方 MHR runtime/拓扑生成随机人体参数和 Mesh，再渲染 RGB、metric Depth、人体 mask、相机内外参、MHR 参数和可见表面标签。

每个样本同时生成三种观测合同：

```text
FULL        完整人体可见
UPPER       下半身或远端区域被截断/遮挡
LOCAL_TORSO 仅保留躯干及其附近区域
```

遮挡、物体覆盖、Depth 空洞、深度噪声、RGB/Depth 小错位和 mask 扰动只作为训练增强。合成数据提供完整 MHR 真值，适合训练模型理解“缺失区域如何补全”，但不能单独证明真实场景效果。

### 3.2 训练/验证数据 B：BEHAVE 真实 RGB-D

BEHAVE 是主要真实几何来源。使用 K0 的 RGB、原始 Depth、mask 和标定作为输入；K1/K2/K3 的 sensor Depth 只作为 held-out 几何监督。

```text
输入：K0 RGB + K0 Depth + K0 mask + K0 calibration
监督：K0 可见表面 + K1/K2/K3 sensor points
辅助：官方 fitted SMPL/person_fit，只作为支持证据
划分：subject-disjoint；不能把同一人的不同相机拆到 train/test
```

BEHAVE 的 fitted mesh 不能冒充绝对皮肤真值。主指标仍然是 held-out sensor depth 到预测 Mesh 的 point-to-surface 误差。

### 3.3 训练/验证数据 C：其他公开数据

只有在数据协议和许可证核实后，才接入 HuMMan、AGORA 或其他 RGB-D/人体 Mesh 数据。它们的作用是增加姿态、场景和传感器多样性，不替代 BEHAVE 的跨相机几何验证。

SAM3D 官方训练集不是第一阶段的前置条件，也不能直接提供穴位标签。授权资产完整核验后，可以作为预训练或保持通用 RGB 能力的补充；不能把它当作穴位训练数据。

### 3.4 穴位数据 D：单独建立，不能从 Mesh 自动假造

穴位模块使用独立的人体背部图像数据：

1. 第一轮只选 5–8 个标准清楚、体表可见的背部点；
2. 每张图保存 RGB、人体 mask、解剖标志、点位来源和医生复核记录；
3. DMD37 可作为工程候选和预标注来源，但未经过医生核验前不能称为医学真值；
4. 后续再扩展到 37 点，并按质量等级放行。

## 4. 穴位模块每一部分到底做什么

### A. 解剖标志检测

输入 RGB 和 Mesh，输出脊柱线、肩峰、肩胛、骶部等标志。它回答的是：

> 这个人的身体基准在哪里？

它不是穴位预测器。

### B. 个体化比例计算

根据已核实标准，将标志之间的距离换算成该人的局部“寸”比例。它回答的是：

> 这个人的身体比例是多少？

比例必须来自正式标准和医生复核，不能从截图或单个样本手工猜。

### C. 骨度分寸法

对有明确标准公式的点，使用骨性/解剖标志和个体比例计算候选点。它是确定性几何规则，不需要神经网络训练。

### D. 体表标志法

从图像或人工 prompt 找到体表可见特征，再计算同一个穴位的候选点。它回答的是：

> 从皮肤表面直接观察时，该点在哪里？

### E. Mesh 表面映射

把候选点投到预测 Mesh，保存三角面索引、重心坐标、世界坐标和相机重投影位置。它回答的是：

> 机器人应该在三维人体表面的哪个坐标工作？

### F. 双路径核验

骨度法和体表法只在两者均可用时互相比较。差值用于发现规则冲突、Mesh 误差或标志误差，不能直接平均成真值。

## 5. 真正部署时的一条完整流程

```text
1. RGB-D 相机采集图像、Depth、内参
2. 人体检测/分割得到 person mask 和 prompt
3. 新 RGB-D Mesh 模型一次前向输出 MHR、Mesh、visibility map
4. 用有效 Depth 做表面几何检查和拒答判断
5. 检测解剖标志，建立背部局部坐标系
6. 用标准公式计算目标穴位候选
7. 用体表路径计算第二组候选
8. 两组候选映射到 Mesh 表面并保存 provenance
9. 做重投影、跨视角和双路径差值检查
10. 通过阈值后转换到机器人坐标；否则只显示结果并拒绝执行
```

模型训练和穴位计算在这里是前后关系：先让 Mesh 可靠，再把穴位规则放到可靠表面上。穴位公式不能反过来替代 Mesh 监督。

## 6. 第一篇论文的实验顺序

1. SAM3D Official；
2. SAM3D + frozen Txyz/T+Pose；
3. RGB-only trainable adapter；
4. RGB-D adapter；
5. RGB-D + visibility；
6. RGB-D + visibility + body-part graph；
7. 完整模型加跨视角表面约束。

所有方法使用相同的 K0 输入、相同的 held-out K1/K2/K3 点、相同的 frame/sequence/subject 聚合。穴位结果单独作为下游实验，不把它混入 Mesh 主指标。

## 7. 研究停止条件

如果完整模型只改善 K0，不改善 held-out K1/K2/K3；或者只改善局部可见区域、却让完整场景退化；或者穴位双路径差异主要来自 Mesh 坐标错误，那么不能继续堆模块，应先修数据合同和标注。
