# 项目当前状态

更新时间：2026-10-10。现役入口以本页及所链接的机器可读结果为准；历史 handoff 保留当时的合同与结论。

**服务器操作偏好（最新）：**只有用户明确要求关机才关闭；先前“任务结束自动关闭AutoDL”的要求已撤销。当前原AutoDL保持无卡模式，未开启新付费GPU或训练。

**主线：**R3/R3.1/R4及R4.1公平Txyz诊断已完成。R4.1复用232帧原始A采样/固定B点与六个R4 Best模型，Official+Txyz逐帧trace/顶点/指标回归差值0。G1+Txyz三seed VAL median/P95为19.26/97.27、12.47/47.70、14.98/60.95mm，均未超过Official+Txyz 11.23/41.60mm；TRAIN median优势主要由救回11个Official超限帧贡献，正常应用帧三seed平均配对误差均更高。p001196及腰/四肢尾部仍恶化。工程维持Official+Txyz，研究建议先Camera/Body解耦再人体几何；不据此宣称真实Pose/Shape/穴位优势。见[R4.1最终报告](handoffs/real-scene-2026-10-10/rgbd-sam3d-r41-fair-txyz/FINAL_REPORT.md)、[逐身份](handoffs/real-scene-2026-10-10/rgbd-sam3d-r41-fair-txyz/PER_IDENTITY.md)。TEST未读；本轮零训练/新推理，3248条帧方法评价、48张固定对照图及缓存自审PASS。完整证据备份到本地与218持久服务器；11:23执行AutoDL关机exit0、SSH随后拒绝连接；交付后暂停，不自动续训。R4公制响应证据仍成立，不将它等同人体几何精度。

**最新R4.2：**232帧全量Camera/Body双向交换完成。保持Official Body并用G1 Camera＋Txyz，VAL三个seed为19.69/56.38、12.26/45.05、15.36/50.52mm，尾部低于耦合G1，但仍未超过Official＋Txyz。相同Body的最终Camera仍有14–26mm逐帧中位差异，不能把Txyz后差距全归给人体参数。39系数Camera-only头实际以18 TRAIN身份的A伪监督训练、TRAIN内留一身份选λ，VAL＋Txyz29.98/81.59mm，失败不晋升；训练域与R4合成不同，不声称架构公平排名。全程TEST未读，B只评价；1856新网格组/5568缓存文件与8组距离重放自审PASS，27帧×3seed＝81张图含全部11旧fallback。几何/训练在本地CPU，无卡AutoDL仅CPU接口QA与RGB导出。当前不启动大训练；工程保留Official＋Txyz，研究保留独立Camera路径，下一项是同合成数据的final-only Camera短跑与可见表面监督。见[R4.2报告](handoffs/real-scene-2026-10-10/rgbd-sam3d-r42-camera-body-decoupling/FINAL_REPORT.md)。

## 目标

**R4.2几何补充核验完成：**重新读取官方原始标定，232帧K/R/T精确一致；官方4×4变换与历史实现最大差0.0003375mm，64个独立三角面距离控制通过。54原始Depth视图重建与缓存最大差0.001263mm（缓存一致性，不是物理测量精度）；四帧/八视图顺序RGB解码与缓存精确一致，硬件时钟未提供，物理配准/同步不称完全验证。p001195全部11个旧fallback的A射线signed深度偏远204–260mm，大错在A就存在；p001196固定Body换Camera后仍可恶化，有限步Txyz不完全消除起点差异。378条A诊断、16新图、696输入及378网格SHA核验完成；保留p100072观测关联极端尾部。没有新SAM推理/训练、B拟合或TEST读取。R5数据升级仅提出计划，不自动启动。见[独立几何最终报告](handoffs/real-scene-2026-10-10/rgbd-sam3d-r42-geometry-verification/FINAL_REPORT.md)、[R5建议](handoffs/real-scene-2026-10-10/rgbd-sam3d-r42-geometry-verification/R5_DATA_UPGRADE.md)。

真实**俯卧背部 RGB-D → 双模态融合 → 个体原生 MHR Mesh → 标准模板固定拓扑点位传播 → 后续机器人坐标接口**。工程效果与可发表的方法贡献并行推进，表面距离、点位稳定性、医学准确率及部署精度分别验收。本轮优先人体几何，不训练独立穴位网络；目前无部署相机和独立临床穴位真值。

