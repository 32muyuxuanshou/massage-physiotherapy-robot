# R4.2 原始传感器与几何评价补充交付

**实际完成：**232帧发布标定核验、27帧/54视图原始Depth重建、四例/八视图视频顺序解码核验、378条A射线诊断、64个独立B距离控制、16张新图。没有新SAM推理/训练、没有B拟合、没有读TEST。

- [最终结论](FINAL_REPORT.md)：p001195大偏差在A已存在；解耦减轻尾部但尚未胜出；物理配准/同步局限单独保留。
- [完整结果](GEOMETRY_AUDIT.json)、[原始传感器QA](RAW_SENSOR_QA.json)、[378条表](A_DEPTH_DIAGNOSTICS.csv)、[四例全部seed表](CASE_TABLE.md)。
- [16张新图](visualizations/README.md)、[上一轮232帧/81图/CPU小模型](../rgbd-sam3d-r42-camera-body-decoupling/README.md)。
- [R5数据升级建议](R5_DATA_UPGRADE.md)：是后续计划，尚未执行。
- [代码与复现](REPRODUCE.md)、[执行记录](EXECUTION_LEDGER.json)、[自审](POST_EXECUTION_INTEGRITY.json)、[备份](BACKUP_RECEIPT.json)、[服务器保持运行](SERVER_STATUS_RECEIPT.json)。

原始观察与Native缓存不入Git，完整增量在本地私有包和218持久服务器。旧R4.1/R4.2依赖包的SHA及恢复路径见备份回执。研究核验完成后暂停，没有自动启动R5或付费GPU；按用户最新指令不关机，原AutoDL保留无卡模式。
