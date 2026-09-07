# 公开背部穴位资源核查（2026-09-07）

结论：DMD-BAK 最相关，但当前官方 Kaggle 下载不含训练图片；可立即使用其代码和标签定义作接入参考，不能声称已取得真人训练集。保留真实照片直接检测路线，继续建立本项目独立参考。

## 实际下载证据

官方入口：https://www.kaggle.com/datasets/chunzheye/dmd-bak

本次调用官方公开 `api/v1/datasets/view/chunzheye/dmd-bak`、`api/v1/datasets/list/chunzheye/dmd-bak`、`api/v1/datasets/download/chunzheye/dmd-bak`，均 HTTP 200。当前版本 2，更新日期 2025-09-01。下载 ZIP 为 415 字节，只含 349 字节的 `DataSet Update Statement.txt`，没有图片或 LabelMe 标注。说明称与安徽中医药大学合作建立标准采集标注流程，拟移除质量不佳的图片，并暂时下架初始数据。

元数据描述仍称 2691 张、139 位志愿者、19 种穴位，含站/坐/躺姿。这是作者对原数据的描述，不是本次取得和逐图验证的事实。仓库展示图已查看，但不足以统计俯卧与遮挡比例。2026 年仍有数据不可用反馈：https://github.com/Ye-ChunZhe/DMDBAK/issues/8 。本次未尝试通过镜像或历史版本绕过作者下架安排。

代码已克隆，版本 `474727f935fdc8873fcd4def461d40a90ed0c68d`。本地证据目录：`AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/dmdbak-audit-2026-09-07/`，包含元数据、文件清单、下载 ZIP、更新说明和仓库。

## 可利用内容与接入问题

- 官方仓库：https://github.com/Ye-ChunZhe/DMDBAK 。有 LabelMe→COCO、训练配置、RTMPose-t 配置。未找到最终背部穴位 checkpoint；初始化主干权重不能当穴位权重。
- `config/acupoint_detection/rtmpose_t_256×192.py` 定义 37 点：1 个中线点 + 18 对双侧点。19 种穴位不等于 19 输出通道。其顺序与 Frontiers Table 1 顺序不同。
- `tools/dataset/test_labelme2coco.py` 第 69 行起按图像 x 坐标对双侧点排序；接入本项目 SUBJECT_LEFT/RIGHT 前必须确认语义，尤其侧视、旋转与俯卧照片。
- `tools/dataset/split_dataset.py` 对文件随机打乱，没有受试者分组逻辑。不能直接据此声称跨人泛化；需要取得受试者 ID 后重新设计独立评估。
- 本项目 `engineering_atlas_back20_v1.json` 明确 `medical_truth=false`，E01–E20 不可解释为穴位。所贴意见给出的 GV14 等 13 个点只是另一套假定医学目标，不是当前工程 Atlas 的已验证对应。
- Kaggle 元数据标注 `CC BY-NC-SA 3.0 IGO`，仓库代码为 GPL-3.0。记录这两项不同许可，不把公开下载视为商业机器人项目已获得全部授权；新版数据许可需随获准版本复核。

## 其他候选

| 资源 | 核查结果 | 本项目用途 |
|---|---|---|
| Frontiers 2025，Structure-guided deep learning for back acupoint localization via bone-measuring constraints | 论文称从 DMD-BAK 选取并重标 430 张；Table 1 为 19 类/37 点。数据声明只指回同一 Kaggle，未核实独立发布的 430 张重标包 | 结构约束与对照实验参考；不能当另一份已获得数据 |
| IEEE JBHI，Exploring an Innovative Deep Learning Solution…，DOI 10.1109/JBHI.2024.3511128 | 作者摘要确认自建专业标注背部数据、84 点；本轮未找到可核验的公开数据与最终模型下载 | 高相关论文；考虑向作者询问可共享数据/权重 |
| AcuSim，Dryad DOI 10.5061/dryad.zs7h44jkz | 官方页面列出 13.04 GB 文件，63936 RGB-D、504 合成人体、174 点，部位为头颈；未下载 13 GB 全包 | 合成数据、可见性、RGB-D 标注流程参考，不填补真人背部监督缺口 |

原始来源：
- https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2025.1662104/full
- https://pubmed.ncbi.nlm.nih.gov/40030421/ （摘要通过 Europe PMC 公共记录交叉核实）
- https://datadryad.org/dataset/doi:10.5061/dryad.zs7h44jkz

不将文中 NME 或 FR@1cm 直接解释为我们设备的毫米误差。DMD-BAK 训练模型即使未来可获得，其在 S01/S03/S05 上的输出也是预测，不是独立真值。拟合用点与评估真值必须隔离。

## 建议顺序

1. 优先询问 DMD-BAK 作者新版图片、原始标注、人体左右定义、受试者划分及用途许可；尚未代用户发送消息。
2. 同时准备本项目少量真实目标点参考，不因等待公开数据而暂停。
3. 数据可得且标签审计通过后，采用已有 RTMPose 工程做直接 2D 基线；按受试者隔离评估，另以本项目场景评估迁移。
4. 再与语义核验后的 mesh/Atlas 和融合方案比较。当前不启动缺少输入数据的训练，不将工程点改名成医学穴位。