## 最新实际交付

[R4.2 Camera/Body解耦与CPU小模型验证](handoffs/real-scene-2026-10-10/rgbd-sam3d-r42-camera-body-decoupling/README.md)：支持人体路径隔离以减少尾部干扰，但位置与小模型仍不可靠，不替代Official＋Txyz；完整逐人逐帧、81图、原生缓存/模型私有备份及执行自审交付。

[Official＋Txyz三种子重复检查](handoffs/real-scene-2026-10-10/rgbd-sam3d-r41-official-seed-audit/README.md)：缓存Official初值、Anchor和A/B点集固定，在Python/NumPy seeds 11/23/37下实际复跑696次Txyz/精确B评价，所有trace/平移/网格/逐点距离差异0，TRAIN 24.65/80.32、VAL 11.23/41.60mm，重复SD为0。这是缓存算法重复性，不是三个Official训练模型，也未检查重新运行GPU的数值波动；G0/G1三训练seed的波动保留，R4.1结论不变。全本地执行，AutoDL保持关机。

[R4.1公平Txyz比较](handoffs/real-scene-2026-10-10/rgbd-sam3d-r41-fair-txyz/FINAL_REPORT.md)：七缓存基底×232帧，同原Anchor/点集/算法。G1+Txyz VAL平均15.57/68.64mm，工程基线11.23/41.60mm；全部seed和负面身份保留。A-only组件诊断支持平移之外仍有局部残差，真实无MHR解剖真值。原R4的模型与训练均保留，本轮结束暂停。

[R4公制Camera与局部几何候选](handoffs/real-scene-2026-10-10/rgbd-sam3d-r4-metric-local/FINAL_REPORT.md)：自审PASS后完成四短跑与六正式cell。公制机制有合成/物理证据，真实尾部优势未成立；G2/G3没有晋升。4800正式合成native预测、1392真实native预测和12正式checkpoint备份通过；全部失败保留，不作为临床穴位或俯卧裸背精度。下一轮优先真实A表面监督和背向/俯卧域覆盖，保持B仅考试，解冻Decoder需单独消融。

[R3.1诊断与匹配小规模验证](handoffs/real-scene-2026-10-10/rgbd-sam3d-r31-diagnosis-pilot/FINAL_REPORT.md)：三seed fixed-mask Depth、七历史模型基底1624次Cheap Txyz、14历史失败图、两个原生MHR候选实作、四组100身份×8epochs、全部232帧独立B及机制干预完成。B合成camera顶点83.23mm优于RGB-only97.69mm，但真实VAL24.35mm劣于RGB-only21.31mm与Official+Txyz11.23mm。研究机制线索保留，稳定真实优势未成立。

[RGB-D SAM3D / MHR R0](handoffs/real-scene-2026-10-09/rgbd-sam3d-r0/README.md)：新实例资源及旧微调接口实际审计；官方权重本地源SHA与官方LFS匹配，重新传到AutoDL并备份218；HuMMan必要压缩包下载与环境准备见回执。Depth encoder/残差与交叉注意力、官方backbone后接入适配器、同RGB affine的米制Depth裁剪及待GPU的原生MHR训练检查入口已实现。小模块梯度与几何检查PASS，不等于R1或真人精度；具体下载/安装完成状态以R0报告为准。以下为历史证据，旧服务器等待/旧路线“下一步”不覆盖本轮决策。

[固定工程点传播诊断V1](handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/FINAL_REPORT.md)：全本地0新推理/拟合/训练，1,920条数字参考点误差重算、1,440真人位置/960三角面绑定重算、480跨度与82公开图完成，小缓存独立回放PASS，1,091源SHA前后不变。16已消费角色切向组表面0.324mm但工程点中位6.378mm、中心点19.651mm；真人Rigid/D跨度8.050/7.391mm，是稳定性而非精度。原8ENG点/20人/三划分保留；完整受控Mesh仍不可读，没有宣称重新计算全网格几何或真人穴位准确率。当前工程基线为标准Mesh固定face/bary→患者表面xyz/法向，再以独立参考决定是否需要解剖辅助模块。[全量图索引](handoffs/real-scene-2026-10-08/engineering-point-transfer-diagnostic-v1/VISUAL_INDEX.md)

