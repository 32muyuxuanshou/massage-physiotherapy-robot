# BEHAVE Cheap Txyz 泛化验证 V2：执行前审查包

状态：`READY_FOR_REVIEW_NOT_EXECUTED`

本提交只包含实验代码与冻结合同。根据最新要求，尚未启动 Smoke 或 Full Batch。Date03 的并行下载已停止，现有分片保留；Date06 在停止指令到达前已经下载完成。

## 审查时请先确认

1. 历史冻结总平移上限为 `0.17788820176363325 m`。V1 BEHAVE 使用了 `0.18 m`，差值是 **2.112 mm**。V2 恢复历史精确值，这一决定在看 V2 结果前冻结。
2. V2 不再硬编码 Date01。代码从 sequence 名解析 `DateXX`，并分别读取对应日期 K0/K1/K2/K3 外参。
3. Sub01 是上一轮已消费的 regression/smoke subject。正式泛化必须单独报告 fresh subjects。
4. K0 固定为推理/修正相机；K1/K2/K3 只做 held-out 评价，不参与 Txyz，也不重新运行 SAM。
5. 主指标、50 mm coverage、low-error 30 mm 与 meaningful degradation 5 mm 均已在结果打开前冻结。

## 下载组合结论

候选 ZIP 的实际 HTTP `Content-Length` 和 subject 集合见 [`report/BEHAVE_V2_DOWNLOAD_PLAN.json`](report/BEHAVE_V2_DOWNLOAD_PLAN.json)。

- 从零开始达到 4 个 fresh subjects 的最小组合：Date06 + Date07，42.896 GB。
- 从零开始达到 5 个 fresh subjects 的最小组合：Date05 + Date06 + Date07，60.141 GB。
- 当前 Date06 已完成，Date03 已传输约 30 GB 分片。若按“剩余下载字节最少”达到 5 个 fresh subjects，完成 Date03 并增加 Date05，预计还需约 32 GB；最终完整包总量约 76.9 GB。

推荐审查选择：使用已经发生的下载进度，完成 Date03 + 新增 Date05，与已完成 Date06 组合，得到 Sub03/04/05/06/07 五个 fresh subjects；Sub01 只进入 Smoke/Regression，不进入 fresh-only 主结论。

## V2.1 预执行修复

- 正式 manifest 使用明确的 subject→date→sequence 表；Sub05 固定 Date03 的 `backpack/stool/yogaball`，不再跨日期模糊搜索。
- `prepare_smoke_manifest.py` 只允许已消费的 Date01/Sub01 进入模型级 Smoke；Sub03–07 只做文件、Depth/Mask 与标定检查。
- Camera QA 逐点对照 BEHAVE 官方 `KinectTransform`，并检查四相机人体点云进入 world 后的重叠。
- rendered-depth 先将 sensor Depth/Mask 最近邻去畸变，再与 pinhole z-buffer 比较。
- 聚合公式、相对 5% P95 Gate、各类审计输出均已在看结果前写入代码。
- 模型、MHR、anchor、评价器、SAM3D 源码树和环境指纹已冻结。
- 可视化按正式 manifest 全量审计并生成确定性 montage，不按结果挑图。

## V2.2 预执行修复

- Smoke 改为调用实际存在的 `choose_frames()`，并在写入 manifest 时保存帧目录名。
- Sub06 冻结为官方存在的 `backpack_back / stool_sit / yogaball_play`。
- rendered-depth 聚合从每个 K1/K2/K3 相机节点读取，预执行测试要求恰好生成 15 条记录。
- point-to-triangle outlier audit 固定报告 P99、max、超过 500 mm 的数量和比例；只审计，不删点、不改 Txyz。
- Runner 要求 Camera QA 覆盖正式 manifest 的每个 sequence、三个 held-out camera 和点云重叠检查。
- Runner 启动时重新计算 checkpoint、config、MHR、anchors、评价器和 SAM3D 源码树哈希，不一致即报 `ASSET_FREEZE_MISMATCH`。
- 3D viewer 旁增加 front/side/top 静态 PNG；Txyz 图改成 Tx/Ty/Tz 三轴显示。

`preflight_v22.py` 已在纯模拟目录通过，包括正式 sequence 解析、QA 缺失拒绝、资产篡改拒绝、rendered-depth/outlier 聚合数量检查。状态仍是 `HOLD_FOR_WEB_REVIEW`，没有读取 fresh subject 模型结果，也没有启动 Smoke 或 Full Batch。

## V2.3 启动修复

- Smoke manifest 现在带冻结状态和 `CONSUMED_SMOKE_ONLY` role；正式汇总明确拒绝该 role。
- Txyz 恢复历史 System C 的全量 Camera-A 人体深度点，不再使用 25,000 点近似。
- fallback 优先分类为 `FALLBACK_OFFICIAL`；非 fallback 按 improved/unchanged/degraded 三态分类。
- 汇总器必须同时读取冻结正式 manifest，并严格验证 5 subjects、15 sequences、45 unique frames 与每帧 K1/K2/K3 完整。
- 25/50/75% 若不能产生三个不同帧，直接报 `DATA_INSUFFICIENT_FOR_FROZEN_SAMPLING`。
- 最终报告增加 Tx/Ty/Tz/|T|、fallback 数量以及 SAM/Txyz/总耗时的 P50/P90。

`preflight_v23.py` 已覆盖 Smoke role、fallback 分类、重复帧拒绝和缺少一个正式结果时阻止 Gate。用户已授权修完后直接启动服务器流程。

## 执行顺序（网页端审查批准后）

1. 完成获批下载并校验 SHA256/ZIP；
2. 运行 `prepare_frozen_manifest.py`，只按 metadata、文件完整性和等距帧规则冻结 manifest；
3. 运行所有日期的官方实现数值对照、round-trip 和点云重叠 QA；
4. 只对已消费的 Sub01 跑 2 actions × 1 frame 模型 Smoke；
5. Smoke PASS 后固化 manifest 和代码哈希，再运行约 45 个 fresh frames；
6. 生成逐 subject、逐 camera、low-error、high-error、rendered-depth 与可视化数量审计；
7. 按预先冻结 Gate 判定 PASS / inconsistent / fail。

## 不在本阶段做的事

不训练、不微调、不改变 Txyz 参数、不评价 DMD37、不上传 BEHAVE 真人图像。当前代码仅做静态语法检查，不能称为 pipeline execution verified。
