# Cheap Txyz Inference Visualization V1

## 我实际怎么使用

输入一帧已经配准的 `RGB + Depth + K + person mask/ROI`：RGB、K 和 ROI 先进入 Official SAM 3D Body，得到 Official MHR Mesh；Depth、K 和 person mask 反投影成 Camera-A 人体点云；冻结的 Cheap Txyz 用点云与 Mesh 表面估计一个三维平移；最终输出 `V_corrected = V_official + Txyz`、修正前后 Mesh、指标和可视化。

Depth **不进入** SAM3D 神经网络。它只在 Official Mesh 产生以后，用来修正 absolute 3D translation。Txyz 只改变整张 Mesh 的 Tx/Ty/Tz，不改变姿态、旋转、形状、尺度、骨架、面部、手部或任何局部顶点关系。

HuMMan 批量入口使用 `code/run_cheap_txyz_demo.py`。新的单帧数据使用：

```bash
python code/run_custom_rgbd.py \
  --rgb RGB.png --depth DEPTH.png --depth-unit mm \
  --intrinsics K.json --person-mask MASK.png \
  --sam-repo /path/to/sam-3d-body \
  --official /path/to/model.ckpt --mhr /path/to/mhr_model.pt \
  --anchors /path/to/MHR_DETERMINISTIC_SURFACE_ANCHORS_V1.npz \
  --output-dir output_case
```

自定义输入必须满足 `CUSTOM_RGBD_INPUT_CONTRACT_V1.json`。产品运行只需要一台已配准 RGB-D 相机；Camera B 只用于本实验的独立考试。正常运行不需要人工修 Mesh。

## 冻结算法

实际代码审计确认：16,384 个拓扑绑定的 MHR 重心表面锚点；最多 6 轮最近邻匹配；每轮剔除距离最大的 20%；保留对应残差逐轴取中位数；每轮每个分量最多移动 50 mm；总平移范数超过 177.888 mm 时返回未修改的 Official Mesh。Camera 坐标是 OpenCV 的 X 向右、Y 向下、Z 向前，内部 Depth 与 Mesh 都用米。

## Smoke 与完整测试

Smoke 使用 10 帧、4 人、9 个动作/姿态 ID。RGB、Depth 单位、配准、K、Mesh 坐标、Txyz 方向、person mask、统一 0–100 mm heatmap、3D viewer 和 A→B 标定链均通过。1 帧超界并正确回退，Gate 为 `SMOKE_PASS`。

完整工程测试使用 45 帧、7 人、13 个动作/姿态 ID，组合自此前已经消费的 System Sealed 与 Selector Sealed 缓存。没有下载新数据，没有打开原始 15 人 Final Deep Reserve。该组合用于 Demo/工程行为分析，不重新声称独立论文级 sealed benchmark。

## 结果

| 指标（跨帧中位数） | Official | Corrected |
|---|---:|---:|
| Camera A median | 88.17 mm | 25.07 mm |
| Camera A P90 | 169.51 mm | 82.27 mm |
| Camera A P95 | 192.34 mm | 100.01 mm |
| Camera A sparse coverage proxy | 0.772 | 0.748 |
| Camera B median | 58.99 mm | 24.07 mm |
| Camera B P90 | 138.66 mm | 70.60 mm |
| Camera B P95 | 162.94 mm | 88.11 mm |
| Camera B sparse coverage proxy | 0.566 | 0.673 |

Camera A 的改善只作调试证据，因为 A Depth 参与了 correction。A 的稀疏 coverage proxy 从 0.772 降到 0.748，说明平移降低距离时不保证所有投影覆盖同时增加。Camera B 没有参与推理、平移估计或选择，所以 B 的改善更可信：37/45 帧改善，0 帧退化，8 帧超界后与 Official 完全相同。这里的 coverage 是统一稀疏深度渲染可视化代理；历史 36 帧 exact coverage 结果仍以旧 handoff 为准。

