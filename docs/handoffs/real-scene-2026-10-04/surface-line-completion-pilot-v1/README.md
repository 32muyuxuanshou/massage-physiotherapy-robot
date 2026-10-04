# 体表线学习原型：代码阶段，尚未训练

**状态：CODE_SYNTAX_AND_DATA_SANITY_VERIFIED / SERVER_STORAGE_UNAVAILABLE。** 2026-10-04连续执行时已写好小模型、数据处理、训练及独立评价入口。服务器随后SSH连接超时；之后密码登录成功，但`/raid5/xuhd`和数据目录不存在，`/raid5`仅为空目录。既有存储当前不可见，原因未确认，不代表已确认数据丢失。未发起训练入口，没有checkpoint、训练结果或医学结论。远端模型正向/反向测试未收到结果，不能声称通过。

[固定协议](PROTOCOL.md) · [本地数据sanity](LOCAL_DATA_SANITY.json) · [执行状态](EXECUTION_STATUS.json)

它只检验同一已使用的PCdare真实XYZ作者体表线能否提供缺失深度下的曲线监督。两种固定策略、各三个初始化；20/4/6扫描角色按SHA排序。数字目录仅是来源组代理，不称已核实患者划分。不是SAM微调，不训练椎体或穴位，模型也不是论文创新的既定结论。

源与原始数据仍位于服务器，见[来源资格](../real-back-reference-qualification-v1/README.md)。本包只有代码、协议和本地sanity，不提供不存在的预测图或结果表。

恢复服务器后按顺序执行；先观察实际正向/反向及数据准备是否通过，再启动训练。不要用旧的远端副本：本地修订了数据模块的延迟导入和依赖冻结，需要重新同步整个code目录和协议。

```bash
PY=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
ROOT=/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004
$PY $ROOT/code/test_data.py
$PY $ROOT/code/test_line.py
$PY $ROOT/code/data_line.py --root $ROOT
$PY $ROOT/code/train_line.py --root $ROOT
$PY $ROOT/code/evaluate_line.py --root $ROOT
$PY $ROOT/code/make_figures.py --root $ROOT
```

数据准备单独缓存30扫描及各角色作者曲线；训练入口只读20训练/4开发角色，六个模型均结束后，评价入口才加载6评价角色。先保存216个方法记录与预测哈希，再读取作者曲线评分。失败、覆盖率和共同位置比较均保留。原几何基线的网格处理若在缺失块上实际报错，应先报告并修数据适配，不放宽DP或按效果选病例。

实际服务器环境此前实读：PyTorch2.4.0+cu121、CUDA12.1、2080Ti；这不是本包GPU执行成功的证据。原始扫描、模型权重和患者照片不入Git。

外部PointDG作者源码已获取，commit `dd5099f1261deeebdb7fa25b23a5c78b681739e3`；当前检出的目录没有权重、数据或LICENSE，未运行，也不当作已经复现的比较方法。[作者代码](https://github.com/malongtan/PointDynamicalGraph-Net)。
