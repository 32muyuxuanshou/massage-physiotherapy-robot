# 按摩理疗机器人

> **网页端最新交付（2026-09-09）：** [完整实验、批量mesh对照与当前训练状态](docs/handoffs/real-scene-2026-09-09/README.md)。内含更正后的验证指标，请以此入口替代旧交付状态。
项目源码、工程文档与交付资料的统一版本管理入口。

> **最新执行（2026-09-09）：** [69图82人体批量mesh对照](AI感知模块/outputs/内部工程证据/2026-09-09_BATCH_MESH/README.md)完成。发现并修正两图三个人体的COCO标注对应，原模型/第2轮/第10轮NME更正为0.035207/0.035243/0.035442，未见主指标提升。全427记录已做对应审查；9条训练记录暂不使用新增人工loss。修正后的可见人工关节监督对照V2已启动10轮，尚无结果，Atlas和原模型未替换。

> AI真实场景微调主线已于2026-09-08获用户授权恢复：已完成官方MHR下载、20图对照及回归头单步更新检查，尚无新正式checkpoint或泛化提升结论。[当前状态与恢复记录](docs/ai-workflow-pause-2026-09-08.md)为最新入口；下方2026-09-06交接文档属于历史版本。本次记录尚未提交或推送到GitHub。

公开仓库：[massage-physiotherapy-robot](https://github.com/32muyuxuanshou/massage-physiotherapy-robot)。
交付下载：[Releases](https://github.com/32muyuxuanshou/massage-physiotherapy-robot/releases)。
让 AI 网页端阅读时，提供仓库链接并要求先读本页、AI 模块说明和交付索引。

## 项目入口

| 内容 | 路径 |
| --- | --- |
| 理疗机器人客户端 | [工程代码](理疗机器人客户端/工程代码/) |
| AI 感知与医生标注工具 | [模块说明](AI感知模块/README.md) |
| 真实场景研究与网页端交接（2026-09-06） | [完整交接文档](docs/real-scene-research-2026-09-06.md) |
| 机械臂官网 | [展开后的源码](机械臂官网/src-project/) |
| 理疗机器人官网 | [展开后的源码](理疗机器人官网/src-project/) |
| 机械臂运动学演示 | [robot_demo](robot_demo/) |
| 组会汇报 | [汇报目录](SKEL_RGBD_组会汇报_2026-09-02/) |
| Git 操作与交付 | [使用指南](docs/GitHub使用指南.md) |
| 交付文件索引 | [交付目录](deliverables/README.md) |

两个官网的 `src-project/` 由原始 ZIP 展开，后续直接修改这里的源码。原 ZIP 仍保留在本机。

## 版本管理范围

Git 管理源码、脚本、文档和适量设计/汇报资料。`.gitignore` 排除本机密钥、数据库、依赖、
构建缓存、升级备份、模型权重、Blender 场景、实验 outputs、大型媒体与安装归档。
这些被排除的内容仍保留在本机，但不能通过 Git 回退，也不会随着代码推送备份到 GitHub。
需要交付的安装包和大型媒体应单独上传到 Releases；实验数据与授权模型需另行备份。

AI 模型与部分医生安装包含受许可约束的资源，按 [AI 模块说明](AI感知模块/README.md) 的范围使用。
