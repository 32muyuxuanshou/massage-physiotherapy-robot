# 按摩理疗机器人

> **网页端最新交付（2026-09-10）：** [公开 RGB-D Surface 微调 V1 复盘与修正门](docs/handoffs/real-scene-2026-09-10/public-rgbd-surface-finetuning-v1-postmortem/README.md)。Gate 为 `V1_SIGNAL_CONFIRMED_BUT_ATTRIBUTION_UNRESOLVED`：固定评分确认 E1 的 surface 改善与旧测试结果，但实际训练了整个 MHR pose 投影头，shape/scale/hand 均变化，且大部分收益由整体平移解释。历史 Pilot 信号保留，归因已修正；下一轮训练暂缓。
项目源码、工程文档与交付资料的统一版本管理入口。

> **最新研究边界：** 原模型/第2轮/第10轮的旧 fitted-only 结果不支持主指标提升；修正版 Visible A/B V2 已完成 10 轮，epoch5 的 NME 为 0.034273，epoch10 的 PCK05 为 0.812213。当前证据只到 COCO 来源二维关节 validation，不能宣称 Mesh surface、DMD37 或医学准确性。

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
