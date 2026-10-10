# R5建议：先补任务相关数据，再做匹配预算的Camera-only验证

这是后续方案，**没有启动R5下载/渲染/训练**。本轮原始几何核验未发现量级足以解释p001195错误的计算bug；解耦能减轻Body干扰，但尚无优于Official＋Txyz的最终模型。

## 1. 现有数据缺什么

R3/R4使用500个程序MHR身份、每身份2个不同随机姿态、每姿态4个相机视角，共4000图。全库约1000个posed meshes，不是“全库只有两种姿势”；但每身份只有两帧姿态、分布以近中性关节扰动为主。身份划分400/50/50，TEST未用于本轮。

已有程序颜色条纹、随机光照、2–6mm高斯Depth噪声、1mm量化及约1–3%随机孔洞。**R5不是首次添加纹理或噪声。**它缺的是有代表性的俯卧姿态、床/接触/遮挡、真实衣物外观及传感器相关噪声。依据：[冻结数据配置](../../real-scene-2026-10-09/rgbd-sam3d-r3-multiseed/SYNTHETIC_DATA_MANIFEST.json)与项目 `native_data_r3.py`。

## 2. 四项优先级

|顺序|要补的内容|为什么现在需要|
|---|---|---|
|1 真实俯卧数据资格|无遮挡俯卧RGB-D、可恢复的RGB/Depth标定、床面坐标；独立参考另列|站姿衣物上的Camera B成绩不能代替按摩场景。先建立考试条件，避免一直只优化HuMMan。|
|2 姿态与相机分布|每身份8–16个有效不同姿态，肩臂/腰背/扭转/身体朝向，俯卧、床边裁切、近距离俯视|500身份不能抵消每身份两个近中性姿态的覆盖限制。固定mesh/姿态后再多视角，不把视角变化计成新姿态。|
|3 真实外观|许可清楚的皮肤/衣物纹理、光照、床单背景，含目标裸背与穿衣困难例|程序条纹不能代替RGB模型面对的真实视觉线索。裸背与衣服外表面精度分别报告。|
|4 结构化Depth退化|边缘飞点、成片缺失、距离相关噪声、RGB–Depth残余错位、运动时间差压力测试|随机独立高斯噪声与随机孔洞过于简单；本轮原始手部断裂、遮挡尾部说明需要空间相关退化。|

标定和坐标正确性是所有四项的前提，不能把坐标错误当噪声增强去补偿。相机高度/距离/视角分布与姿态一并更新，单独随机FOV不能替代真实采集几何。

## 3. 具体数据来源与使用边界

|来源|下一步用途|限制/资格要求|
|---|---|---|
|既有HuMMan TRAIN/VAL 232帧|保持A输入、B独立评价的固定回归表；分析公制定位和可见表面|已经消费的开发集，衣物/站姿居多，不称新人物或后背医学精度；TEST继续封存。|
|既有PressurePose真实俯卧20人|任务相关外观与失败压力测试|近似相机合同尚不能当独立毫米级GT；同源空间留出不等于多相机验证。|
|SLP原始RGB/Depth的无遮挡俯卧候选|优先做来源资格小包，不立即当训练真值|作者提供多模态/覆盖条件与访问流程；必须读元数据确认俯卧，恢复内外参、像素域/时间和单位；未获访问就保留等待，不伪造下载。|
|BodyPressure的SLP清理Depth/床坐标及SLP-3Dfits|辅助理解床面和体型；与原始SLP联合核查|填补后的Depth不是原始传感器真值；作者SMPL拟合不是独立扫描GT，也不是MHR同顶点标签。不能由bed transform直接推断RGB–Depth已准确对齐。|
|升级后的原生MHR渲染|提供精确公制Camera、原生Pose/Shape/Scale及顶点监督|必须有物理K/射线、单位、同姿态跨相机、床面接触/遮挡QA；不能把合成模型上的工程点称医生穴位GT。|

可核查来源：[SLP作者仓库](https://github.com/ostadabbas/SLP-Dataset-and-Code)、[BodyPressure作者数据说明](https://github.com/Healthcare-Robotics/BodyPressure)、[SLP-3Dfits作者仓库](https://github.com/pgrady3/SLP-3Dfits)。本轮只核查资料，没有下载上述新人体数据或运行作者模型。来源许可和访问要求按作者原说明办理。

## 4. 首个可执行小验证

先做同R4合成划分与短跑预算的真正final-only Camera-only模型，避免同时改变架构和训练域：

```text
RGB -> frozen Official native Body + final decoder features
                         | Body arrays unchanged
Camera A XYZ / rays / valid -> small MetricCamera head -> final translation
                         | no feedback to Body decoder
                  native projection update -> mesh
                         -> optional frozen Txyz
Camera B ---------------------------------> evaluation only
```

保持Native Body路径，缺Depth精确回到Official；对照Official、Official＋Txyz、G1、G1＋Txyz、Camera-only、Camera-only＋Txyz。先同数据同预算，再分别做新姿态/新外观/新Depth退化消融；不要一次全加后宣称某项起效。GPU需求是小型adapter训练，不是全模型训练；租用/模式切换和正式预算需用户下一阶段授权，本轮未运行。

条件：独立相机median/P95、逐身份、11旧fallback分层、公制Depth扰动与缺失、人体参数完全不变、运行成本。不得只看fallback减少，或只挑seed23；胜出后再安排11/23/37三seed正式训练。

如果Camera-only在匹配预算下仍不及Official＋Txyz，就保留后者工程基线，把论文研究转到有独立证据的局部人体几何/俯卧域改进。先证明学习方法带来它不能提供的价值，不能把“Camera有公制响应”单独当完整论文贡献。
