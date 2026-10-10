# R5 Camera-only 夜间对照：完成，暂不替换工程基线

本轮15个训练cell、18个GPU诊断、15×232帧真实独立Camera B评价均已完成。**Depth确实帮助恢复距离，新扫描数据也有收益；但当前小Camera头仍明显弱于Official＋Txyz，不能作为最终按摩定位模型。**全部正常与失败样本保留，没有读取封存TEST，没有因真实评价结果重新选checkpoint。

## 实际做了什么

- 原生MHR合成：400 TRAIN身份/3,200张、50 VAL身份/400张；另外50 TEST身份/400张未读取。各身份2种姿态×4视角。复用完整冻结Official输出和1280维backbone池化特征。
- 新照片纹理扫描：HuMMan 12身份、48个固定扫描Mesh×64物理相机＝3,072张；9 TRAIN/2,304张，3 VAL/768张，464张截断图保留。相机距离、倾角、视角可控，但衣物扫描中心不是MHR root，未伪造root标签。
- 三个Camera头各seeds11/23/37、30epochs，共9组：raw残差限制、公制XYZ残差、仅RGB小头。它们不是旧R3完整融合网络。
- 公制XYZ各seed从相同预训练last状态，做native-only与native＋scan两组匹配续训，各20epochs，共6组。每组native顺序、曝光、200次更新/epoch相同；mixed另外4张scan/更新，额外计算单列。不是整个SAM3D重训。
- Body、Pose、Shape、Scale、global rotation及完整MHR参数固定。只有Camera发生变化；最终相机空间顶点/投影重新计算。

native监督：逐轴Camera Smooth-L1，beta=0.05m。scan监督：**原nvdiffrast透视渲染器**，640×480原K，完整clean person-mask轴向Z Smooth-L1（beta=0.02m）＋逐图抗锯齿轮廓IoU。权重由TRAIN32 native＋TRAIN32 scan的Camera梯度量级固定：Z=0.1944463、轮廓=0.2604647。没有执行Anchor替代训练。原渲染器解析透视、梯度QA见[冻结回执](WEAK_SUPERVISION_FREEZE.json)。checkpoint仅按native VAL Camera L2选择。

218的8×2080Ti完成原生训练及5卡扫描Official初始化；既有AutoDL RTX6000D以原渲染器完成续训、扫描VAL和Depth消融；218 CPU完成独立B评价。GPU已没有任务，完整备份核验后执行了AutoDL关机指令；218保持开启。

## 主要结果

真实HuMMan沿用已消费的开发数据：18 TRAIN身份/192帧、4 VAL身份/40帧。A为输入和Txyz拟合，B固定2,048点只评价；历史精确点到三角面距离、frame→sequence→identity等权汇总完全复用。下表的median/P95是该层级汇总，**不是所有点合并后的分位数，也不是穴位误差**。

|真实VAL方法|seed11 median/P95 mm|seed23 median/P95 mm|seed37 median/P95 mm|
|---|---:|---:|---:|
|Official＋Txyz|11.226 / 41.604|相同确定性基线|相同确定性基线|
|native 30epoch公制头＋Txyz|49.902 / 130.081|28.933 / 82.232|31.791 / 85.029|
|继续native-only 20epoch＋Txyz|50.237 / 133.278|33.155 / 90.021|33.967 / 91.669|
|加入scan 20epoch＋Txyz|37.937 / 93.116|24.082 / 67.368|22.860 / 62.857|

mixed相对匹配native-only在三个seed均改善。但mixed median均值±样本标准差为**28.293±8.375mm**，P95为**74.447±16.325mm**；Official＋Txyz分别11.226、41.604mm。50mm覆盖率mixed均值78.22%，基线97.07%。mixed的三个seed均不支持替换强基线。

TRAIN也公开：Official＋Txyz median/P95为24.645/80.317mm；mixed三seed为31.771/100.690、24.902/84.455、26.737/89.172mm。[完整逐seed表](summary/PER_SEED_RESULTS.md)包含所有15组raw及＋Txyz结果、TRAIN/VAL、fallback；[逐帧](summary/PAIRED_FRAMES.json)、[逐身份](summary/PAIRED_IDENTITIES.json)与[全部原始结果](real_evaluation)供复查。

Official的232帧Txyz重新计算与历史逐帧一致，Gate PASS。仍使用16,384 anchors、固定A点、6次、trim20%、每轴±0.05m、总范数177.8882018mm上限。Official有11个fallback；mixed三seed为0。三个mixed seed都改善这11帧，但在4个真实VAL身份中，P95分别4/4、4/4、4/4比基线更差。`p001196`各seed median分别多17.52、23.73、13.55mm。**减少fallback不等于整体更准。**[11帧完整审计](summary/OFFICIAL_FALLBACK_AUDIT.json)不删负面记录。

