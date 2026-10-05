# 参考约束的表面/解剖坐标场 V2

[事实报告](FINAL_REPORT.md) · [方法与论文定位](METHOD_AND_PAPER.md) · [预注册配置](TRAINING_SPEC_V2.json) · [代码](code)

这轮完成了新模型结构和真实Mesh接口，**没有完成大规模训练或医学准确率验证**。保留V1基础、比例先验和历史几何基线。V2修正方法设计，不改历史SAM/Txyz/O2实验。

实际完成：四个旧TRAIN来源的三模型正常训练路径；正式评价器在这四例的缓存重算；20个既有俯卧Mesh产生60个参考建议、160个规则候选、220个面绑定重算；20张完整图均检查。

关键文件：

- `checks/MODEL_PATH_RESULT.json`：三模型各40步、参考约束和刚体/单位转换检查。
- `checks/SOURCE_EVAL_PATH_RESULT.json`：四TRAIN例的正式评价器检查，不是考试准确率。
- `checks/PATIENT_PATH_RESULT.json`、`checks/PATIENT_CACHE_REPLAY.json`：20实际Mesh的接口及独立缓存重算。
- `patient_paths/`：全部输出、坐标场、顶点/面及使用的点索引。
- `figures/montage_01.jpg`～`montage_04.jpg`：全量，不按效果筛选。
- `checks/SERVER_RECHECK.json`：服务器未返回SSH握手的实际记录。

结构检查命令从本目录运行，需PyTorch和项目已安装的NumPy/Matplotlib；本轮使用任务独立的Windows PyTorch 2.4.1+cpu目录，没有更换服务器环境：

```powershell
python code/check_and_train_path.py
python code/check_source_eval.py
python code/check_patient_path.py
```

前两项只用四个已消费的TRAIN例。第三项使用上一步结构权重，观察点从Mesh采样，**不是新RGB-D实验**。

服务器恢复后：先核实V3作者MD5和成人来源处理，再将本包代码同步到新目录`/raid5/xuhd/datasets/reference_anchored_surface_field_v2_20261005/code`。来源目录沿用`/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005/v3_dataset`。满足200合格TRAIN/20开发及完整来源处理后，执行`run_source_grid.py`：GPU0/1/2并发三方法，每方法三初始化，60轮；正式测试只读预冻结作者adult-test角色。

**不要把V1/V2两套完整训练都默认启动。** 本轮方法学习后的现役候选为V2，V1保留研究起点。先验、软参考、硬参考及联合射线分支形成V2对照；先看它能否击败比例先验，再决定是否扩大模型。
