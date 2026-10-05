# 俯卧两参考→建议→规则工作台V2

2026-10-05完成。工程链从原20份实际RigidD/input0 Mesh读取，无新SAM、拟合或训练。旧V1及所有旧结果保留。

## 实际能做什么

1. 在原图点击T3、L2及左右方向工程参考；射线与实际Mesh三角面相交，保存全局face/bary/XYZ/normal。
2. 读取上阶段**旧CT训练角色38例**拟合的冻结比例，沿患者3D T3—L2弦及正交化左右方向，生成C7/T5/T9三个**未采纳建议**。
3. 操作者可重新点击定位，也可明确采纳为工程候选；只有这些槽位补齐并输入显式B-cun比例后，才能进入原规则引擎。
4. 输出8个规则候选与完整建议/输入来源，保存本地JSON；修改输入会清除依赖建议，切换患者清空全部输入与比例。

图像输入、未采纳建议、工程采纳建议、规则候选分别显示。比例来源及投影距离可查看，医学/相机/机器人验收仍为false。

## 做到了什么，没证明什么

20个实际Mesh的正常路径验证生成60建议、160规则候选，全部face/bary/normal及单位重算通过。输入使用几何fixture，仅检查接口；没有真人解剖精度成绩。全部20图/4页已实际查看。

fixture中的直线建议到曲面投影距离中位13.17、最大58.23 mm，说明患者表面弯曲与CT X/Z坐标不能直接等同。该距离不是穴位误差，也不能因投影完成就消失；原始目标和投影距离都保留。这是可修改的工程建议工具，不是自动医疗定位。

实际浏览器S104：4次图片点击→3建议→明确工程采纳→输入25 mm占位比例→8规则→HTTP保存成功。保存文件独立重算规则位置误差约2.24e−16 m，并逐点检查建议来源及冻结prior hash。再切换S107确认参考、建议、规则及比例均清空。原照片与浏览器截图仅本地，不重新公开。

**C7骨骼后侧代理不等于C7棘突下凹陷**，T3/L2输入也仍需身份确认。V2保留规则槽位名称用于复核，suggestion明确记录语义不等价；工程采纳不升级为医学确认。

## 与上阶段9.70 mm的关系

上阶段是在TUM CT坐标中的准确T3/L2 oracle和剩余CT代理上考试；此处使用操作者输入及患者3D弦、真正Mesh投影。坐标表示、参考来源、标签语义和患者姿态都不同，**不能把9.70 mm搬到本工作台**。

V2把最简单参考先验接成了真实工程流程。论文后续必须比较这种基线，研究联合几何与解剖对应；不是把GUI或三点插值当创新。

## 文件与运行

服务入口[code/serve_workbench.py](code/serve_workbench.py)，[页面](site/index.html)，[20份结果](ENGINEERING_COMPLETION_RESULTS.json)，[实际GUI保存重算](BROWSER_REVIEW_CHECK.json)，[冻结来源](SOURCE_IDENTITY.json)，[全量图](montages/)。

本地入口`http://127.0.0.1:8867/index.html`。无原RGB的公开资产可替代private assets运行；原始实际Mesh来自V1。Python调用：

```powershell
python code/serve_workbench.py --site site --assets ../prone-reference-rule-workbench-v1/site --reviews local_reviews --port 8867
```

服务器代码：`/raid5/xuhd/datasets/prone_reference_rule_workbench_v2_20261005/code`，公开页面/几何资产可运行同一服务，未对外暴露监听。