原生合成GT Camera：Official 153.36mm；30epoch RGB-only小头75.25–76.82mm，带Depth公制头32.32–33.63mm。续训mixed为29.62/30.83/30.44mm，匹配native-only为30.00/31.28/30.66mm。Body不变：mixed相机空间对应顶点误差仍95.78–97.46mm，局部Body约100.23mm、去平移约76.24mm；**Camera 30mm不能转述成Mesh 30mm**。

新scan VAL完整person-mask Z误差：native-only median127.51/129.50/145.61mm，mixed62.58/60.84/60.51mm；射线命中率约78–80%→85%，轮廓IoU约0.72–0.74→0.79。完整mask P95仍约2.32m，因为约15%未命中按Z=0计入，相减的是人体约2m深度；它惩罚漏覆盖，不能转述为已命中人体表面有2.32m误差。各文件同时报告与Official共同命中的距离和数量；各模型与Official的交集可能不同，不能把交集分数当固定点集的跨模型排名。[扫描结果](summary/SCAN_SUMMARY.json)

## Depth真正贡献了什么

固定RGB、mask有效性、rays和Body；完整400 native VAL做11种干预，9个checkpoint均保存逐图输出。以mixed seed11为例：正确Depth Camera29.62mm，缺Depth严格回到Official153.36mm；抹去绝对Z约766.73mm，mask/rays固定参考Z约757.27mm。±100mm输入Z偏移导致预测Z平均−95.16/+94.34mm，说明读到了公制数值；只保留绝对深度、抹平局部形状误差38.93mm。局部顺序扰乱约29.63mm，变化很小。

因此当前头主要利用**全局绝对距离与统计量**。它没有逐像素局部对应机制，不能因为梯度非零或深度敏感就宣称学会局部背部几何。错身份/同身份不同姿态Depth也会改变其距离分布；这些是固定RGB下干预，不是正交分解所有信息来源。[完整消融](summary/DEPTH_ABLATION_SUMMARY.json)

## 修复与证据边界

真实评价先发现数米异常，追查到native TRAIN归一化主点两维恒定0.5，旧std floor把真实微小差值放大。修复规则**只由TRAIN min==max确定**：恒定通道归零；验证全部3,600 native TRAIN/VAL输出精确不变。原始checkpoint和错误真实输出另存，未覆盖，未据B选择修复阈值。新结果明确使用`repaired__`名称。[问题说明](NORMALIZATION_FIX.md)

此次真实开发集反复使用、scan VAL仅3身份；不是封存TEST泛化。冻结缓存与新scan Official初始化分别来自旧BF16和2080Ti FP16，精度差异公开记录。这个pilot还改变了RGB表示为1280 backbone池化，不能把与R4/G1的差别全部归因于硬解耦。

## 交付与下一步判断

- [93张实际Mesh对照：12扫描＋81真实](VISUAL_INDEX.md)：真实27帧×3seed，包含历史16帧及全部11个Official fallback。透视z-buffer来自缓存Mesh，不再拟合。B彩色点是独立误差，不是预测Mesh。
- [训练与对照曲线/汇总](summary)、[可执行代码](../../../../research/rgbd_sam3d_mhr/r5_camera_only)、[执行记录](EXECUTION_LEDGER.json)。全部15个best/last、optimizer/RNG与大缓存不上Git。
- [数据索引与SHA](data_manifests)、[实际缓存核验](SAVED_OUTPUT_AUDIT.json)、[匹配续训核验](MATCHED_CONTINUATION_AUDIT.json)、[逐交付文件哈希](FILES_MANIFEST.json)。服务器完整公开包解压于`/raid5/xuhd/rgbd_sam3d/r5_camera_overnight_v1/delivery/`。
- [GPU备份回执](GPU_FINAL_BACKUP_RECEIPT.json)：128,785,261字节，本地和218同SHA。
- [真实评价备份回执](REAL_BACKUP_RECEIPT.json)：6,016,568,299字节，含原始/修复预测、校正Mesh、逐点距离、固定输入/B资产及日志，本地和218同SHA。

工程继续保留Official＋Txyz。研究可以保留“Body固定、Camera单独学习”的方向，但**不直接延长同一个小头训练**：下一轮应优先检验输入全局统计的域偏移与同一Body的逐像素几何约束，既保护正常帧，又测大偏差帧恢复；不据本轮B结果设置切换阈值或挑模型。先把定位机制在现有场景做准，再扩大真实俯卧数据和验证工程穴位。本轮没有证明解剖对应、裸皮肤接触精度或医生穴位传播精度。