[真实观测点云接口V1](handoffs/real-scene-2026-10-05/observed-prone-surface-interface-v1/FINAL_REPORT.md)：本地S107原始作者点云实际接入冻结V2，原RGB/depth/相机点数组与历史SHA完全一致、seed0 split逐数组一致；9452个合格train点中固定取512，与留出交集0。双输入分支6建议/16规则及缓存独立重放通过，输入切换建议移动0.75–1.08mm；这是输出差异而非精度。没有训练、新SAM或拟合；结构权重与fixture参考不升级，射线修正未应用。原图叠加本地保留，其他19人原始输入与大规模训练仍等服务器恢复。

[MICCAI 2026三篇获奖论文学习](research/2026-10-05-miccai-best-papers/READING_NOTES.md)：实际下载三篇接收版、阅读方法/实验并查看关键图，检查LRM-Functa与L-TGVN作者代码。当前优先借鉴测量约束与解剖参考分工，视频低秩留待连续数据，CancerVerse借鉴资源/标注一致性评价；没有运行这些作者模型或修改冻结V2训练。L-TGVN公开实现为软谱过滤，不能称绝对硬零空间保证。下一步仍是全量来源/先验对照及真实深度与独立参考验证。

[独立体表参考/穴位核验接口V1](handoffs/real-scene-2026-10-05/independent-surface-reference-interface-v1/FINAL_REPORT.md)：实际核查GB/T12346-2021相关方法/目标页，明确椎体等级坐标不是B-cun、CT代理不等于棘突下标准位置。独立深度反投影及逐标注者/一致性比较CLI已实现，解析模拟正常路径16比较/8配对通过；零真人标注、零新临床准确率，不从预测Mesh制造参考。模型大规模验证仍等待可用服务器。

[参考约束表面/解剖场V2](handoffs/real-scene-2026-10-05/reference-anchored-surface-field-v2/FINAL_REPORT.md)：四TRAIN三模型40步、刚体/单位一致性、正式评价器缓存重算及20实际Mesh→60建议/160规则完成，220面绑定重算通过。参考为fixture、观察点为网格采样，非新RGB-D或医学准确率；结构权重3/4来源仍输比例先验。不再调小例，当前候选是V2的大规模来源/先验/软参考/硬参考/联合对照。服务器TCP可连但SSH握手失败，全量数据MD5与九训练仍待恢复核实，V1保留研究起点。

[大规模解剖来源与联合场基础V1](handoffs/real-scene-2026-10-05/anatomical-surface-method-foundation-v1/FINAL_REPORT.md)：实际读取V3完整档案1939 CT/1830 train/109 test，预冻结1393成人TRAIN、125开发、88作者test图像；资格后数量未定、没有独立患者ID。最后确认33.964/37.416GB，后续磁盘等待/SSH失败，完整MD5待核实。四旧训练来源18等级64/72有效、32768点与缓存重算完成；GPU四例80步联合场、CPU三模型训练/解码及先验/聚合正常路径完成。表面分支未优于零修正；大规模训练和真实MHR学习接口未执行。继续完成完整来源与模型对照，保留可靠几何/两参考比例基线。

[两参考→规则工作台V2](handoffs/real-scene-2026-10-05/prone-reference-rule-workbench-v2/FINAL_REPORT.md)：20缓存Mesh接入、60建议/160规则、20图及真实浏览器4输入→3建议→8规则→保存/重算完成。新增两参考比例建议与显式工程采纳；输入及建议分开，医学未确认，坐标与CT外部考试不同，不转述9.70mm为此系统精度。继续扩大解剖来源与联合表面/对应方法基础。

[同步CT外部考试＋两参考基线](handoffs/real-scene-2026-10-05/tum-synchronized-anatomy-validation-v1/FINAL_REPORT.md)：实际下载268文件/513.8MB、17病例来源资格、442预测缓存/1380有效目标重算与9页全量图完成。10世界坐标例普通查询37.98mm，没有保持源内优势；相同剩余代理点查询38.86→两参考校准14.39mm，简单两参考比例先验9.70mm。参考为CT oracle，非相机/医生输入、非俯卧穴位精度；7导出坐标例另列。停止CT小网络调试，继续把显式参考坐标接到真实MHR工程，并以比例先验作为论文新方法必须击败的基线。

