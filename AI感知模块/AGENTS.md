# AI 感知模块协作规则

## 项目定位

本目录负责按摩理疗机器人的 SKEL 人体表面标注、合成 RGB-D 数据和穴位定位研究。正式医生路线是
在 SKEL 原生皮肤上建立躯干、颈部与四肢 Atlas；SMPL-X 只作独立内部研究，两者不叠加。

当前阶段、实验指标和下一门统一以本目录 `README.md` 为准。历史过程留在
`outputs/内部工程证据/` 和对应 `标注工具/blender_mcp/workstreams/`，不要复制进本规则文件。

## 代码真身

- 穴位插件：`标注工具/blender_addons/smpl_acupoint_annotator/`，版本 0.6.3，schema
  `smpl-acupoint-annotation-v5`。
- SKEL 控制插件：`标注工具/blender_addons/skel_blender_controls/`。
- 训练导出核心：`标注工具/blender_addons/modules/training_export_core/`。相机投影、evaluated
  surface binding、scene ray cast、RGB-D 和 Mask 只在这里实现。
- Blender MCP：`标注工具/blender_mcp/server.py` 与
  `标注工具/blender_addons/acupoint_blender_mcp_bridge/`，当前版本 0.2.1。
- v2.3 模板脚本：`标注工具/prepare_v23_template.py`。
- v2.3 一体化工作树：
  `发布/医生穴位标注工作台_v2.3.0_完整版/医生穴位标注工作台_v2.3.0_完整版/`。
- `构建缓存/`、运行时副本和 ZIP 都是生成物。修改时先改源码真身，再定向同步并验证，禁止只改 ZIP。

## 正式交付边界

- 当前一体化交付为 `发布/医生穴位标注工作台_v2.3.0_正式完整版.zip`。
- 两个入口保持独立：`开始使用_SKEL躯干与四肢标注.cmd` 与 `打开_SMPL-X独立研究工具.cmd`。
- 不得把旧 `smplx_skel_reference` 或 `project-surface-fit-v1` 恢复为医生正式流程。
- Blender MCP 与训练导出核心属于本机内部研究环境，尚未进入上述正式 ZIP。
- 模型及其衍生包遵守原许可；内部模型不得外发给未获许可者。

## Atlas 与数据合同

- 正式 Atlas 只绑定 SKEL 原生皮肤；骨架和关节不可选中，不自动推断医学穴位。
- 当前 E01–E20 与所有 `ENG_*` 都是非医学工程点，不得写成医生确认穴位。
- 主绑定是 `face_index + vertex_indices + barycentric`；SKEL/SMPL 的 6,890 顶点拓扑不得与
  SMPL-X 的 10,475 顶点拓扑混用。
- 规范 Atlas 锁定体型和姿态；内部研究模式才允许改变 SKEL 的 10 维 shape 与 46 维 pose。
- 只有用户主动点击“保存本次标注”才提交 `.blend` 和正式 JSON；未保存改动不得自动记录或恢复。
- 导入必须保持模型家族、性别、模板和拓扑一致；UTF-8 BOM 可兼容；重复编码与侧别跳过。
- SKEL canonical object-local `+X` 为受试者左侧，`-X` 为受试者右侧。
- Depth 为 OpenCV 相机坐标中第一可见场景表面的 `Zc`，`float32` 米，背景 0；`skin_mask.png`
  只表示第一可见表面为 SKEL 皮肤。场景必须为公制且 `scale_length=1.0`。

## 实验规则

- 研究实验必须保留 baseline，明确唯一改动，冻结 split、seed、预处理、decoder、指标和 checkpoint。
- 不能用同一测试集调参再宣称未触碰测试；Shape/Pose/Camera 离散通过不得推广为连续空间安全。
- 新定位器必须重新训练自己的 reliability/abstention 模型和阈值，禁止继承其他网络的校准器。
- 合成结果只证明当前数据合同和离散工程配置；不得外推到医学有效、真人泛化、临床可用或机器人安全。
- SKEL 是结构先验，不是患者 CT；Blender 坐标不是机器人执行坐标。

## 保护与交付

- 不得擅自覆盖、重载、关闭或删除用户 `.blend`、Atlas JSON 或未保存的 Blender 会话。
- 正式插件、canonical SKEL、Atlas、用户工作文件和发布 ZIP 默认受保护；实验写入新目录。
- `outputs/交付文件/` 的 GPT 网页端审查包必须精简：主文档、机器摘要、必要表格/图和 SHA 清单；
  不放 `.blend`、逐样本 RGB-D、权重、缓存、运行时或完整实验树。
- 完整证据放 `outputs/内部工程证据/`；每个实验只保留一个权威结果目录，失败或 superseded 目录
  必须明确标识，不得冒充现役结果。
- 正式打包排除 workspace、日志、缓存、最近记录、`test_*.py` 和自动保存文件；发布前从 ZIP 全量
  解压核对字节、文件数、禁入文件、启动器、手动保存、Atlas 导入和 SKEL shape/pose 主流程。

## 验证与停止条件

遵守上级 `AGENTS.md` 的正向开发原则：做最小正确改动，先验证主路径，只修实际发现的问题。区分
“代码可运行”“实验完成”“合成结论成立”和“真实/医学结论成立”。请求完成且相关主路径通过后停止，
不要顺手扩成框架重构、额外模型搜索或大规模负面测试。
