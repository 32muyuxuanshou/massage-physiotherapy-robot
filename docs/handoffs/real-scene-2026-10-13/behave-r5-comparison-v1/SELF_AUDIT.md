# 本轮自审

已通过的范围是无卡准备，不是 GPU 正式路径或模型科学结论。

|项目|证据/状态|
|---|---|
|官方 TEST 与采样|90 序列 / 270 帧，固定完整文件时间戳 25/50/75%；模型结果未产生|
|旧数据使用说明|3 个已消费身份，25 帧历史重合；不称全新人物|
|原始下载|HTTP direct，不经过 FlClash；原 ZIP CRC 和文件 SHA，断线续传复用已校验文件|
|参考与坐标|真实 3 帧 / 12 cameras，与官方 KinectTransform 直接导入数值对比及实际 sensor→RGB 重投影通过|
|标定检查边界|代码数值/像素一致性及 broad cloud sanity；不是物理毫米级标定认证|
|原生参考|6,890 顶点拟合 SMPL-H；process=False，不重新拟合、重新排序或冒充裸露皮肤真值|
|统一新输入|显式去畸变，K 不改变；与旧 distorted-RGB 口径差异写明|
|原生输出|GPU 代码保存 MHR/Camera/vertices；只平移分支须 Body exact equal；实际 forward 尚待 GPU|
|深度隔离|K0 作为输入和 Txyz 拟合，拟合 reference 与 K1/K2/K3 分文件，仅评价脚本打开|
|完整输入实际核验|270 帧 / 810 个文件，全部实际 SHA、shape 和 A-only 输入检查通过；每个 B/C/D 均 2,048 点|
|Txyz|直接复用 R4.1 AST 加载的 R3.1 函数和原 16,384-anchor；6 次迭代及原 bound/fallback 不改|
|权重|24 个 Best/Last 与三 seed 固定，实际 SHA 与本地原备份及 218 回执吻合，不按 BEHAVE 选择|
|聚合|在结果前编写；30 个 cell 全覆盖才发布完整汇总；去平移不变量和固定帧集检查|
|代码验证|语法通过；3 个正常路径检查通过。未把语法通过称作 GPU forward 已验证|
|失败可视化/HTML|未完成，正式推理后的交付，不预先宣称完成|

R5 输入仍用同样的 Official Body，不允许通过 B/reference 重新拟合。G1 的姿态/形状变化须用去平移 PVE 和可见表面证据分开解释。M³ 论文值只是参考，不拿不同对齐、不同 mask 处理或不同汇总宣称严格超越。
