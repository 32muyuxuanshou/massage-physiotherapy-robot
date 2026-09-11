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

## 执行顺序（审查通过后）

1. 完成获批下载并校验 SHA256/ZIP；
2. 运行 `prepare_frozen_manifest.py`，只按 metadata、文件完整性和等距帧规则冻结 manifest；
3. 运行所有日期 K0↔K1/K2/K3 round-trip geometry QA；
4. 跑 2 subjects × 2 actions × 1 frame Smoke，只允许修 loader/标定/renderer/输出 bug；
5. Smoke PASS 后固化 manifest 和代码哈希，再运行约 45 个 fresh frames；
6. 生成逐 subject、逐 camera、low-error、high-error、rendered-depth 与可视化数量审计；
7. 按预先冻结 Gate 判定 PASS / inconsistent / fail。

## 不在本阶段做的事

不训练、不微调、不改变 Txyz 参数、不评价 DMD37、不上传 BEHAVE 真人图像。当前代码仅做静态语法检查，不能称为 pipeline execution verified。

