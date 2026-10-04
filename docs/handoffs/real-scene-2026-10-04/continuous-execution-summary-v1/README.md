# 连续执行交付索引

2026-10-04，用户授权三小时内连续推进、每段提交后继续。开始时间12:23:09（Asia/Shanghai），窗口终点15:23:09。三项实际实验完成并分别推送；第四项曲线学习原型写好，但服务器既有存储不可见，训练尚未发起。[机器可读执行记录](EXECUTION_LEDGER.json)。

## 本轮实际推进

| 顺序/提交时间 | 工作 | 实际产物与结论 | 提交 |
|---|---|---|---|
| 1 / 12:38 | 真实XYZ参考提取 | 30扫描、90曲线、30完整图；沟槽与作者画线差异中位3.69 mm。非俯卧、非医学GT。 | `b885c7ad0e1de6a06a4067e9cbca8476dcdae756` |
| 2 / 12:52 | 俯卧参考→Mesh接口 | 20人、180提取记录、132曲线、396绑定、3564ENG探针。完整的12/16测试角色沟槽跨划分跨度25.52 mm；RigidD贴面1.58 mm，点位跨度仍25.41 mm。 | `051ffbba0c4cf34906c76fed7a44e79527b51a91` |
| 3 / 13:06 | 不放大噪声的对应 | 同60固定表面、300缓存、2400点、60图；切向带噪中位6.586→5.338 mm，但P95 9.269→11.438 mm退化。 | `36b0b74e6b1c22c10dab90fd02275b42ea09d711` |
| 4 / 随后 | 真实体表线学习原型 | 7份数据/训练/评价/可视化脚本与固定协议；本地语法和数据sanity通过。服务器执行未确认，训练入口未启动，0新训练结果。 | 见本索引所在提交 |

阶段结果不是同一种误差，不能将3.69、1.58和5.338 mm拼成一个“穴位精度”。其中3.69是作者曲线对照，1.58是查询点贴面距离，5.338是受控程序参考下的点位误差。

## 完整复查入口

1. [真实曲线完整报告](../back-reference-extraction-v1/FINAL_REPORT.md) · [30图](../back-reference-extraction-v1/figures/INDEX.md) · [独立缓存复算](../back-reference-extraction-v1/CACHE_REPLAY_VERIFICATION.json)。
2. [俯卧接口完整报告](../prone-reference-mesh-interface-v1/FINAL_REPORT.md) · [20图](../prone-reference-mesh-interface-v1/figures/INDEX.md) · [缓存核验](../prone-reference-mesh-interface-v1/CACHE_VERIFICATION.json) · [工程目标接口例子](../prone-reference-mesh-interface-v1/ENGINEERING_TARGETS_EXAMPLE.json)。
3. [对应机制完整报告](../bounded-reference-correspondence-v1/FINAL_REPORT.md) · [60图](../bounded-reference-correspondence-v1/figures/INDEX.md) · [2400逐点表](../bounded-reference-correspondence-v1/PER_PROBE_RESULTS.csv) · [缓存核验](../bounded-reference-correspondence-v1/CACHE_VERIFICATION.json)。
4. [学习原型状态与运行入口](../surface-line-completion-pilot-v1/README.md)：代码阶段，不给训练效果数字。

每份已完成交付包含固定协议、配置、代码、逐条结果、匿名预测缓存、全量图和FILES_MANIFEST。[本次Git字节核验](DELIVERY_VERIFICATION.json)检查已完成三包的工作区文件、交付SHA和真实Git blob一致。原始扫描/RGB、大型网格及权重原存于服务器；当前其存储不可见，尚未确认原因或数据损失。服务器最终交付镜像同步为pending，不能写成同步成功。

## 当前判断及下一项

主流程已扩展成：**RGB-D → 既有MHR表面 → train-only体表曲线 → face/bary/xyz/normal绑定 → 工程目标导出**。接口成立，可靠的解剖身份仍不成立；ENG点不是穴位，不能执行治疗。

这轮更清楚地区分了三个问题：表面有没有贴上、参考是不是稳定且正确、对应机制会不会放大参考错误。小贴面距离未解决后两个问题。下一笔算力应先运行已经写好的真实曲线监督/缺失深度对照；不继续调D分数，也不拿当前不稳定曲线生成穴位伪标签。原型若无优势，照实保留失败，不在六份评价来源上连续调参数。

PCdare扫描已有作者线，但非俯卧RGB-D医学标签；PressurePose是衣物俯卧、相机合同近似；受控对应是程序生成真值。现阶段不能声称临床毫米级穴位精度、部署验收或顶会创新已完成。医生参考可后补，工程开发继续。

服务器：`xuhd@172.18.18.151:436`。运行根：

- `/raid5/xuhd/datasets/back_reference_extraction_v1_20261004`
- `/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004`
- `/raid5/xuhd/datasets/bounded_reference_correspondence_v1_20261004`
- 待运行：`/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004`

当前权威状态见[CURRENT_STATUS](../../../CURRENT_STATUS.md)。未修改用户其它工作或长期生成记忆，没有删除实验、原始数据及复核现场。
