# SIM_BACK_20_REFERENCE_V1 独立验收

结论：工程结构与导入回放通过；未发现会阻断使用该 JSON 作为“模拟参考 Atlas”的问题。它不是医生确认医学真值，不能提升为正式临床 Atlas。

## 静态检查

- Atlas SHA-256：`FC9E387134F277B27A2D9F1C6FE8690EA0D6C1C15E4FCB0DA380BB295011FBC0`
- schema / plugin：`smpl-acupoint-annotation-v5` / `0.6.3`
- model / gender：`SKEL` / `female`
- model template：`skel-female-trunk-limb-v2.3`
- session template：`SKEL_FEMALE_TRUNK_LIMB_v2.3`
- canonical shape / pose：`shape-zero` / `template-default`
- topology：6,890 vertices / 13,776 triangles / `dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733`
- annotations：20；annotation id、point_id、code+side 均 20/20 唯一。
- barycentric：全部在范围内；最大 `abs(sum-1)` 为 `3.725290298461914e-08`；最小/最大权重 `0.003417043015360832` / `0.9533290266990662`。
- `1/3,1/3,1/3`：0/20；不是统一写死的三分之一。
- notes：20/20 均包含 `SIMULATED_FROM_REFERENCE; medical_validated=false`；20/20 为 `DRAFT`。

## 保存态工作 Blend

- 原文件 SHA-256：`C73BF510FD19EDDF171BCF72758C213FA220F4473C40A71FE909F6387A37BBF5`
- 只打开相同哈希的隔离副本；副本重开后读取到已序列化的 20 点。
- 20/20 face、vertex indices、barycentric 与 JSON 匹配；最大 barycentric 误差 `0.0`。
- 工作 Blend 与正式 JSON 的最后写入时间同为 2026-08-29 16:00:52（Asia/Shanghai，文件系统记录相差约 47 ms）。

## 干净 canonical 正式插件导入

- canonical 原文件、导入前副本及 session 声明的模板 SHA-256 均为：`539D39AA45C2696FE6B5F79E5A82B623604E6E569167763A4AEAA494C49BA1E9`。
- Blender 4.5.12 LTS，`--factory-startup --background` 隔离运行。
- 加载正式插件真身 `标注工具/blender_addons/smpl_acupoint_annotator/__init__.py`，版本 0.6.3。
- canonical 副本导入前 0 点；导入 20，跳过 0；导入后 20 点。
- 20/20 face、vertex indices、barycentric 完全恢复；最大 barycentric 误差 `0.0`，最大 canonical local position 误差 `0.0 m`，严格小于 `1e-7`。
- 导入结果仅另存为 verification 目录内的 `canonical_after_formal_import.blend`；未保存或改写 canonical 原文件及原工作 Blend。

## 挑错式注意项

- 该文件的 session 已明确写为 `doctor_id=CODEX_SIMULATION_NOT_DOCTOR`，每点 notes 也明确未医学验证，且均为 DRAFT；因此只能作为模拟参考/工程链路材料。
- 根字段 `medical_status` 仍使用插件通用文本 `doctor_annotation; not an automatic clinical recommendation`，且每点 `confidence=1.0`。这不破坏 schema 或导入，但脱离 notes 单独展示时有误读风险；任何下游都应以模拟标记和 `medical_validated=false` 为硬门。
- session 与 model 的 template ID 分别使用大写下划线和小写连字符两种规范字符串。当前 canonical 文件哈希、对象描述与拓扑全部匹配，所以不是本次导入故障，但下游不应只做区分大小写的 template 字符串等值判断。

## 边界保护

- 正式插件、canonical 模板、发布包未修改。
- 用户 Blender PID 32808 验收结束时仍存在并响应；未向该进程发送任何命令。
