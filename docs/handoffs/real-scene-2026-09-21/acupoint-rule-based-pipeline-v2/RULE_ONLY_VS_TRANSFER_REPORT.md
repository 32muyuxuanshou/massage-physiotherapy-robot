# Rule-first 工程 sanity 交付

## 目的

本次执行把穴位阶段拆成了一个可审计的规则引擎：显式输入参考水平、侧向轴和比例尺度，计算规则目标，再投影到 `POSTERIOR_TORSO_V1` 表面。它验证的是**软件流程和几何数据流**，不是临床定位准确率。

## 实际执行

`run_rule_engine_sanity.py` 对 canonical MHR 以及现有 B1–B5 `prediction.npz` 使用同一份 `RULE_ENGINE_CONFIG_V1.json` 和同一张 posterior mask，生成每个样本的：

- `PROXY_LANDMARKS.json`：由 mask 几何插值得到的代理参考水平；
- `RULE_OUTPUT.json`：规则目标、表面点、face index、barycentric、surface normal；
- `RULE_ONLY_GEOMETRY_SANITY_V1.json`：汇总与明确限制。

## 规则范围

当前配置只把背部工程演示点写成可计算合同：`GV14`、`BL13`、`BL15`、`BL18` 和 `GV4`（左右穴位按规则展开）。配置记录参考水平和 `1.5 B-cun` 侧向关系，但没有把固定毫米偏移当成医学事实。

## 结果解释

所有输出均为 `ENGINEERING_PROXY_ONLY`，`medical_truth=false`。当前代理水平来自后背 mask 的纵向插值，比例尺度来自 mask 横向宽度的确定性 proxy；它不能替代 C7、T3、T5、T9、L2 或肩胛等真实解剖标志。因此本次结果只能证明：

1. 规则输入合同明确；
2. 规则点可在相同拓扑的 canonical / prediction mesh 上重复计算；
3. 表面投影能输出机器人后续需要的几何字段。

它不能证明 topology transfer 或规则计算已经达到医生可接受误差，也不能直接用于治疗执行。

## 后续门槛

医生介入可以放到工程链完成之后，但在临床/论文准确率结论前必须替换代理参考框架，并用独立真人标注做验证。若代理链在真实数据上显示稳定残差，再考虑 landmark/visibility/residual 小模块，而不是直接把穴位预测做成黑箱。
