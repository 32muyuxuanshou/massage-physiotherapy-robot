# 俯卧 Mesh 点位工作台：工程闭环完成，学习模型不放行

已完成20人全部对照、600实际绑定/4800 ENG点、120 Mesh面缓存与离线人工复核工作台。没有新训练、SAM推理或Mesh拟合。默认仍使用同拓扑传播。

## 当前实际结果

原20人、4开发/16已消费测试角色、三个训练点空间划分、Rigid/RigidD缓存不变。位置参考BODY网络来自上一学习阶段三个开发选checkpoint；与原Topology及相同patch坐标NN比较。

16人RigidD，输入划分跨度先每模型计算、再模型平均、最后受试者中位：

| 方法 | 点位置跨度 mm | 到预测面投影距离 mm | 与Topo位置差 mm |
|---|---:|---:|---:|
| 默认Topo | 7.39 | 0.00 | 0.00 |
| BODY_CHART_NN | 20.75 | 2.44 | 112.28 |
| BODY_QUERY | 19.33 | 1.77 | 143.02 |

新学习点依然明显偏移，不能以“贴面1.77mm”宣称定位准确。本轮实际视觉复查S104时，学习点的纵向范围还明显收缩；全20人方法/种子图全部保留。网络不升级，固定拓扑也仅是工程基线，没有真人解剖精度参照。

600实际绑定与120原Mesh核查3000项PASS，源资产未变；Git中的600目标及120相关面缓存可用纯NumPy独立重算，同样3000检查PASS。没有重新拟合来生成漂亮图。

## 可直接使用的工作台

- 原图上显示实际缓存Mesh和ENG点，可切换Topo/坐标NN/三个BODY初始化。
- 右侧旋转查看同一后背候选区域；它是正交3D，不冒充RGB透视图。区域沿用历史候选面，不是新医学分区资格证明。
- 在原图点击参考位置，用真实透视射线与当前后背三角面求交，保存xyz、face、bary、normal、原像素与Mesh hash。
- 点击没有命中时不补点。人工标记不是自动医学真值；后续医生可以用同一接口记录独立参照。
- 内部浏览器Blob下载未实际落盘；已改为本地HTTP服务明确写入private_reviews，再显示真实文件路径。静态file版本仍发起下载请求并要求在浏览器下载列表确认。

实际浏览器已验证：切换方法、点击背部、写入复核JSON、重新读取并从该面/权重重建位置（约3.1e-17m数值误差）。这是绑定计算验证，不是毫米临床精度。验证点名TEST_REF_NOT_MEDICAL，不进入医学标签。8个Topo实际射线与非平面解析三角形检查通过，见GUI_RAY_CHECK/BROWSER_REVIEW_CHECK。

## 文件入口

[完整结果](RESULTS.json)、[逐人CSV](PER_SUBJECT_RESULTS.csv)、[全20图](figures)、[600绑定](targets)、[120重算面缓存](mesh_reviews)、[40默认/实验JSON](exports)、[缓存核查](CACHE_REPLAY.json)、[本地独立重算](DELIVERY_REPLAY.json)。

[公共几何工作台](site/public_workbench.html)不含原患者RGB。真实图像版本仅本地`output/prone_body_query_workbench_v1/site/workbench.html`及服务器site/workbench.html，公共Git不重分发原图。

本地启动：`python code/serve_workbench.py --site E:/项目-按摩理疗机器人/output/prone_body_query_workbench_v1/site --reviews E:/项目-按摩理疗机器人/output/prone_body_query_workbench_v1/private_reviews --port 8865`，浏览器打开`http://127.0.0.1:8865/workbench.html`。当前已在内部浏览器打开。服务仅本机可访问，保存仅新增本地复核文件，不修改源网格/atlas。

服务器 `/raid5/xuhd/datasets/prone_body_query_workbench_v1_20261005`，源码run_workbench/analyze_workbench/build_workbench/serve_workbench。当前相机仍重建近似合同，工程点不等于穴位，机器人不放行。

## 本阶段后的决定

停止继续调这一类纯局部几何匹配。工程保留表面拟合＋Topology＋可记录独立参考的工作台。论文方法下一步审视能够提供解剖/身体结构的监督与模型，而不是靠更复杂的局部特征掩盖17cm错位；独立俯卧裸背/医学参考仍需补齐。
