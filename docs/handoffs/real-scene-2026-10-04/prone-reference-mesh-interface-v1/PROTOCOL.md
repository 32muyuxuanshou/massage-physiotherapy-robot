# PRONE_REFERENCE_MESH_INTERFACE_V1

2026-10-04；俯卧曲线结果尚未产生。

目标：将已运行的XYZ几何参考提取器接入现有俯卧RGB-D后背ROI，并输出同一MHR表面的face_id/barycentric/xyz/normal工程接口。不是训练或医学定位验收。

沿用原20人、开发4/已消费测试角色16、seeds0/1/2、6 cm空间块划分。每seed只把原train_idx与posterior_point_mask交集中的点传给提取器。原heldout_idx不参与计算；冻结RGB ROI为共享上游输入。相机维持历史近似pinhole，衣物观测不是皮肤GT。

三提取法及全部参数与BACK_REFERENCE_EXTRACTION_V1完全相同，不改支持半径/平滑/DP阈值。若空间块缺失使DP没有连续支持路径，记录失败，不补深度、不放宽参数、不用另一条线冒充该方法。BOUNDARY_CENTER若回绑距离大也直接报告，不隐藏支持缺口。

全部180方法/人物/seed记录先保存，之后接缓存Official、Rigid、Rigid+D三个Mesh分支；不复用T+Pose参数、不重拟合网格。原分支的optimization_point_idx必须仍属于原train_idx。后背face mask沿用2152面。

每人物在所有成功曲线的共同native-Y域内预先按0.1…0.9九个分位取同Y工程探针。不是C7/L5/T3/B-cun/穴位，曲线端点不是解剖端点。将每seed曲线插值得到九点，准确最近三角面绑定到三个缓存Mesh，保存face/bary/xyz/normal、投影距离及原查询。正常接口由这些缓存直接导出，不再拟合。相同九个Y位置用来评价三seed稳定性；缺seed时不宣称三seed稳定。

报告完整度、源点回绑距离、参考位置三seed最大两两跨度、对应Mesh位置跨度、查询→表面距离、bary重建误差、面法向。按人物等权汇总并分别保留4开发/16已消费测试角色。数值是工程稳定性/接口几何，不是穴位准确率；不将低投影距离当定位成功。

可视化：全部20人物曲线/点位图；原RGB叠加只放本地/服务器私有目录。无原RGB/原全点云/授权权重入Git。端到端是“既有RGB ROI和离线缓存→深度曲线→缓存Mesh绑定→工程目标接口”，未验收机器人变换或治疗接触。
