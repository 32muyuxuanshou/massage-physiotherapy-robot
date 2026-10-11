# R5 执行自审

2026-10-11。这是代码与实际运行的自审，不冒充独立第三方审稿。当前结论：**实现和训练主链可以继续；完整科学实验尚未完成。**

|检查|实际证据|状态|
|---|---|---|
|七组结构与实际参数更新|PREFLIGHT七组真实GPU前向/反向，2次更新|PASS|
|零初始化复现Official|同batch比较；历史单图缓存的微小GEMM差异另记|PASS|
|R5的Body硬隔离|所有12个Body字段不变；深度缺失回到Official Camera|PASS|
|fine不是摆设|fine末层梯度0.106658；两样本134/72个可见query|PASS，仅主路径QA，不是优势结论|
|平面/曲面方向处理|平面切向抑制、曲面保留；原生透视解析例|PASS|
|G0合并为Cross-Attention|复制相同权重、非零gate和输出权重，实际空间特征数值比较|PASS|
|RGB-only不读取Depth|非零gate的fusion输入Depth/mask/rays全部更换，输出相同；完整Decoder消融保留实际舍入响应|PASS|
|原始RGB-D端到端入口|固定扫描VAL，full/RGB-only直接读取原图与注册Depth，与缓存Body/Camera/参数比较|PASS，使用短筛checkpoint作代码QA|
|native身份划分|400 TRAIN/50 VAL；TEST不在缓存manifest|PASS|
|扫描标签边界|完整空间cache；没有伪造MHR root/人体参数真值|PASS|
|扫描输入与弱监督|3072全缓存；固定TRAIN梯度校准，共享权重|PASS|
|扫描弱监督权重|axial-Z=1.0664188982，silhouette=4.4302755108|已冻结|
|历史工程基线|232帧raw translation/fallback/独立B评价逐帧核对|PASS|
|学习率对照|14单元均完成，七组选3e-4；full在fine预热阶段|PASS，仅有限范围短筛|
|备份|数据16.20GB及首批第5/10轮checkpoint，E盘＋218实际SHA一致|PASS，后续持续复制|
|三seed正式训练/最佳末轮/真实评价|21单元运行中，后处理等待训练冻结|尚未完成|
|全量最终图与后验完整性|代码已串联；将生成4896份best可视化和60200份best/last预测|尚未完成，不以计划数量充当实际数量|

## 已修的实际问题

- 早期队列文件`queue.py`遮蔽Python标准库，已改名`run_queue.py`，实际训练已通过。
- AutoDL缺历史Camera B/Txyz评价资产包，已从本地传入原包并核对SHA；232帧复现已通过。原失败日志保留，当前ledger没有活动失败。
- 旧模型输出的辅助字段可能为`None`，评价/消融现在只读取注册Body与Camera字段。
- 完整Decoder重复相同RGB也出现约0.00023mm的GPU舍入响应。RGB-only先做Depth无关fusion的严格相等检查，再以0.005mm数值容差检查完整路径；实际响应不清零、不包装成Depth利用证据。

以上修复没有修改已启动训练的core、数据划分、损失或配置。训练checkpoint记录实际core与清单SHA，结束后再次读取核对。

## 结果解读的边界

1. pooled/coarse/full的新增变化只能来自Camera平移，不会修好Official已有的Pose/Shape。真实数据没有原生MHR对应参数真值。
2. native顶点是对应点L2；scan是透视轴向Z和轮廓；real是独立B传感器点到三角面。三个分数不合并。
3. scan全mask未命中计Z=0惩罚，米级P95可能来自未命中，不能叫米级已命中表面误差。另保留命中率、自身命中及与Official配对共同命中。
4. 当前噪声/空洞是受控零基线像素采样，未声称完整真实Kinect模拟。扫描穿衣人物也不等于俯卧裸背。
5. 真实TRAIN/VAL均已消费，仅作开发评价；B不拟合、不选LR/损失/架构。native TEST仍封存。
6. 50轮是统一预算，不自动等于收敛。结论必须结合末轮趋势、三个seed、逐人P95与失败图；没有证据时不宣布R5胜出或可部署。
