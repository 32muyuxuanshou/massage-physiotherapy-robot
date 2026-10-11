# 完整 R5 与旧模型：同数据三种子对照

**状态：执行中。** 2026-10-11 用户批准后开始。本文件不宣称训练完成或 R5 已胜出。

## 目标与方法

冻结 Official 的 RGB 人体分支；新 R5 用公制点集做粗定位，再用固定表面查询、可见深度/RGB 对应和法线方向约束做一次细修正。新模型直接输出 Camera，不外挂 Txyz，不改变原生 MHR Body。

七组：RGB-only、Spatial Residual、Cross-Attention/G0、G1、历史 pooled Camera MLP、R5 coarse、完整 R5。统一数据、曝光、学习率筛选和三个正式种子 11/23/37，共21个正式训练单元。

Official 与 Official＋历史 Cheap Txyz 是固定工程基线；没有训练种子。Txyz 只用于 Official 基线，不进入新模型主结果。

## 数据与边界

|数据|训练|验证/评价|标签含义|
|---|---:|---:|---|
|native MHR|400身份/3200图|50身份/400图|对应顶点、MHR参数、真实 Camera|
|HuMMan textured scan 重渲染|9身份/2304图|3身份/768图|可见穿衣扫描表面、轴向Z和轮廓；没有 MHR root/Pose/Shape GT|
|真实 HuMMan|不作训练|已消费 TRAIN18人/192帧、VAL4人/40帧分别评价|A输入，固定B的2048点独立点到三角面；没有 MHR 对应顶点真值|

native TEST50身份/400图封存。真实两部分都是开发证据，不称全新泛化。保留全部扫描截断图。没有新增穴位训练或临床精度判断。

## 实施细节与计划的明确差异

- Batch实测2/8/16后选择16，4进程并发；不是按显存猜测。旧模型约6.3GB/进程，完整R5约0.9GB。
- native30轮＋混合20轮；混合阶段每轮3200 native和2304 scan均完整无放回遍历；扫描相机分组按每asset等权，保留全部视图。
- 同样比较 `1e-4/3e-4`，筛选seed7、5轮；依据native VAL对应Camera-space顶点误差选择。完整R5的fine前10轮预热，因此五轮LR筛选只评价粗阶段，不用它判定fine价值。
- 当前深度增强是原RGB像素格的 stride1/2/3 采样、2%随机空洞、额外0/1/3mm噪声；保留K/rays和clean标签。**它是零基线受控采样实验，还不是已标定的完整Kinect噪声模拟器。**不得把它包装成真实设备建模。
- 旧native十项损失保留形式和权重；公共深度/轮廓改为逐图归一化。整体旋转按资产实际XYZ解释，修正历史ZYX实现；历史代码不覆盖。
- scan弱监督权重以固定TRAIN样本的Camera输出梯度校准，所有架构共用；不用VAL或Camera B选权重。
- fine：2048输入点、256固定face/bary查询，自身可见深度筛选；仅输出平移。法线矩阵弱方向衰减，不新增learned uncertainty，也不整向量清零。
- 训练使用原生空间backbone缓存；scan必须重新导出完整空间缓存，不能以1280维pooled向量替代旧融合输入。

## 已验证与尚未完成

已完成七组前向/反向/参数更新；同batch零初始化复现Official；三Camera-only组更新后Body全部保持不变，缺Depth返回Official位置。斜三角形透视Z解析检查、平面/曲面方向检查和fine有效梯度通过。

14/14个LR筛选已完成，七组均选择`3e-4`，正式队列已启动。首批RGB-only三seed和Residual seed11已超过10轮；这不是最终模型排名。完整3072份扫描空间缓存已生成并无损压缩约36GB→9GB，全部文件通过CRC/大小一致性和实际tensor读取检查。

Official的400 native、768 scan、232 real预测已保存。历史Official＋Txyz在相同232帧逐帧重现通过：真实VAL 30.586→11.226mm，TRAIN 53.971→24.645mm（固定Camera B点到三角面、身份等权）。这些固定基线只用于比较，不能代表新R5效果。

新R5和RGB-only的实际输出消融流程QA通过（使用LR筛选seed7，不冒充正式三seed结果）；透视图从实际缓存生成。原生/真实输入备份12.06GB、扫描源备份4.14GB已经存入E盘与218并逐包核对SHA。首批第5/10轮checkpoint的best/last也已独立备份。完整证据见[自审](SELF_AUDIT.md)、[实际QA及运行快照](review)、[三个数据清单](manifests)和[学习率曲线](lr_screen_curves)。

待完成：21个正式50轮训练、最佳/末轮评价、正式Depth消融、三份互不混算的数据集表、逐人失败图和完整最终备份回执。尚不能判断哪个模型效果最好。程序已串联训练→冻结best/last评价→Camera B→消融→报告/全量图→后验SHA检查；完成后执行异机全包备份与Git交付。

coarse/full各自独立跑50轮，不复用预热checkpoint；相同seed使用相同数据顺序。并发GPU存在微小数值差异，不宣称其前10轮训练状态严格相同。

原始RGB-D推理入口`infer_registered.py`也已实际验证完整R5和RGB-only：直接读取RGB、注册轴向Depth、原K、bbox/person mask，不使用backbone缓存；主推理只跑一次SAM。以固定扫描VAL样本对照缓存，Body/Camera/参数数值一致。此项使用短筛checkpoint作流水线QA，不是正式模型效果结论。

## 运行位置与复现

- 计算：已在线AutoDL `connect.cqa1.seetacloud.com:39846`，RTX6000D；本轮未开新付费实例。
- 执行根：`/root/autodl-tmp/rgbd_sam3d/runs/r5_complete_comparison_v1`。
- Python：`/root/autodl-tmp/rgbd_sam3d/envs/rgbd/bin/python`。
- 官方源是导出的源码，没有`.git`元数据；以实际Python源码SHA和checkpoint/MHR SHA记录，不能伪造repo commit。
- 独立备份：`172.18.6.218:436`的 `/raid5/xuhd/rgbd_sam3d/r5_complete_comparison_v1`，以及本地 `E:/项目-按摩理疗机器人/output/r5_complete_comparison_v1`。218有8×2080Ti，但当前缺原渲染CUDA编译环境，先承担备份与CPU工作。

公开代码：[r5_complete](../../../../research/rgbd_sam3d_mhr/r5_complete)。私有权重、原图和大Mesh包不进Git；密码不进交付。

```bash
python prepare_pipeline.py --root <execution_root>
python run_queue.py --root <execution_root> --workers 4
python run_postprocess.py --root <execution_root> --workers 4 --cpu-workers 8
```

执行前要求 `PREFLIGHT.json` PASS；正式队列等待完整scan manifest和弱监督权重冻结。评价脚本单独读取冻结checkpoint，raw新模型不做Txyz。服务器不自动关机。