[俯卧参考→规则→Mesh工作台V1](handoffs/real-scene-2026-10-05/prone-reference-rule-workbench-v1/FINAL_REPORT.md)：20人缓存接入、160个几何fixture候选、实际S104图像点击/HTTP生成/保存/独立重算通过。可输入7参考与显式个体B-cun比例，生成8候选及face/bary/normal；切换患者清空输入。参考及比例未医学确认，相机未部署标定，不报告穴位准确率。

[CT输入线索对照V1](handoffs/real-scene-2026-10-05/ct-surface-cue-ablation-v1/FINAL_REPORT.md)：12新训练/1404缓存/78全量图/CPU重算完成。有序查询完整17.57、去高度17.08、只留扫描尺寸25.20mm（12已消费CT测试，非医学精度）；没有稳定高度增益。停止CT小模型继续调试，保留来源与基线，进入真实MHR参考输入→规则候选→面绑定工程工作台。

[CT解剖参考查询V1](handoffs/real-scene-2026-10-05/ct-anatomical-query-pilot-v1/FINAL_REPORT.md)：三卡9训练完成，78输入/780缓存/3120有效目标和全量图、实际缓存独立重算通过。12例CT代理X/Z：回归21.80、热图20.94、有序查询17.57mm；3初始化一致优于回归，逐例8改善/4退化。保留来源内候选，不称临床或俯卧定位；输入证据消融已完成（见上项），不继续CT小模型调试。

[CT解剖参考来源V1](handoffs/real-scene-2026-10-05/ct-back-anatomical-reference-v1/FINAL_REPORT.md)：102例小包实际下载3.2446GB并通过作者MD5，全部外表面/五等级代理抽取、17页全量图检查完成。一例倾斜扫描重采样，一例C7逆序的训练来源完整排除，原记录保留。代理中心与后侧极值的水平差异T5/T9/L2中位15/21/15mm。51训练/11开发/12新任务考试/4作者val支持的外表面定位对照已完成，由以下交付承接。CT代理不是俯卧或医学穴位GT。

[解剖身体模型学习与路线调整](research/2026-10-05-anatomical-body-models-v1/READING_NOTES.md)：实际下载5篇论文、查看方法/失败/骨骼图、读取3份作者源码。SKEL运动脊柱为三大段，不直接输出穴位所需逐节水平；未运行HSMR/SKEL-CF。TotalSegmentator102例CT小包的下载与全量来源资格已完成，由上述交付承接；元数据98train/4val。不会将CT代理称俯卧或穴位GT。

[俯卧点位工作台V1](handoffs/real-scene-2026-10-05/prone-body-query-workbench-v1/FINAL_REPORT.md)：20人、600绑定/4800ENG点、120面缓存、全量对照与独立重算完成。BODY跨度19.33 mm、与Topo差143.02 mm，未升级；默认Topology跨度7.39 mm（非医学误差）。工作台原图点击→实际Mesh射线绑定→本地复核JSON已经浏览器与真实文件验证；原RGB私有，公共几何版进入Git。

[局部身份学习结构对照V1](handoffs/real-scene-2026-10-05/body-intrinsic-query-learning-v1/FINAL_REPORT.md)：三卡9训练完成、3600评价/40图/实际缓存重算PASS。PARTIAL身份BODY FAUST2.21/SCAPE7.17；DUAL2.63/8.07（%各库sqrt-area，非mm），几何分支更差。不采用该双路候选，不再在消费考试上调轮数。工程保留Topology，论文转向可靠解剖/身体结构参考与新的数据证据。

[同输入局部曲面编码V1](handoffs/real-scene-2026-10-05/intrinsic-local-query-v1/FINAL_REPORT.md)：362局部算子/1080评价/40扫描图完成，实际缓存重算PASS。冻结全身DiffusionNet在局部背部输入失败（PARTIAL FAUST13.36、SCAPE12.49 %各库sqrt-area），不能把全曲面参考1.70/2.40作为局部部署效果。当前进入身体位置参考＋局部曲面特征双路query训练对照，保留拓扑工程默认。

