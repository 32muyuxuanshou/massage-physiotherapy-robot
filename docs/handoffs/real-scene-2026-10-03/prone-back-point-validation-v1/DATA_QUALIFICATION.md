# 实际数据资格：可用范围与缺口

日期：2026-10-03。下载/解码/结构通过与医学参考资格分开。当前没有公开资产被本轮放行为三维穴位 GT，没有训练。

| 来源 | 可取得 | 已下载/解码 | 已审核 | 本轮使用 |
|---|---|---|---|---|
| PressurePose p_select | 已有 | 20 人俯卧 RGB/过滤点云与历史 300 缓存 | 本轮实际读取缓存、身份及拓扑 | 点传播与形变诊断；近似相机合同 |
| BEHAVE | 官方日期包 | 原 45 帧四机位输入完整 | 180 视图预模型 ROI，16 sequence 标定/点云 QA | 225 网格；36 held-out 后背小块、28 帧有效；穿衣非俯卧 |
| PCdare | 官方仓库固定 commit | 504 PLY 解码，324 非 Output 路径 | 324 扫描与 1,326 邻近线候选；单位/重新绑定源码 | 几何与线来源开发；无校准 prone RGB-D / 穴位 GT |
| DMD 历史 V1 | 远程历史版本 | 205 图/JSON，449,142,256 bytes | 205 身份、全部 35 页视觉复核 | 格式/二维诊断资格；1 张确认俯卧；撤下的标签不用于准确率或训练 |
| DMD 当前 V2 | 下载入口可返回文件 | ZIP 415 bytes，0 图片 | 撤下/整改声明已读取 | 无图像可用 |
| SLP | 官方仓库说明多模态并指向访问申请 | 本轮未取得该数据包 | 项目页当前访问失败；未核样例、字段、prone 子集或真实相机合同 | 未使用，不将仰卧/侧卧自动计为俯卧 |

## DMD

[匿名结构审计](results/p3/IMAGE_LABEL_IDENTITY_AUDIT.json)有 185 个二维结构开发候选、20 个身份/坐标待核实案例。17 个尺寸不一致、11 张越界点和其它问题集合重叠，不能相加成坏图数量。5 张精确重复以总数减唯一 image hash 计。

[205 图视觉资格表](results/p3/DMD_205_VISUAL_QUALIFICATION.csv)确认 `dmd_audit_020` 为支撑面上的俯卧裸背且结构合格。其余仅编码“直立/部分背部、无俯卧证据”，包含前倾、坐姿和局部裁切，不一概说站立。可靠受试者身份和医学标注一致性都没有建立。

[embedded 图像诊断](results/p3/DMD_EMBEDDED_PIXEL_DIAGNOSIS.json)：001/201/204 三组宽高均匹配，解码像素均值差分别 1.16/0.48/0.82。重编码可造成这种差异，不能凭“非 exact”判定错配；保留待核实状态，没有改变原标签。

[点类拼写清单](results/p3/DMD_POINT_CLASS_INVENTORY.json)保留 25 个原始 label 字符串及点数。`back`、`rushu` 等不能自动当标准穴位；`sanjioashu` 等疑似拼写差异也不在本轮改原标签。整个 withdrawn V1 没有升级为医学监督。

[作者仓库](https://github.com/Ye-ChunZhe/DMDBAK)与[Kaggle 入口](https://www.kaggle.com/datasets/chunzheye/dmd-bak)只用于来源核查，发布者历史规模不等于当前实际文件数。

## PCdare

[匿名扫描表](results/p3/SCAN_REFERENCE_BINDING_PUBLIC.csv)和[单位来源](results/p3/PCDARE_UNIT_AND_PROVENANCE.json)来自实际读取和源码，不靠拟合 Mesh 调尺度。`pc.Location` 为 m；saved `pcLinePts` 为 mm，软件读取时 /1000。其它旧版 marker 和派生线字段仍须按各自代码链解释。

旧索引直接匹配 0 不代表参考线无用：[重新绑定诊断](results/p3/PCDARE_LINE_REBINDING_PUBLIC.json)对应官方 `E2_StartPCDrawLineApp.m:58` 的 nearest-neighbor 重新绑定。7 个旧索引范围候选中的 pcscan_292 一组线坐标精确落在当前表面附近；另 6 组最大最近距离约 1.2 mm，仍可能反映扫描降采样。没有用数字相近直接确认唯一 session、人或解剖 GT。

`pcLinePts` 是 drawn surface line；`eslLinePts` 可能是拟合/平滑派生线。影像脊柱线、体表画线、动画关节与触诊椎体是不同参考，不能互换。非 Output、文件夹数也不自动等于原始扫描数或独立人数。

公开表使用 scan/candidate 匿名 ID 与 SHA；含原文件路径及姓名线索的完整关联保留在服务器。原始数据未重发。[官方代码](https://github.com/mkaisereth/PCdareSoftware)固定 commit `35f7a1d9c1b24264708111a986ba89bdf17f1df1`。

## 后续资源与范围

[SLP 官方仓库](https://github.com/ostadabbas/SLP-Dataset-and-Code)介绍 RGB/LWIR/depth/pressure 及覆盖条件，但本轮未下载、未建立 prone 与标定资格。没有授权代发申请。其它俯卧穴位机器人论文尚未取得可用完整公开包，见[前次下载审计](../back-data-acquisition-v1/README.md)。

若取得新数据，先验收真实图/depth/K/单位/同一人对应/目标参考及许可，再冻结开发和测试。不会把 DMD 照片与 PCdare 扫描配成不存在的 RGB-D，也不会把文件数叫作样本人数。
