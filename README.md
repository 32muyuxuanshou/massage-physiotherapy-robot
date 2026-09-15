# 按摩理疗机器人

> **项目现役状态（2026-09-15）：** 统一见[项目当前状态](docs/CURRENT_STATUS.md)。最新正式交付是 [SAM3D → Txyz 复现实验 V1.4.12](docs/handoffs/real-scene-2026-09-14/sam3d-txyz-reproducibility-isolation-v1/formal-execution-v1.4.12/README.md)，Gate 为 `PASS_REPRODUCIBILITY_ISOLATION_EXECUTION`。固定帧顺序下 SAM 与 Txyz 可精确复现；另发现最大约 0.001 mm 的浮点帧顺序效应。后背语义、DMD37→MHR桥接、合成DMD37和RTMPose微调仍未放行。
项目源码、工程文档与交付资料的统一版本管理入口。

> **研究边界：** HuMMan/BEHAVE 指标是 Depth observation 到 Mesh 的单向距离聚合，不是完整人体双向表面误差或穴位误差。现有结果不能外推到治疗床、裸背、产品相机、临床有效性或机器人安全。

公开仓库：[massage-physiotherapy-robot](https://github.com/32muyuxuanshou/massage-physiotherapy-robot)。
交付下载：[Releases](https://github.com/32muyuxuanshou/massage-physiotherapy-robot/releases)。
让 AI 网页端阅读时，提供仓库链接并要求先读本页、AI 模块说明和交付索引。

## 项目入口

| 内容 | 路径 |
| --- | --- |
| 项目现役研究状态 | [当前状态](docs/CURRENT_STATUS.md) |
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