[MHR模板查询工程接口V1](handoffs/real-scene-2026-10-05/mhr-query-engineering-interface-v1/FINAL_REPORT.md)：20俯卧、3训练点划分、两缓存Mesh、960绑定/7680ENG点完成。16已消费测试角色RigidD输入跨度：拓扑7.39、学习22.03–25.07 mm，学习点与拓扑差174–194 mm；贴面约2 mm不能证明身份正确。默认保留拓扑。120原Mesh与960绑定实际核查，Git交付目标/面缓存可独立重算。原始20pose_type实读均p_sel_prn。

[可换模板对应V1](handoffs/real-scene-2026-10-05/paired-template-query-v1/FINAL_REPORT.md)：FAUST60训练/20开发/20已消费考试，SCAPE20姿态跨库。局部query身份GLOBAL约1.96→7.22（各库sqrt-area百分比，非mm），LOCAL更差；实际作者完整上下文参考SCAPE2.40，非公平局部输入对照。6模型/2520评价/40全量图、实际缓存重算完成，不采用小网络为最终匹配。当前转向相同局部输入的曲面几何编码器。

[注册后背身份学习机制V1](handoffs/real-scene-2026-10-05/registered-back-correspondence-v1/FINAL_REPORT.md)：服务器实际下载100 FAUST/71 SCAPE注册衍生扫描；FAUST60训练/20开发/20网格来源考试，9身份场模型+6query模型完成。PARTIAL可见query身份：近邻8.19、全局2.22、先验局部1.57（%模板sqrt-area，非mm）；完整上下文DiffusionNet作者基线1.70。直接query1.90弱于身份场反查，保留失败。Oracle ROI/完整几何归一化/程序缺失，非俯卧或医学GT。当前转向成对模板可移植性，原保留20已消费。

[Mesh引导坐标对照V1](handoffs/real-scene-2026-10-05/mesh-guided-back-chart-v1/FINAL_REPORT.md)：原20人、1080曲线、3240学习绑定/180拓扑绑定完成。固定人体坐标跨度21.28→20.90 mm，8改善/8退化、初始化跨度14.36→22.89 mm；约44%目标超出线范围而钳制，不采用为最终定位。新的27工程点与旧9点定义不同。全量缓存重算及180实际Mesh核验通过。当前继续注册人体表面身份学习机制，不调这20人测试范围。

[最新两阶段完整交付](handoffs/real-scene-2026-10-05/prone-learned-reference-transfer-v1/README.md)：服务器既有存储已恢复，六个体表线小模型实际训练完成、冻结模型俯卧迁移完成。没有新SAM推理或Mesh拟合。以下先列新增事实，原三阶段及更早交付保留历史合同。

- [体表线学习](handoffs/real-scene-2026-10-04/surface-line-completion-pilot-v1/results-v1/FINAL_REPORT.md)：20训练/4开发/6已消费扫描来源，两策略×三初始化各120轮；216评价/222缓存。缺失增强相对普通模型作者线横向差异6.99→4.15 mm，6/6来源改善。不是独立患者/俯卧/穴位精度。训练实测10.76分钟；缓存重算exact通过。
- [俯卧冻结模型迁移](handoffs/real-scene-2026-10-05/prone-learned-reference-transfer-v1/FINAL_REPORT.md)：原20人、360曲线、1080绑定/9720ENG点。与沟槽共同12人的RigidD绑定输入跨度25.41→16.66 mm；完整16人对普通模型13改善、3退化，初始化跨度仍15.17 mm。表面未重新拟合；跨度不是定位误差。留出输入交集0、180实际网格与全部缓存核验通过。

[上一轮连续执行索引](handoffs/real-scene-2026-10-04/continuous-execution-summary-v1/README.md)保留当时三阶段状态；其训练待运行说明已被上述执行结果承接。

1. [有界参考对应V1](handoffs/real-scene-2026-10-04/bounded-reference-correspondence-v1/FINAL_REPORT.md)：同一60固定表面、300对应缓存/2400点/60图完成；180旧缓存精确继承、430源不变。16已消费验证来源切向带噪：FIXED9.271、RBF6.586、CONVEX4 5.338 mm；但P95 9.269→11.438变差。投影前考试点最大噪声响应14.730→4.563 mm，噪声放大减少；控制组仍全部退化，不能补救参考身份错误。工程基线保留，不当医学teacher。

