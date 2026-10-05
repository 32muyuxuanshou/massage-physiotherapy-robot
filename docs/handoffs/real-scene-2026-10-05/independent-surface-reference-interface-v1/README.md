# 独立体表参考与穴位核验接口 V1

完成了**从独立深度导出参考点、与每位标注者分别比较、保留标注者间差异**的工具。正常路径用解析模拟输入通过；没有真人医生标签、没有新的医学准确率、没有改动现役规则或模型。

读[报告](FINAL_REPORT.md)、[目标定义](spec/TARGET_DEFINITION.json)、[核验流程](VALIDATION_WORKFLOW.md)。代码与可复算示例均在本包。

```powershell
python code/check_observed_label_path.py
python code/export_observed_reference.py --sensor sensor.npz --annotations annotations.json --output references.json
python code/compare_observed_reference.py --prediction prediction.json --reference references.json --output comparison.json
```

第一条从本目录运行，不需服务器或Torch。后两条是未来实际输入的入口；示例格式见`checks/SIMULATED_*.json`和NPZ。全部示例明示模拟，不能放入临床结果表。

此工具不用预测Mesh决定参考点位置。相机输入必须已经统一为对齐彩色的校正pinhole、轴向Z深度；相机或配对采集注册未确认时，只能保留诊断，不能宣称临床毫米精度。
