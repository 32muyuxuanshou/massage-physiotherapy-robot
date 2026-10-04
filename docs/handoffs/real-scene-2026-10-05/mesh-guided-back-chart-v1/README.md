# 背部坐标与工程接口对照V1

[最终报告](FINAL_REPORT.md) · [机器结果](RESULTS.json) · [逐人表](PER_SUBJECT_RESULTS.csv) · [协议](PROTOCOL.md) · [缓存核验](CACHE_VERIFICATION.json) · [离线Mesh接口示例](DEMO_S104.html) · [示例PNG](DEMO_S104.png)

结论：固定人体坐标约21.28→20.90 mm，8人改善/8人退化、初始化更差，且近半数目标钳制。当前不作为最终定位。没有训练/SAM/新拟合。

全部20人图在figures；全量输入/曲线/绑定/拓扑缓存及清单在本目录，可运行：

```powershell
python code/replay_delivery.py --root .
```

动态曲线沿用上一交付，其服务器路径/hash保留。原始RGB/权重不入Git。目标JSON不是穴位标签，禁止治疗执行。