2. [俯卧参考到Mesh接口V1](handoffs/real-scene-2026-10-04/prone-reference-mesh-interface-v1/FINAL_REPORT.md)：20人×3seed×3几何方法180记录，132曲线、396绑定、3564ENG点和20全量图；train-only、267源不变、缓存位置/bary/法向实读通过。三seed完整的12/16测试角色：沟槽源点跨度25.52 mm，RigidD贴面1.58 mm、跨度仍25.41 mm；**接口跑通，当前曲线不宜当穴位参考**。对应机制增量见上项，不启动医学伪标签训练。

3. [真实几何参考提取V1](handoffs/real-scene-2026-10-04/back-reference-extraction-v1/FINAL_REPORT.md)：30真实XYZ扫描×3方法、90曲线/评价完成；预测不输入作者标记/画线。共同覆盖中位90.66%；与作者画线差异：轮廓10.51、对称11.87、沟槽3.69 mm，沟槽26/30改善、4/30退化。90缓存独立重算PASS，30图全部保留。**非俯卧、作者已裁背部、非穴位GT；不替代临床精度。**原PLY仅XYZ，没有颜色；上一轮color_present不能据读取字段列表判真。俯卧接口增量见上项。

4. [真实背部参考来源资格V1](handoffs/real-scene-2026-10-04/real-back-reference-qualification-v1/FINAL_REPORT.md)：20俯卧RGB实读/复看；324真实扫描、1326关联候选实算，459几何兼容候选，四标记路由60份合并成30参考包/30扫描SHA。1043项源资产前后冻结、30原扫描暴力最近点及坐标重建、30完整几何图通过。M1/M2到体表画线的每包中位再跨包中位约31.72 mm，注册标记轴不能直接当后正中线。**真实扫描参考可开发；仍无合格俯卧RGB-D/医学穴位GT；不以30扫描称30独立新患者。**零推理/拟合/训练。[完整索引](handoffs/real-scene-2026-10-04/real-back-reference-qualification-v1/README.md)

5. [四参考点辅助表面对应V1](handoffs/real-scene-2026-10-04/reference-assisted-correspondence-v1/FINAL_REPORT.md)：沿用20份受控几何与60个固定D_VECTOR表面，四个已知工程参考输入、另外四点只考试，180点位缓存/1440逐点记录/60页图完成。16验证角色切向组：固定拓扑9.271→准确参考3.681 mm，16/16改善；参考带5 mm扰动后6.586 mm，13/16改善。法向组准确参考仅4/16改善；带噪参考使原本0.306 mm控制组退化到5.056 mm。RBF负权重放大噪声，当前插值不适合作最终定位。407冻结源/60固定表面/180点位核验PASS；独立交付复算PASS。**四参考为合成oracle工程身份，非自动识别/医生/穴位真值。**零新推理/拟合/训练。[全量表图与审计](handoffs/real-scene-2026-10-04/reference-assisted-correspondence-v1/README.md)

6. [已知参考几何与绑定点受控闭环V1](handoffs/real-scene-2026-10-04/controlled-back-reference-v1/FINAL_REPORT.md)：20份既有预测作为程序生成参考，精确虚拟相机，三类注入×四方法，60 case/240最终网格/480逐点指标/1,920工程点结果/60页图全部完成。16验证角色：法向凸起组表面Rigid 1.330→法向D 0.330 mm、8点2.778→1.128 mm；切向组表面0.440→0.323 mm，但8点6.431→6.420 mm，中心附近点仍约19.766 mm。解析平面反例表面近零、绑定点仍错20 mm。52冻结源、20参考/60观测/240缓存核验PASS；有局部边长及面法向代价。**不是真人/独立sensor/医学精度。**零新SAM推理、零训练。[完整表与图](handoffs/real-scene-2026-10-04/controlled-back-reference-v1/README.md)

7. [工程模板与法向几何对照V2](handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2/FINAL_REPORT.md)：新8个ENG中性探针/300缓存/2,400传播完成；20人×3种子新增60个法向D，四方法240缓存/评价完成。16人测试角色后背距离Rigid 8.25、向量D 3.66、法向D 3.99 mm；切向移动1.86→0.48 mm，但跨种子点跨度7.39→7.75 mm，14/16人法向D的全身投影支持IoU弱于Rigid。300个BEHAVE候选资格筛查不足5×6帧，Sub07最多3个非相邻时刻/1序列，未启动新BEHAVE模型。470冻结源与240缓存核验PASS，原180基线逐点指标exact一致。没有新训练/SAM推理，不能作为临床或部署精度。

