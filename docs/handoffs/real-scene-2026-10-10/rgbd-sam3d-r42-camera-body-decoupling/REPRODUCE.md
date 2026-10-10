# 恢复与重算

依赖上一轮[R4.1恢复说明](../rgbd-sam3d-r41-fair-txyz/REPRODUCE.md)中的三个私有包。先核对SHA并恢复R41_WORK；本轮增量包位置和SHA见`BACKUP_RECEIPT.json`。R4.1证据源commit为`97afeae585528edfa0fd80d399bd0b9493c4ee54`，Official三seed缓存复算增量为`852a9bcf`。

本地实际环境：Python3.11、NumPy2.4.6、SciPy1.17.1、Pillow/Matplotlib；无GPU需求。重新生成全部缓存：

```text
python code/run_r42_components.py --source R41_WORK --out NEW_R42 --workers 6
python code/train_r42_camera_only.py --source R41_WORK --out NEW_R42/camera_only_pilot
python code/evaluate_r42_camera_only.py --source R41_WORK --out NEW_R42 --workers 6
python code/analyze_r42.py --source R41_WORK --work NEW_R42
```

脚本与旧数值源码一起交付。新tiny头不需要Torch；39系数ridge以TRAIN A伪标签训练，不使用真实Camera GT或B选模。新输出目录不要覆盖原交付。

图需原16帧私有RGB，以及增量包的11帧RGB和`VISUAL_SELECTION.json`。复制到新目录后：

```text
python code/visualize_r42.py --source R41_WORK --work NEW_R42
```

Torch接口检查需要原SAM3D源码、四个既定缓存fixture及真实prepared batch；脚本`check_r42_camera_output.py`在AutoDL CPU Torch2.12.1上实际执行。它直接执行官方projection AST，避免无卡机器加载完整模型。参考`TORCH_ADAPTER_QA.json`及`EXECUTION_LEDGER.json`，不要把它误解成新网络推理。

本轮私有包已保存四份实际prepared batch（`torch_fixtures/cache/*.pt`）、全部fixture和对应官方源码。恢复为R42_WORK后，可在CPU Torch环境独立重放：

```text
python code/check_r42_camera_output.py --official R42_WORK/official_source --fixtures R42_WORK/torch_fixtures --cache R42_WORK/torch_fixtures/cache --out REPLAY_TORCH_QA.json
```

缓存独立审计用`audit_r42.py`：实际检查全部新网格、A/B点集SHA、原生参数、单次平移，8例直接从缓存重算B距离。原执行中“训练源码快照”和最终推理代码只有缺失Depth旁路不同，训练kernel精确相同。若重放最终版训练，新的full-file SHA与原训练快照不同是预期现象；不应混淆成原权重变更。

只有组件交换使用G1三个训练seed；小模型为确定性闭式训练，没有复制三套种子结果。全部聚合保持frame→sequence→identity，原始/校正两阶段、TRAIN/VAL分开。所有B点固定，无B对齐，无TEST读取。
