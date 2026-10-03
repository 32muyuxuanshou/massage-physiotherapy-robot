# 无部署相机时：公开背部数据搜集与审计

日期：2026-10-03。状态：实际下载与文件审计已完成；本轮没有训练、SAM 推理或新的几何拟合。

后续已完成205图全量视觉与更细的单位/线关联审计，见[最新资格报告](../prone-back-point-validation-v1/DATA_QUALIFICATION.md)。本页以下保留最初下载阶段的检查范围，不将当时37张浏览等同于后续205张复核。

## 结论

新增真实背部点云及历史穴位图片，已保存到 `172.18.18.151`。这些资产分别补充表面几何和二维语义开发，尚不能组成“校准俯卧 RGB-D + 独立三维穴位参考”的验证集。继续保留现有 PressurePose 俯卧缓存和 BEHAVE 跨相机证据，不用不同数据的结果替代部署精度验收。

| 资产 | 实际取得与检查 | 当前可用范围 |
|---|---|---|
| PCdare | 2,250 个选定文件，共 402,360,708 bytes；504 个 PLY 全部解码，非有限坐标为 0 | 真实背部表面与参考线开发；接入前须完成逐文件单位、扫描与标记绑定 |
| DMD-BAK V2 | 实际 ZIP 415 bytes，仅一份整改声明，图片数为 0 | 不构成可用图像数据集 |
| DMD-BAK 历史 V1 | 实际取得 205 组图像/JSON，共 449,142,256 bytes；逐条 CRC 校验、SHA256 记录及图像解码 | 单独保存供质量审计和格式开发；标签暂不作为正式训练或穴位准确率参考 |

PCdare 的 504 个 PLY 包含 **324 个不在 Output 路径下的文件和 180 个 Output 派生文件**。324 也不等于独立扫描数或人数，未做受试者去重。数据下载通过不等于医学对应验证通过。

## PCdare：为什么取得，缺什么

