# R4 正式训练前自审

原生前向/反向、断点恢复、物理距离数据、并发吞吐全部 PASS 后启动短跑。此后四组8epoch、G0/G1各三seed×30epoch及评价全部完成；[结束完整性](POST_EXECUTION_INTEGRITY.json)PASS。结构正确与执行完成不代表真实科学优势成立，结论见[最终报告](FINAL_REPORT.md)。

| 检查 | 实际结果 |
|---|---|
| 原 K + RGB crop affine → Camera rays | 四 TRAIN 样本独立重算，最大差0 |
| 原生 MHR cm→m、Y/Z flip | 沿官方 head；不额外转换；保留原顶点拓扑 |
| pred_cam→cam_t→2D keypoints/vertices/crop | 三候选完整训练后独立公式对照，cam_t差0；2D最大3.06e−5px；crop差0 |
| 零初始化保留 Official | 最大顶点差6.56e−7m；cam_t最大1.44e−6m（原缓存前向浮点误差） |
| 训练后缺失 Depth | Official回退最大顶点6.56e−7m、cam_t1.44e−6m |
| Metric / Geometry 有效内部梯度 | 三候选实际16步；camera.metric/token、relative_bias/log_sigma均有限且非零 |
| 四 TRAIN 样本过拟合 | G1 0.4426→0.3496；G2→0.4078；G3→0.3489；不是科研精度结果 |
| SAM/MHR 冻结值 | 前后逐参数hash相同 |
| 旧 R3 checkpoint 回归 | 固定真实帧Camera A native mesh 最大差6.56e−7m |
| TRAIN/VAL/TEST | 原400/50身份；交集空；缓存无TEST；QA不读取B |
| 无效深度 | NaN/空有效图的XYZ有限且零；正常训练输入仍按既有注册合同 |
| Batch16 + fresh-process resume | 4 TRAIN身份/32图、2epochs；模型状态恢复exact，scheduler/RNG相同；续训VAL差5.27e−5mm；不声称继续训练逐位相同 |
| 物理一致相机距离 | 4个既有TRAIN/VAL身份×4距离，固定Mesh/纹理/光照/K，共16图；独立射线点到精确面的QA PASS |
| 吞吐、显存 | 单/双/三路G3实测52.13/67.79/77.06张每秒；三路峰值分配合计约21.42GiB；据此选择三路 |
| 磁盘/资产/备份路径 | Official/MHR实际SHA和缓存/固定B点集manifest核实；既有持久服务器路径可用；新checkpoint完成后逐文件hash并备份，不提前声称完成 |

训练器仍沿用 R3 AdamW、warm-up/cosine、损失和原 backbone BF16 / adapter FP32，不新增未经对照的 AMP 训练策略。原 R3 rotation loss 使用 ZYX，而官方 native 参数和指标为 xyz；这项历史损失选择明确保留，避免与本轮架构改动混淆，不能声称历史损失已纠正。

8 epoch 短跑使用相同100 TRAIN身份与全部50 VAL；充分训练使用原400 TRAIN/50 VAL。真实232帧 Camera B 仅作开发评价；不参与优化、checkpoint选择或采样。短跑通过后按合成精度及物理机制证据选择长跑候选。

证据文件：`qa/NATIVE_SELF_REVIEW_QA.json`、随后生成的 `qa/RESUME_QA.json`、`qa/PHYSICAL_GEOMETRY_QA.json`。

具体修复记录保留在 `qa/QA_REPAIR_RECORD.json`：新物理图 body_pose缓存复算差2.74e−6，顶点0.00054mm、相机0.00012mm；仅该新图的参数容差明确改为1e−5，顶点0.001mm/相机0.002mm合同不变，原R3缓存不重算。恢复检查将“加载时状态exact”与“继续训练逐位相同”区分；续训末轮参数最大差0.0001399、Adam状态5.73e−6，但VAL差仅0.0000527mm。该结果不构成bitwise reproducibility证明。