8. [可信俯卧五方法修正版](handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2-execution/FINAL_REPORT.md)：PressurePose 20人、开发4/测试角色16、3 seeds，共300缓存完成。优化前划分6 cm空间块留出，各分支共享新的Official。测试角色后背距离Rigid 8.25→Rigid+D 3.66 mm；属于近似相机合同下的同源空间留出，13/16人全身投影支持IoU下降，不是产品或穴位精度。
9. [表面与点位对应验证](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/FINAL_REPORT.md)：300缓存/单位/拓扑实读；2,400工程点、60共享规则框架及2,400规则代理点；BEHAVE五人固定45帧、五方法225网格、K1/K2/K3独立sensor对照完成。
10. 新BEHAVE posterior patch：Rigid 30.80→Rigid+D 30.32 mm，4/5人改善，Sub06略退化。180视图仅36个held-out后背小块/28帧有效；仅5帧/3人同时有K0及held-out后背参考。穿衣、非俯卧、已消费人物，**不足以确认俯卧裸背的稳定独立D增益**。[全部结果](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/results/p2/RESULTS.json)
11. 旧8点atlas：canonical原始cm，修正为×10 mm；缓存m×1000不变。同拓扑通过，但旧GV14/GV4上下颠倒、中线种子偏侧、左右与历史轴声明冲突。**语义HOLD，不生成医学标签或治疗目标。**[资产审计](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/results/p0/POINT_ASSET_AUDIT.json)
12. [公开数据资格](handoffs/real-scene-2026-10-03/prone-back-point-validation-v1/DATA_QUALIFICATION.md)：DMD历史205组全部视觉检查，1张确认俯卧；当前V2为0图。PCdare324非Output点云与1,326线候选已枚举，有源码支持的几何重新绑定；没有三维穴位GT或已核验校准prone RGB-D关联。

PressurePose和BEHAVE的区域、相机和聚合不同，不把绝对数值拼成同一项精度。全部失败和缺失保留。上述为早期几何/体表线历史结果；最新R3/R4已训练原生SAM3D融合适配器，官方backbone/Decoder冻结，不能把早期“无SAM训练”当作当前状态。

## 已有基础

- 官方SAM3D Body checkpoint/MHR推理、真实图像Mesh叠加已跑通；不等于从头复现论文训练。
- 历史Cheap Txyz：HuMMan36帧63.63→22.48 mm；BEHAVE五人45帧whole-body口径31.17→17.80 mm。单向depth点→面距离，不是穴位准确率。[历史报告](handoffs/real-scene-2026-09-11/behave-cheap-txyz-generalization-v2/results-v2.3/RESULTS.md)
- [固定顺序复现V1.4.12](handoffs/real-scene-2026-09-14/sam3d-txyz-reproducibility-isolation-v1/formal-execution-v1.4.12/README.md)历史Gate通过，225次SAM B–F固定顺序精确一致、27特征稳定；另有最大约0.001 mm帧顺序浮点效应，后续保持帧顺序冻结。
- 历史合成RTMPose只证明合成工程任务可行，不能推导当前真人穴位定位精度。

## 历史几何与穴位 Gate（不覆盖本页R4状态）

