# prone_rgbd 工程门

用途：在最终女性 canonical SKEL 上建立第一个刚性俯卧、背部朝上、上方相机与床面的单样本 RGB-D 闭环。

- `prone_engineering_fixture.json`：8 个冻结表面绑定；6 个背部、2 个前侧对照，均不是医学穴位。
- `freeze_prone_fixture.py`：只用于一次性构造夹具；验收不得调用它重新选点。
- `prepare_prone_scene.py`：从 canonical Blend 生成独立俯卧快照，不覆盖源模型。
- `export_prone_sample.py`：调用共享 `training_export_core` 导出 RGB/Z-Depth/Mask/labels。
- `verify_prone_contract.py`：在通用独立验证报告之上检查背部可见、前侧遮挡、床面语义和夹具冻结。
- 构建入口：`../../build_prone_rgbd_delivery.py`。

当前姿态只是 canonical SKEL 的刚性旋转，未改变 10 维 shape 或 46 维关节 pose；通过此门不等于医学传播或批量数据生产已验证。