[官方仓库](https://github.com/mkaisereth/PCdareSoftware)固定在提交 `35f7a1d9c1b24264708111a986ba89bdf17f1df1`。选定工作目录含点云、JSON 与读取代码；每个文件核对 Git blob identity、字节数并记录 SHA256。旧服务器 Git 不支持 partial clone，因此 Git 对象包仍包含仓库其它资源，不能把稀疏工作目录等同于全部磁盘下载范围。

933 个 JSON 含非空 `pcMarkers`，1,104 个含非空 `pcLinePts`；这是文件计数，包含重复或派生标注，不是已确认的独立专家标签数。源代码存在“软件内用 m、保存标记/线用 mm”以及旧版标记用 m 的分支，故审计保留全部 native 坐标，尚未统一换算。每个扫描必须先与其 JSON、处理变换和单位绑定。

[相关原始研究](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0321429)主要分析脊柱侧弯人群的背部形状及影像关系，包括站立采集。研究中影像上的脊柱线不能自动当作背部表面的椎体或穴位真值。当前选定文件也未建立可直接输入 SAM3D 的校准 RGB/depth/相机元组。

因此先将它作为**真实裸背表面与对应关系的研究资源**，不计入俯卧 RGB-D 主评价、不承诺三维穴位精度。仓库标明 CC BY-NC-SA 4.0；公开数据留在服务器，不在项目 Git 重发。

## DMD-BAK：实际内容推翻了此前的可用性假设

[官方仓库](https://github.com/Ye-ChunZhe/DMDBAK)指向 [Kaggle 数据入口](https://www.kaggle.com/datasets/chunzheye/dmd-bak)。当前 V2 的实际下载只包含声明：作者正在与中医药大学完善采集与标注规范，移除质量不足内容并暂时撤下初版。网页描述中的 2,691 张、139 名志愿者等是发布者描述，不能当作当前可下载资产的实测数量。

仍可匿名读取的 V1 远程 ZIP 为 8,562,947,645 bytes；目录枚举得到 2,357 个 JPG/PNG、2,358 个 JSON，其中按同目录同 stem 精确配对得到 1,255 组，涉及 75 个目录分组。目录不是经过验证的受试者 ID。未下载整包；按目录排序，取每组首/中/末配对样本，共 205 组，用 HTTP Range 下载、逐条 ZIP CRC 校验并记录文件 SHA256。

205 组的实际检查结果：

- 17 组 annotation 的宽高与实际图像不一致；11 张存在实际图像范围外的标注点。
- 5 张为 SHA256 完全重复图像，计数方式为总数减去唯一图像数。
- 43 组 JSON 中的 `imagePath` basename 与实际文件名不同；这可能来自重命名，不能仅凭此判定图文错配。
- 点数分布为：198 张有 37 点、5 张有 35 点、1 张有 36 点、1 张有 38 点；出现点类拼写差异，以及 3 张中的 `back` point 标签，不能直接规范化成医学点位。
- 人工查看 7 页、37 张：可见直立或前倾背部，未确认床上俯卧；未检查的 168 张不推断体位。横置照片不等于俯卧。

已生成全部 35 页“原图 / 供应标签”对照，黄色点来自原 JSON，**没有模型预测**。完整图像解码不等于逐图临床标注复核。未建立原始 depth、相机标定、独立三维穴位参考或可靠 subject split。标签目前隔离保存，不能用于宣称医学定位精度。平台元数据标示 CC BY-NC-SA 3.0 IGO；后续正式使用需确认图像与标注的具体授权。

## 其它来源与没有完成的事项

- PressurePose 现有俯卧 20 人测试继续使用。额外 prescribed 文件所在 Dataverse 接口本轮返回 403，没有取得新文件，也不填报新增样本。
- [MinimalRequiredResolution](https://github.com/mkaisereth/MinimalRequiredResolution)仓库主要提供代码，研究数据另有 ETH 入口；本轮未取得该独立数据包。
- [近期俯卧穴位机器人研究](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2025.1696824/full)描述了俯卧 RGB-D 与专家定位，但未找到公开完整下载包；没有将论文中的精度当作我们的结果，也没有联系作者。
- [Acupoint 图像项目](https://github.com/moon-no-sleep/Acupoint/blob/main/README.en.md)公开说明的点类主要为四肢/腹部，不作为本阶段背部主资源，未下载大包。

本轮未发现可立即作为主验证集使用的公开“俯卧裸背、校准 RGB-D、可靠受试者划分、独立三维穴位标签”完整资产。这是本轮检索与实测范围内的结论，不是对所有公开资源的断言。

## 服务器与审计入口

服务器：`xuhd@172.18.18.151`，SSH 端口 `436`。

根目录：`/raid5/xuhd/datasets/back_prone_acquisition_20261003`

| 内容 | 根目录下路径 |
|---|---|
| PCdare 选定工作目录 | `pcdare_35f7a1d9/` |
| PCdare 下载身份 | `PCDARE_DOWNLOAD_AUDIT.json` |
| DMD 当前 V2 ZIP 与审计 | `dmd_bak/dmd-bak-v2.zip`、`dmd_bak/DOWNLOAD_CONTENT_AUDIT.json` |
| DMD 历史 V1 目录清单 | `dmd_bak/VERSION1_REMOTE_INVENTORY.json` |
| DMD 205 组实际文件与 SHA/CRC | `dmd_bak/historical_v1_quality_audit/`，含 `SELECTION.json`、`DOWNLOAD_AUDIT.json` |
| 全量结构审计及可视化 | `quality_audit/` |

本地审阅副本在 `E:/项目-按摩理疗机器人/output/data_acquisition_20261003/review/`，其中 `quality_audit/` 含两份逐文件 JSON、PCdare 点云预览和 DMD 35 页对照。原始数据留在服务器。点云预览采用 PCA 显示轴，颜色不代表相机 depth，更不代表穴位。

本交付的 [资产摘要](DATASET_INVENTORY.json)、[匿名图像结构审计](DMD_PILOT_ANONYMIZED_AUDIT.json)和 [脚本说明](CODE_AND_REPRODUCTION.md)可复查计数与处理逻辑。包含原始路径的身份清单保留于服务器/本地审阅目录。

## 对下一步的影响

继续现有俯卧缓存的 topology transfer 与 Rigid→Rigid+D 点位形变诊断；该步骤不依赖新采集设备。随后按冻结规范检查 BEHAVE 的独立机位表面改善。新增 PCdare 先核实扫描/标记/单位，DMD 先处理标签资格，不将“下载到更多图片”当作训练启动条件。

暂不因本轮数据搜集调整算法、超参数、原 20 人划分、种子或历史指标。没有部署相机可以继续研究与工程验证，但公开数据不能保证未来设备上的效果不变。
