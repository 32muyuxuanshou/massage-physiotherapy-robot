# R4：公制 Camera 条件与局部 XYZ Attention

**实际完成：**四组8轮短跑；G0/G1各三个seed×30轮；全部232帧独立Camera B、400图合成VAL、Depth消融、16图物理距离探针及保存Mesh的组件交换。原 R3/R3.1 保留；封存 TEST 未读取。

G1合成PVE86.95→59.55mm、Camera66.47→27.07mm；物理距离响应斜率0.488→1.013。真实VAL平均median28.59→22.83mm，但P95 68.19→70.32mm且p001196仍失败；未击败Official+Txyz的11.23/41.60mm。保留G1研究候选，不升级最终工程模型。

- [最终报告与下一步结论](FINAL_REPORT.md)
- [全部seed、Best/Last指标及曲线](summary/R4_SUMMARY.json)
- [逐人对照](PER_IDENTITY_REVIEW.md) · [全部配对帧与Depth机制](FINAL_DIAGNOSTICS.json)
- [全部短跑/正式可视化](VISUAL_INDEX.md)
- [架构与接入点](ARCHITECTURE.md)
- [自审](SELF_REVIEW.md)
- [结束完整性](POST_EXECUTION_INTEGRITY.json) · [checkpoint SHA](CHECKPOINT_MANIFEST.json)
- [执行Ledger](EXECUTION_LEDGER.json) · [正式备份回执](FORMAL_BACKUP_RECEIPT.json)
- [三个可恢复档案及范围](BACKUP_INDEX.md) · [实际评价器源码](evaluation_dependencies/surface_metrics.py)
- [实验合同](../../../../research/rgbd_sam3d_mhr/R4_CONFIG_V1.json)
- [上一轮完整结果](../rgbd-sam3d-r31-diagnosis-pilot/FINAL_REPORT.md)

工程目标仍是 RGB-D 俯卧背部 Mesh，再验证模板工程点/穴位传播。HuMMan 本轮只验证人体几何和深度机制，不证明俯卧皮肤或穴位定位精度。
