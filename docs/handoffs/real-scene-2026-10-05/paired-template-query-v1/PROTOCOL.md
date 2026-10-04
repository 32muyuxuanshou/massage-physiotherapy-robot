# 成对模板查询V1：可换模板的真实注册扫描机制

主问题：不依赖固定FAUST canonical坐标，把模板任意query经共享形状描述子匹配到当前观测表面，能否跨模板/数据来源工作。向最终MHR模板查询接口前进，不增加临床标签、SAM训练或不确定性模块。

## 输入/模型

源模板点云XYZ/法向、模板query采样索引、目标可见点云XYZ/法向。共享PointNet编码+全局max；PAIR_LOCAL额外12近邻边编码。源query描述子与目标点描述子相似度×20，加共享MLP(两描述子+XYZ相对位移)。不输入GT对应、FAUST固定canonical坐标、vts编号或医学穴位名。

训练随机FAUST源/目标姿态对，query来自源模板实际几何；注册同义采样只用于监督soft matching（sigma0.01）。source/target均小旋转增强，所有条件沿上一轮缓存。PAIRED_NN为源query XYZ直接检索目标XYZ的几何基线。

PAIR_GLOBAL / PAIR_LOCAL ×seed0/1/2；1200steps、batch8、256候选、24随机query、Adam0.001、每200steps仅开发选checkpoint。仍仅000–059训练，060–079开发，不看考试改参数。

## 数据角色与转换

- FAUST 080–099已被两前轮消费，作为连续机制验证来源，不称全新泛化。
- SCAPE mesh051–070为本轮新跨数据姿态考试；不把20姿态说成20患者，不混入训练/开发。
- 只用各数据集**库内**共享vts对应；绝不假设FAUST与SCAPE的5000行跨库同义。每库独立模板000、独立后背ROI和query。
- source模板FAUST000 / SCAPE000几何公开可读，但无SCAPE对应标签/测试输出进入训练。模型可以看到SCAPE000的模板几何，这是matching任务给定的参考，不是零样本无参考检测。
- SCAPE原生前向为+X，与FAUST的+Z不同，头部侧面核对后固定proper rotation：x'=-z,y'=y,z'=x。先前另一方向预览是前胸，在训练/考试前修正；不靠模型分数选方向。
- 统一单位面积归一化。SCAPE仅一次纯数据预处理；后背裁剪仍是oracle注册ROI，缺失/噪声仍为程序模拟，不冒充真实RGB-D或临床证据。

每库template在原生/统一坐标按Y0.10…0.42、|X|<0.18、Z<-0.02、normalZ<-0.30定义ROI；9×3工程网格近邻后去重，数量独立记录。每源×FULL/PARTIAL_BAND/NOISY_PARTIAL×扰动seed0/1/2。FAUST沿旧180case；SCAPE180新case，原角色不变。

## 评分与交付

模型对全部template query推理；随后评分器仅使用可见query，GT可见率单列，不输入模型。保存所有query检索索引、可见掩码和face/bary；不可见输出不批准定位。绑定为作者观测扫描上的顶点角点，非预测MHR/治疗点。

先初始化平均、再扰动seed平均、再每来源/条件统计，最后每库20来源中位。指标为query身份位置距离/P95及当前扫描位置距离，单位% sqrt(area)，不是mm或测地误差。FAUST/SCAPE不混成同一患者精度。

完整上下文的作者DiffusionNet-HKS（训练80 FAUST）只作更强输入支持参考，不混入相同局部输入主对照。新增源/代码/配置在执行前hash，实际缓存可重算。原始/标签/几何缓存/权重仅服务器，Git交付代码/指标/来源摘要和全量误差图。

本轮不强求新网络胜出；要区分“目标查询接口能运行”与“材料身份真的认准”。若SCAPE迁移失败，报告失败，不用考试调权重。MHR/俯卧真正迁移及医学语义仍单独验收。