Txyz 统计：Tx 中位数/P90 为 `+11.01/+18.00 mm`；Ty 为 `-28.75/+7.53 mm`；Tz 为 `-80.95/+4.17 mm`；原始 `|T|` 为 `94.22/207.90 mm`。P90 超过总界限，是因为统计保留了超界原始建议值；这些帧实际应用 0 mm 并回退。主要修正方向是负 Z，其次负 Y。

2080 Ti 上 Official 中位运行时间约 `351.1 ms`，Cheap Txyz `109.9 ms`，两者合计 `462.3 ms`。计时不含文件解码、可视化和 Camera-B 评价。

## 怎么看可视化
打开 `CHEAP_TXYZ_VISUAL_REPORT_V1.html`。每帧包含同设置的 Official/Corrected RGB overlay、Camera-A 统一色标残差、Camera-B held-out 残差、Txyz 数值和可旋转 `3d_viewer.html`。灰色是观察点云，红色是 Official，蓝色是 Corrected，可分别开关。

- BEST：`p000838_a000084_f000023`，|T| 156.24 mm，Camera-B median 102.29→23.15 mm。
- NORMAL：`p000891_a001199_f000040`，|T| 14.19 mm，Camera-B median 17.25→16.58 mm。
- FAILURE/LIMIT：`p000838_a000017_f000008`，整体位置明显改善但 Camera-B median 仍有 34.84 mm，说明只做 translation 无法修复内部姿态/表面误差。

每个 case 都保留图片、metrics 与 3D viewer。为控制 Git 体积，所有 45 帧保留可视化；三个代表案例同时保留完整 OBJ/MHR 参数，其余 Mesh 可由冻结命令和 manifest 确定性重建。

## 工程问答

1. 实际输入：`RGB、Depth、K、person mask/ROI`。
2. Depth 不进入 SAM3D 网络，在 Official Mesh 后计算 Txyz。
3. Txyz 只给全部顶点加同一个三维向量，其余人体参数不变。
4. 它能改善 absolute placement，因为 RGB 单目深度/相机平移存在尺度与绝对位置歧义，而同相机 Depth 直接观察到了米制表面。
5. 本批主要修正 Z，一般原始移动中位数约 94 mm；超过 177.888 mm 不应用。
6. 本批没有“应用后 B 变差”的帧；8 帧被 fallback 保护。不能据此保证未来域零退化。
7. 困难弯腰、扭转、支撑和四肢/躯干姿态错误只能搬准整体，局部仍可能不贴。
8. 产品不需要 Camera B，也不需要人工逐帧修 Mesh。
9. 视频中人体和相机不动时可复用/低频重算 Txyz；发生运动、深度覆盖变化或跟踪置信度下降时重算。当前独立单帧实现每帧可重算。
10. Depth 缺失、有效点不足、低覆盖、无效相机/配准、数值失败或平移超界时应 fallback；明显配准错误、多人 mask 混入、强遮挡或 Depth 大面积空洞时应重新采集。
11. 本流程不需要 Adapted/Selector 即可运行；本批 Official+C 的 held-out 结果支持继续测试 C，但没有验证产品域。
12. 本次完全没有 DMD37，因为这里只回答 Mesh 的 absolute 3D placement 是否能由 Depth 后处理改善。

## 边界与下一步

Final Gate：`PASS_CHEAP_TXYZ_INFERENCE_VISUALIZATION`。这个 PASS 表示单帧流程、可视化、冻结 Txyz 与 Camera-B 独立评价已经可复现；不表示治疗床、裸背、按摩机器人遮挡、产品相机噪声或医学点位已经验证。状态保持 `TARGET_DOMAIN_NOT_VALIDATED`。

下一步唯一建议：冻结现有 Txyz，不再在 HuMMan 调参，直接采集一小批产品 RGB-D 数据，包含治疗床、裸背/衣物、侧卧/俯卧/坐姿、机器人或治疗师遮挡以及真实传感器噪声；同样保留独立 Camera B 或其他几何真值用于评价。


