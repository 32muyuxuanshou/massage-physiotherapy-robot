# 俯卧参考→规则→Mesh工作台 V1

已完成实际工程链：选择20人之一 → 原图点击7个参考 → 真实缓存三角面绑定 → 显式填写个体B-cun比例/来源 → 生成8个规则候选 → 保存可复算JSON。没有新的SAM推理、拟合或训练。

## 实际结果

- 20份既有RigidD/input0网格，每份使用2152个候选后背面；原全身Mesh哈希与既有来源核验。
- 20人几何流程fixture全部通过，160个规则候选输出，XYZ/face/barycentric/normal及米→毫米换算独立重算通过。
- S104实际浏览器点击7点，真实调用HTTP规则接口生成8候选、保存复核文件，独立重构最大误差2.29×10^-16 m。
- 切换S104→S107时清除参考/规则；检查发现个体比例残留，已局部修正。实际S107→S165复查确认参考、比例、来源全部清空。
- 规则核心与9月21日rule_engine.py逐字节一致，不在本轮另改规则或假定骨度比例。

## 使用

本地含原图版：

```powershell
python -X utf8 docs/handoffs/real-scene-2026-10-05/prone-reference-rule-workbench-v1/code/serve_workbench.py --site output/prone_reference_rule_workbench_v1/site --reviews output/prone_reference_rule_workbench_v1/private_reviews --port 8866
```

浏览器打开 http://127.0.0.1:8866/index.html 。先记录C7_T1/T3/T5/T9/L2及患者左右方向参考，再填写1 B-cun的mm值和实测/工程占位依据。当前测试比例25mm和GUI_FIXTURE_NOT_MEDICAL只用于演示，不是患者测量值。

Git公共版本只包含预测几何、不含原始RGB；原图录入使用上述本地/服务器private版本。server源地址见SOURCE_IDENTITY.json。公共几何版可旋转查看缓存，不能在缺少原图时声称完成图像参考复核。

## 输出和边界

输出实际患者XYZ(m)、原MHR全局face ID、重心坐标、surface normal、投影距离mm、输入参考及来源、个体比例来源和Mesh SHA。参考由输入者提供，算法没有从骨质中心或人体bbox假装恢复棘突凹陷。当前规则的横向欧氏偏移＋最近面投影仍是工程规则实现，不等同完整临床骨度分寸验收。

8个候选为GV14、左右BL13/BL15/BL18及GV4；沿用既有工程配置。GV14/GV4和椎体水平的医学语义需要以后实际参考确认，成功绑定只说明几何数据流可用。WHO/GB规则证据及历史医学语义限制保留原9月21日EVIDENCE_MATRIX，不借用CT代理作为它们的真值。

参考fixture并未医学验证，原PressurePose是穿衣俯卧，近似相机合同；2152面也是工程候选区域，边缘可含邻近身体区域。因此medical_validated/calibration_validated/robot_release均false。不报告穴位准确率，不下发治疗。

## 下一步

工程继续把“参考质量→规则结果”的关系量化，明确哪种输入错误会影响左右、椎体水平和旁开距离；论文主线应研究几何贴合与解剖对应联合恢复，并以真实参考证据检验。CT小模型不再反复调试。
