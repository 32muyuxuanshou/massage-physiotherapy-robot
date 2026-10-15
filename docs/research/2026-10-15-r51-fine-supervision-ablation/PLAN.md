# 固定Coarse的Fine监督消融 R5.1

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run / controlled code experiment
- Origin Date: 2026-10-15 Asia/Shanghai
- Verification Status: COMPLETE；12组有限续训、10542条独立评价与实际资产SHA核验完成，见正式交付。
- Version Label: r51_fine_supervision_ablation_v1

## 对建议的裁决

可以执行，修正四处定义：E0是固定Coarse后的Fine继续训练基线；同seed四组共享Coarse和Query，不要求不同原seed有相同Coarse；E1实际拆成0.5与0两组，共4组×3seed=12单元；E2先用简单L2，不把未经证明的10–15mm当传感器噪声阈值。

## 固定范围

只使用218现有授权资源，不启动付费GPU或关闭服务器。原Full Last三seed为配对初始化；仅训练rgb_local、local、fine_head，身体和Coarse不训练。训练预算6轮、相同AdamW/lr1e-4；不与原50轮联合训练混称同一实验。

已有诊断缓存不足以训练：从已核验12.06GB历史缓存包恢复所需Native TRAIN，保留原VAL及划分。最初检查发现该包不含Scan，原MISSING回执保留；随后由AutoDL直接SFTP补齐1536份Scan TRAIN/VAL缓存并核验实际SHA，见DATA_READY.json。Native预先按身份哈希选64人、全部8姿态/视角，共512张；Scan按asset×camera-group比例及哈希选768张，完整Native400/Scan768 VAL不变。子集只为有限机制筛查，不称正式充分训练。

## 单变量矩阵与梯度

E0最终Camera权重2；E1_half为0.5；E1_zero为0；E2_l2保持E0再加公制步长L2。其余loss、数据、初始化和顺序一致。L2系数只用TRAIN32 Native+32 Scan原seed11最后层梯度标定成基线梯度中位数的10%，在任何新VAL/B结果前写定。Native Camera梯度、Z/轮廓梯度、合成向量范数及余弦分别记账；Scan没有伪Camera GT。

固定Coarse/Query后允许Fine的RGB投影和MLP学习。若预采样1280维RGB特征替代先1×1投影再采样，必须先验证观察点上的输出及参数梯度等价；不能偷偷冻结RGB投影或降低数据精度。

## 选模与评价

每轮保留权重，在0/2/4/6轮评价。旧规则Native身份等权vertex_camera_mm；联合规则为Native/Scan分别相对同seed初值的full-mask median等权平均，要求两个域命中率和IoU都不低于初值1个百分点。epoch0可选，平分取早。Scan按身份→asset→camera-group→frame聚合，各层等权。共同命中只作支持，漏命中仍进入全mask。

所有单元选模记录冻结后，才运行真实HuMMan232和BEHAVE270。复用历史点集、坐标与严格三角面评价；保留旧负收益名单，统计救回/新增坏帧及P95。Native Camera与表面负收益分开。新模型不加Txyz；不读封存TEST、不用真实Camera B选lambda/epoch/结构。真实数据已经消费，只称开发验证。

## 验证与结束条件

先通过缓存来源SHA、固定Coarse与Body、四组初始相等、非Fine无梯度、E0损失与旧数学式一致、Query预采样输出/梯度等价及一更新主路径，再运行12单元。先用实际吞吐估时。完整保存配置、数据索引、每轮权重、梯度、两个Best及Last、逐域/逐人结果、图和备份SHA。

只依据预设预算完成本轮，不自动拼E1+E2、不追加轮次。结论允许无效或退化，不承诺追平Txyz、证明因果唯一性或论文接受。

## 实际结果

四组×三seed均完成。Camera权重0.5相对同预算E0的HuMMan VAL median只改善0.044mm；完全移除Camera监督虽改善Native，却使真实VAL三seed全部退化；简单L2无稳定收益。按计划结束，不追加组合或训练。完整结果：[正式交付](../../handoffs/real-scene-2026-10-15/r51-fine-supervision-ablation-v1/README.md)。
