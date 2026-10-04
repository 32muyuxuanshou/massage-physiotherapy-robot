# 从论文走到当前方法

读过两篇的摘要、方法主要页和主架构图，已本地下载PDF；不是全文附录审计。

| 工作 | 学到什么 | 当前动作 | 暂不照搬 |
|---|---|---|---|
| [RINO, CVPR2026](https://arxiv.org/abs/2603.27773) | 刚体方向变化与非刚性对应应分开处理；点映射要有结构约束 | 使用真实注册对应评价身份，而非仅看点→面；后续成对模板输入避免固定坐标空间 | 作者Code soon，当前模型无其向量神经元/复杂功能映射，不叫复现 |
| [DV-Matcher, CVPR2025](https://openaccess.thecvf.com/content/CVPR2025/html/Chen_DV-Matcher_Deformation-based_Non-rigid_Point_Cloud_Matching_Guided_by_Pre-trained_Visual_CVPR_2025_paper.html) | 模板/目标双分支、局部和全局特征；对应与形变耦合；partial loss不能惩罚缺失表面 | 先隔离对应并比较全局、局部、query输出，再走成对可换模板输入 | 没做DINO/FeatUp投影、形变图或其损失；当前收益不能归于该完整系统 |
| [DiffusionNet, ACM TOG](https://github.com/nmwsharp/diffusion-net) | 可靠可用的谱结构强参考；跨离散/姿态比NN难得多 | 作者HKS checkpoint和原fmap代码实际运行，单列更强的full-context合同 | 作者训练80/完整输入与当前60/partial不同，不做架构胜负排名 |

当前实验只证明学习表面身份可行、简单先验/局部有小收益；不能把PointNet+近邻包装成足够创新。下一研究假设是**动态模板条件的query与表面对应**，最终再与RGB/MHR先验和sensor表面几何形成共同约束。

最终使用应为：RGB-D → frozen SAM/MHR初值 → 传感器表面/原工程几何基线 → 任意canonical工程query与观测对应 → 在患者预测Mesh绑定face/bary/xyz/normal → 规则/atlas生成目标 → 验证后机器人变换。没有临床标签时仅ENG接口，不能说医生穴位精度。
