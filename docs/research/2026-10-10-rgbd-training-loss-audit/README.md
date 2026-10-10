# R5 训练与损失：论文依据、历史对账、下一轮设计

日期：2026-10-10。状态：**文献与代码审计完成；新训练方案尚未实现、尚未训练。**

本目录回答：旧实验用了什么损失，当前两种合成数据分别能监督什么，如何保持 SAM3D 人体输出并训练公制定位，以及怎样验证改善确实来自 Depth。

- [完整设计与判断](TRAINING_DESIGN.md)
- [论文方法、图和实验的阅读笔记](PAPER_EVIDENCE.md)
- [历史配置与源码 SHA 对账](LOSS_HISTORY_AUDIT.json)
- [PDF 身份、结构检查和实际阅读范围](PAPER_READ_RECEIPT.json)
- [Euler loss 与 batch IoU 的独立数值例](CONVENTION_AND_REDUCTION_CHECK.json)

本轮重新核验 R5 manifest：3,072 图、12 身份、48 源 Mesh、464 截断图；9 TRAIN / 3 VAL。新扫描数据没有原生 MHR root、Pose、Shape、Scale 或对应顶点 GT。旧原生 MHR 的 500 身份 / 4,000 图继续保留。

核心判断：**先做 final-only Camera 分支的原生 Camera GT 监督，再独立检验扫描表面弱监督；不要直接把旧十项损失套到扫描上。**摄影扫描和多相机丰富了外观与成像条件，没有自动增加人体身份、姿态或医学标签。

上一条讨论里的 `Lcam + 0.5 Lsurface + 0.5 Ldepth + 0.1 Lmask` 等系数及 50/20 mm 归一化方案撤回为未验证草案，不作为执行合同。已有 Smooth-L1 的 beta 则是历史实验参数，含义与归一化常数不同。

实际完成：读取训练主路径和标签生成/缓存代码；检索并定向阅读七篇原论文及选定架构图；八份PDF通过结构检查；重新核验R5索引数量；运行CPU数学示例。没有运行新的SAM推理、backward、模型训练或真实开发集评价。
