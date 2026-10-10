# 可恢复资产与备份范围

全部档案在本地 `output/r4_development/private_backup` 及持久服务器 `172.18.6.218:436` 的 `/raid5/xuhd/rgbd_sam3d_backups/2026-10-10_r4_geometry_v1`。SHA在计算端、本地、持久端一致。密码不入库。

|档案|Bytes|SHA256|
|---|---:|---|
|r4_pilot_native_v1.tar.gz|1836848197|`26e57b5fe360d91e19895ca9136531829bed6ed78d9baaf547069293019e45d2`|
|r4_formal_native_v1.tar.gz|2686045965|`caa531e2b878d46f7e17b60f21bc2f838ccf8dd5b03599ecd7e30b9658115c9f`|
|r4_closeout_evidence_v1.tar.gz|1286486362|`6688136addc84940f20f06dcebc729a3a5e87d0408fced429701117e59e26df3`|

- Pilot：G0/G1/G2/G3四个Best/Last、合成与真实native输出、全部消融/物理探针/QA。
- Formal：G0/G1六cell、12个Best/Last、Adam/scheduler/RNG、4800个合成VAL原生预测、1392个真实Mesh NPZ、完整训练/消融/指标。
- Closeout：全部R4 QA及初始失败记录、物理图/缓存、训练与评价日志、相机组件交换、正式图与汇总。该档案形成于最终Git/关机回执之前，最终公开报告以Git为准。

未重新复制原始HuMMan数据、3600张backbone缓存或Official权重进这些三个档案。原数据/权重在AutoDL数据盘保留，Official/MHR持久备份沿用R0回执；恢复训练还需原数据与缓存。公开Git交付不含checkpoint及native大数组。

[12个正式checkpoint逐文件SHA](CHECKPOINT_MANIFEST.json) · [原始R0准备/权重备份](../../real-scene-2026-10-09/rgbd-sam3d-r0/README.md) · [三seed评价器与232实际点集SHA](EVALUATION_ASSET_RECEIPT.json)
