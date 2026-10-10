# R4.2 Camera / Body 解耦验证

[最终报告](FINAL_REPORT.md)：全232帧双向交换、三个G1训练seed、相同Txyz完成；保持Official Body可降低G1的P95，但VAL仍未超过Official＋Txyz。39系数Camera-only模型实际完成A-only训练、模型冻结与B评价，失败保留，不晋升、不长跑。

- [完整逐帧与聚合](ALL_RESULTS.json)、[逐身份](PER_IDENTITY.md)、[逐帧CSV](PER_FRAME.csv)、[分析/全部失败](ANALYSIS.json)。
- [执行合同](EXECUTION_CONFIG.json)、[先诊断后小验证决定](PRE_PILOT_DECISION.json)、[训练配置](camera_only_pilot/TRAIN_CONFIG.json)、[选模结果](camera_only_pilot/TRAINING_RESULT.json)。
- [完整代码](code)、[重放说明](REPRODUCE.md)、[实际完整性](POST_EXECUTION_INTEGRITY.json)、[投影QA](TORCH_ADAPTER_QA.json)、[全部81张图](visualizations)。
- [缓存网格SHA](CACHE_MESH_MANIFEST.json)、[增量备份](BACKUP_RECEIPT.json)、[执行记录](EXECUTION_LEDGER.json)、[关机回执](SHUTDOWN_RECEIPT.json)、[Git交付文件哈希](FILES_MANIFEST.json)。原始RGB-D、完整网格与小模型权重放私有备份，不进入Git。

原比较资产和全部封存TEST未改。本轮几何和训练在本地CPU完成，无卡AutoDL只做CPU接口QA与11个历史fallback帧RGB导出。交付后暂停，不自动重训。