| 事项 | 状态 |
|---|---|
| 缓存传播/单位/同拓扑 | 新ENG atlas几何绑定通过；人体解剖左右/旧医学语义仍未验证 |
| Rigid+D同源局部拟合 | 局部收益成立，存在轮廓/全局质量代价 |
| Rigid+D独立机位后背收益 | 已执行；收益小、覆盖有限，未通过强结论 |
| 法向D单因素对照 | 60新分支完成；切向代价下降，种子稳定性/完整网格合格性未通过 |
| 已知几何/对应受控闭环 | 已完成；整体/法向错误可恢复，切向绑定错位仍在；不替代真人精度 |
| 真实标记/体表线来源 | 324扫描/1326候选审计、30包通过几何开发；注册标记轴与画线分歧，医学中线语义HOLD |
| 四参考点辅助对应 | 已完成；准确参考改善切向错位，但带噪参考退化/放大明显；真实参考来源和医学语义仍HOLD |
| 新BEHAVE共同后背cohort | 300候选筛查不足计划预算；未签发manifest，0新模型/拟合 |
| 8点atlas医学语义 | HOLD；独立代理候选也未医学验证 |
| Mesh+规则代理链 | 跑通；椎体/B-cun输入为代理 |
| 独立三维穴位/可靠目标对应 | 尚无资格数据，不报告准确率 |
| 体表线小模型训练与迁移 | 已完成；源域改善、俯卧仍厘米级分歧 |
| SAM3D融合适配器 / Mesh teacher / DMD37伪标签 | R3/R4融合训练已完成；官方Decoder未解冻；医学teacher/伪标签未放行 |
| 部署相机、机器人变换及接触控制 | 未验收 |

## 运行位置

最新计算服务器：`root@connect.cqa1.seetacloud.com:39846`，根目录`/root/autodl-tmp/rgbd_sam3d`，R4代码`r4_code`、输出`runs/r4_geometry_v1`、Python`envs/rgbd/bin/python`。持久备份`xuhd@172.18.6.218:436`的`/raid5/xuhd/rgbd_sam3d_backups/2026-10-10_r4_geometry_v1`；本地备份`output/r4_development/private_backup`。关机状态见R4执行Ledger。

以下为10月5日前后历史几何路线位置，当前可用性不能由旧记录推断：`xuhd@172.18.18.151:436`当时出现磁盘等待/SSH失败。GPU0/2080Ti此前完成六个体表线小模型；其“没有SAM微调”描述只适用于当时任务，不覆盖R3/R4。

- 有界参考对应：`/raid5/xuhd/datasets/bounded_reference_correspondence_v1_20261004`
- 俯卧参考Mesh接口：`/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004`
- 真实曲线提取：`/raid5/xuhd/datasets/back_reference_extraction_v1_20261004`
- 已完成学习原型：`/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004`
- 俯卧冻结模型迁移：`/raid5/xuhd/datasets/prone_learned_reference_transfer_v1_20261005`
- 最新真实参考资格：`/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004`
- 参考辅助对应：`/raid5/xuhd/datasets/back_reference_assisted_v1_20261004`
- 已知参考受控闭环：`/raid5/xuhd/datasets/back_controlled_reference_v1_20261004`
- 真实缓存法向对照：`/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003`
- 上一轮：`/raid5/xuhd/datasets/prone_back_point_validation_20261003`
- 300俯卧Mesh源：`/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2`
- BEHAVE数据：`/raid5/xuhd/behave_rgbd_mesh_v1/data`
- 新资料：`/raid5/xuhd/datasets/back_prone_acquisition_20261003`
- SAM代码/权重：`/raid5/xuhd/sam3d_s01_pilot_20260906`，授权权重不入Git。

完整RGB复查保留服务器及本地`output/prone_back_point_validation_v1`；Git交付不含原图的预测图、代码、配置、索引和指标。原始数据、原生模型资产、大型NPZ不重发。

## 下一步

现役R4下一步：保留G1＋匹配G0＋Official/Txyz，优先设计真实TRAIN相机A表面监督和背向/俯卧域覆盖的独立对照；B只考试，TEST不碰，解冻Decoder另设消融。不继续机械堆G2/G3或只挑最好seed。当前没有证明最终俯卧/穴位精度。

早期体表线训练的历史结论：缺失增强有帮助，但工程点仍厘米级变化、没有可靠医学身份。其几何基线保留，不继续用16名已消费角色调参追分。穴位阶段仍需可靠后正中参考及上下端身份，再比较拓扑传播与规则；不能把作者画线、稳定输出或小贴面分数当医学teacher。相机标定、完整Mesh质量及部署验收分别推进。

本轮原计划见[工程模板与几何机制验证计划V2](research/2026-10-03-no-deployment-camera/NEXT_EXECUTION_PLAN_V2.md)，执行结果以上方最新报告为准。完整原RGB新副本在本地 `output/back_geometry_correspondence_v2/private_review/INDEX.html`。

医学对应最终需要可靠独立目标参考，部署效果最终需要设备标定和验收。当前小残差不能替代这两项。
