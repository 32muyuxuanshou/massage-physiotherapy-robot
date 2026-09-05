# SIM_BACK_20_REFERENCE_V1 重选后独立验收

结论：通过。此报告取代 `independent_qa_20260829_162500` 对当前 Atlas 的结论；旧目录保留且未覆盖。

## 输入哈希

- 新 Atlas：`F29E5BCD9C8CEF0E015924486FD81F5E8F6748B7D2EA35B10D6E3F9A16CE2E2A`
- 最终复核时的工作 Blend：`755344E28B0FF7FE45F84EE8DAD0455C99A80AF415606F5009898F27B6E9B6A3`
- canonical SKEL female：`539D39AA45C2696FE6B5F79E5A82B623604E6E569167763A4AEAA494C49BA1E9`

## 完整静态检查

- schema / plugin：`smpl-acupoint-annotation-v5` / `0.6.3`
- model / gender：`SKEL` / `female`
- canonical shape / pose：`shape-zero` / `template-default`
- topology：6,890 vertices / 13,776 triangles / `dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733`
- annotation id、point_id、code+side：均 20/20 唯一。
- barycentric：全部在 `[0,1]` 且和在 `1e-7` 内；最大 `abs(sum-1)` 为 `3.3527612686157227e-08`；最小/最大权重为 `0.0032378581818193197` / `0.9533290266990662`。
- `1/3,1/3,1/3`：0/20，不是统一写死的三分之一。
- 20/20 均保留 `SIMULATED_FROM_REFERENCE` 与 `medical_validated=false`，且均为 `DRAFT`。

## 四个重新点选点

- `GB21_LEFT`：`body_region=NECK`；notes 含 `C7-to-acromion midpoint approximate`。
- `GB21_RIGHT`：`body_region=NECK`；notes 含 `C7-to-acromion midpoint approximate`。
- `SI15_LEFT`：`body_region=TORSO`；notes 含 `same C7 level as GV14; 2 B-cun approximate`。
- `SI15_RIGHT`：`body_region=TORSO`；notes 含 `same C7 level as GV14; 2 B-cun approximate`。

canonical local Y：

- GV14：`0.22726985812187195 m`
- SI15 左：`0.22723186016082764 m`
- SI15 右：`0.22722914814949036 m`
- 三点最大跨度：`4.07099723815918e-05 m` = `0.0407099723815918 mm`
- GV14↔SI15 左：`3.7997961044311523e-05 m`
- GV14↔SI15 右：`4.07099723815918e-05 m`
- SI15 左↔右：`2.7120113372802734e-06 m`

## 工作 Blend 保存态重开

- 第一份隔离副本 SHA-256 为 `FE9FBE863A31B966FFB96A0E01D03CB07DA44FA8292FD08C82EE16513C49E6E0`，对应 16:18:48 保存态；重开读取到已序列化的 20 点并通过。
- 验收期间原工作 Blend 被外部进程于 16:22:45 再次写入，SHA-256 变为 `755344E28B0FF7FE45F84EE8DAD0455C99A80AF415606F5009898F27B6E9B6A3`。验收流程没有打开或保存原文件。
- 对最终哈希另取 `work_saved_copy_final.blend`，再次隔离重开；仍为 20 点，且与同一新 JSON 完全一致。
- 20/20 face、vertex indices、barycentric 与新 JSON 匹配；最大 barycentric 误差 `0.0`。

## 干净 canonical 正式插件导入

- Blender 4.5.12 LTS，`--factory-startup --background` 隔离运行。
- 加载正式插件真身 `标注工具/blender_addons/smpl_acupoint_annotator/__init__.py`，版本 0.6.3。
- canonical 隔离副本导入前 0 点；导入 20、跳过 0、最终 20 点。
- 20/20 face、vertex indices、barycentric 完全恢复。
- 最大 barycentric 误差 `0.0`；最大 canonical local position 误差 `0.0 m`，严格小于 `1e-7`。
- 导入证据 Blend SHA-256：`CD2B10282F299CF32843079369F38ECD1CDAD5695CB969578FCAE804DA6506F8`。

## 边界保护

- 旧 verification 证据未覆盖。
- 正式插件、canonical、发布包和原工作 Blend未由验收流程写入。
- 导入结果仅保存到本目录 `canonical_after_formal_import.blend`。
- 原工作 Blend 在验收期间存在一次外部保存竞态；两个捕获版本都通过相同的 20 点精确核对，最终报告以 `755344…B6A3` 为准。
