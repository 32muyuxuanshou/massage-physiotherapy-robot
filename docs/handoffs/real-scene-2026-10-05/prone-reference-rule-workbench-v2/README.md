# 两参考工程工作台V2

[最终报告](FINAL_REPORT.md)、[20人60建议/160规则](ENGINEERING_COMPLETION_RESULTS.json)、[浏览器实际保存与复算](BROWSER_REVIEW_CHECK.json)、[冻结旧规则及先验](SOURCE_IDENTITY.json)。

- 不重复存储20原Mesh，从[原V1资产](../prone-reference-rule-workbench-v1/site)读取；私有RGB版本在本地output。
- 三个待复核建议来自CT比例先验，经患者3D弦/左右参考与实际三角面投影，不等于棘突凹陷/医学穴位。
- [全量图1](montages/all_1.jpg)、[图2](montages/all_2.jpg)、[图3](montages/all_3.jpg)、[图4](montages/all_4.jpg)已逐页查看，均为几何占位输入。
- 原规则代码字节不变，只有建议模块/显式采纳流程新增。原报告和原结果不覆盖。
- 正常路径验证：`python code/check_completion.py`；全量缓存图：`python code/make_figures.py`。
- `code/frozen_reference_prior.json`按TUM/TotalSegmentator来源保留出处；其参数从旧TotalSegmentator训练角色计算，不使用TUM考试点拟合。
