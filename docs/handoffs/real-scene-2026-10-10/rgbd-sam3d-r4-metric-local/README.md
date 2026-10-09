# R4：公制 Camera 条件与局部 XYZ Attention

本轮是实际实现、自审、短跑筛选和多 seed 训练。原 R3/R3.1 保留；封存 TEST 不读取。状态与实际结果以最终执行 Ledger 为准。

- [架构与接入点](ARCHITECTURE.md)
- [自审](SELF_REVIEW.md)
- [实验合同](../../../../research/rgbd_sam3d_mhr/R4_CONFIG_V1.json)
- [上一轮完整结果](../rgbd-sam3d-r31-diagnosis-pilot/FINAL_REPORT.md)

工程目标仍是 RGB-D 俯卧背部 Mesh，再验证模板工程点/穴位传播。HuMMan 本轮只验证人体几何和深度机制，不证明俯卧皮肤或穴位定位精度。
