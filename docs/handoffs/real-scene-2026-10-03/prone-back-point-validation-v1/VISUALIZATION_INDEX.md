# 全量可视化索引

105 页全部预测图均由最终缓存生成，不含原始 RGB。可看模型形状/点位变化，不能单凭这些白底图判断图像对齐。

颜色：紫色面/绿色轮廓是预测，不是数据集真值；旧点名仅为语义 HOLD 的回归标识。

[旧 canonical 审计](figures/canonical_seed_audit.jpg) · [新工程 proxy 候选](figures/candidate_proxy_review.png) · [逐人独立机位结果](figures/per_subject_posterior_distance.png)

完整原图叠加保留在本地及服务器：

- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p1_cached_transfer/visualizations/`（60 页）
- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p2_behave_crossview/private_rgb_review/`（45 页）
- 服务器 `/raid5/xuhd/datasets/prone_back_point_validation_20261003/` 下对应目录。

## PressurePose：20 人 × 3 seeds

| 人物/种子 | 缓存预测与点位图 |
|---|---|
| S103 / seed 0 | [图](figures/p1/S103/seed_0.jpg) |
| S103 / seed 1 | [图](figures/p1/S103/seed_1.jpg) |
| S103 / seed 2 | [图](figures/p1/S103/seed_2.jpg) |
| S104 / seed 0 | [图](figures/p1/S104/seed_0.jpg) |
| S104 / seed 1 | [图](figures/p1/S104/seed_1.jpg) |
| S104 / seed 2 | [图](figures/p1/S104/seed_2.jpg) |
| S107 / seed 0 | [图](figures/p1/S107/seed_0.jpg) |
| S107 / seed 1 | [图](figures/p1/S107/seed_1.jpg) |
| S107 / seed 2 | [图](figures/p1/S107/seed_2.jpg) |
| S114 / seed 0 | [图](figures/p1/S114/seed_0.jpg) |
| S114 / seed 1 | [图](figures/p1/S114/seed_1.jpg) |
| S114 / seed 2 | [图](figures/p1/S114/seed_2.jpg) |
| S118 / seed 0 | [图](figures/p1/S118/seed_0.jpg) |
| S118 / seed 1 | [图](figures/p1/S118/seed_1.jpg) |
| S118 / seed 2 | [图](figures/p1/S118/seed_2.jpg) |
| S121 / seed 0 | [图](figures/p1/S121/seed_0.jpg) |
| S121 / seed 1 | [图](figures/p1/S121/seed_1.jpg) |
| S121 / seed 2 | [图](figures/p1/S121/seed_2.jpg) |
| S130 / seed 0 | [图](figures/p1/S130/seed_0.jpg) |
| S130 / seed 1 | [图](figures/p1/S130/seed_1.jpg) |
| S130 / seed 2 | [图](figures/p1/S130/seed_2.jpg) |
| S134 / seed 0 | [图](figures/p1/S134/seed_0.jpg) |
| S134 / seed 1 | [图](figures/p1/S134/seed_1.jpg) |
| S134 / seed 2 | [图](figures/p1/S134/seed_2.jpg) |
| S140 / seed 0 | [图](figures/p1/S140/seed_0.jpg) |
| S140 / seed 1 | [图](figures/p1/S140/seed_1.jpg) |
| S140 / seed 2 | [图](figures/p1/S140/seed_2.jpg) |
| S141 / seed 0 | [图](figures/p1/S141/seed_0.jpg) |
| S141 / seed 1 | [图](figures/p1/S141/seed_1.jpg) |
| S141 / seed 2 | [图](figures/p1/S141/seed_2.jpg) |
| S145 / seed 0 | [图](figures/p1/S145/seed_0.jpg) |
| S145 / seed 1 | [图](figures/p1/S145/seed_1.jpg) |
| S145 / seed 2 | [图](figures/p1/S145/seed_2.jpg) |
| S151 / seed 0 | [图](figures/p1/S151/seed_0.jpg) |
| S151 / seed 1 | [图](figures/p1/S151/seed_1.jpg) |
| S151 / seed 2 | [图](figures/p1/S151/seed_2.jpg) |
| S163 / seed 0 | [图](figures/p1/S163/seed_0.jpg) |
| S163 / seed 1 | [图](figures/p1/S163/seed_1.jpg) |
| S163 / seed 2 | [图](figures/p1/S163/seed_2.jpg) |
| S165 / seed 0 | [图](figures/p1/S165/seed_0.jpg) |
| S165 / seed 1 | [图](figures/p1/S165/seed_1.jpg) |
| S165 / seed 2 | [图](figures/p1/S165/seed_2.jpg) |
| S170 / seed 0 | [图](figures/p1/S170/seed_0.jpg) |
| S170 / seed 1 | [图](figures/p1/S170/seed_1.jpg) |
| S170 / seed 2 | [图](figures/p1/S170/seed_2.jpg) |
| S179 / seed 0 | [图](figures/p1/S179/seed_0.jpg) |
| S179 / seed 1 | [图](figures/p1/S179/seed_1.jpg) |
| S179 / seed 2 | [图](figures/p1/S179/seed_2.jpg) |
| S184 / seed 0 | [图](figures/p1/S184/seed_0.jpg) |
| S184 / seed 1 | [图](figures/p1/S184/seed_1.jpg) |
| S184 / seed 2 | [图](figures/p1/S184/seed_2.jpg) |
| S187 / seed 0 | [图](figures/p1/S187/seed_0.jpg) |
| S187 / seed 1 | [图](figures/p1/S187/seed_1.jpg) |
| S187 / seed 2 | [图](figures/p1/S187/seed_2.jpg) |
| S188 / seed 0 | [图](figures/p1/S188/seed_0.jpg) |
| S188 / seed 1 | [图](figures/p1/S188/seed_1.jpg) |
| S188 / seed 2 | [图](figures/p1/S188/seed_2.jpg) |
| S196 / seed 0 | [图](figures/p1/S196/seed_0.jpg) |
| S196 / seed 1 | [图](figures/p1/S196/seed_1.jpg) |
| S196 / seed 2 | [图](figures/p1/S196/seed_2.jpg) |

## BEHAVE：固定全部 45 帧

无可用后背参考的 17 帧也保留，不按好坏筛图。有效 ROI/评价见逐相机表；原图的青色小块是冻结参考区域。

| sequence/timestamp | 五方法 × 四相机预测图 |
|---|---|
| Date03_Sub03_backpack_back / t0014.000 | [图](figures/p2/Date03_Sub03_backpack_back/t0014.000.jpg) |
| Date03_Sub03_backpack_back / t0026.000 | [图](figures/p2/Date03_Sub03_backpack_back/t0026.000.jpg) |
| Date03_Sub03_backpack_back / t0036.000 | [图](figures/p2/Date03_Sub03_backpack_back/t0036.000.jpg) |
| Date03_Sub03_stool_sit / t0015.000 | [图](figures/p2/Date03_Sub03_stool_sit/t0015.000.jpg) |
| Date03_Sub03_stool_sit / t0027.000 | [图](figures/p2/Date03_Sub03_stool_sit/t0027.000.jpg) |
| Date03_Sub03_stool_sit / t0038.000 | [图](figures/p2/Date03_Sub03_stool_sit/t0038.000.jpg) |
| Date03_Sub03_yogaball_play / t0014.000 | [图](figures/p2/Date03_Sub03_yogaball_play/t0014.000.jpg) |
| Date03_Sub03_yogaball_play / t0025.000 | [图](figures/p2/Date03_Sub03_yogaball_play/t0025.000.jpg) |
| Date03_Sub03_yogaball_play / t0036.000 | [图](figures/p2/Date03_Sub03_yogaball_play/t0036.000.jpg) |
| Date03_Sub04_backpack_back / t0015.000 | [图](figures/p2/Date03_Sub04_backpack_back/t0015.000.jpg) |
| Date03_Sub04_backpack_back / t0026.000 | [图](figures/p2/Date03_Sub04_backpack_back/t0026.000.jpg) |
| Date03_Sub04_backpack_back / t0037.000 | [图](figures/p2/Date03_Sub04_backpack_back/t0037.000.jpg) |
| Date03_Sub04_stool_sit / t0015.000 | [图](figures/p2/Date03_Sub04_stool_sit/t0015.000.jpg) |
| Date03_Sub04_stool_sit / t0027.000 | [图](figures/p2/Date03_Sub04_stool_sit/t0027.000.jpg) |
| Date03_Sub04_stool_sit / t0038.000 | [图](figures/p2/Date03_Sub04_stool_sit/t0038.000.jpg) |
| Date03_Sub04_yogaball_play / t0010.000 | [图](figures/p2/Date03_Sub04_yogaball_play/t0010.000.jpg) |
| Date03_Sub04_yogaball_play / t0022.000 | [图](figures/p2/Date03_Sub04_yogaball_play/t0022.000.jpg) |
| Date03_Sub04_yogaball_play / t0034.000 | [图](figures/p2/Date03_Sub04_yogaball_play/t0034.000.jpg) |
| Date03_Sub05_backpack / t0035.000 | [图](figures/p2/Date03_Sub05_backpack/t0035.000.jpg) |
| Date03_Sub05_backpack / t0070.000 | [图](figures/p2/Date03_Sub05_backpack/t0070.000.jpg) |
| Date03_Sub05_backpack / t0101.000 | [图](figures/p2/Date03_Sub05_backpack/t0101.000.jpg) |
| Date03_Sub05_stool / t0019.000 | [图](figures/p2/Date03_Sub05_stool/t0019.000.jpg) |
| Date03_Sub05_stool / t0035.000 | [图](figures/p2/Date03_Sub05_stool/t0035.000.jpg) |
| Date03_Sub05_stool / t0050.000 | [图](figures/p2/Date03_Sub05_stool/t0050.000.jpg) |
| Date03_Sub05_yogaball / t0019.000 | [图](figures/p2/Date03_Sub05_yogaball/t0019.000.jpg) |
| Date03_Sub05_yogaball / t0035.000 | [图](figures/p2/Date03_Sub05_yogaball/t0035.000.jpg) |
| Date03_Sub05_yogaball / t0051.000 | [图](figures/p2/Date03_Sub05_yogaball/t0051.000.jpg) |
| Date05_Sub06_backpack_back / t0015.000 | [图](figures/p2/Date05_Sub06_backpack_back/t0015.000.jpg) |
| Date05_Sub06_backpack_back / t0026.000 | [图](figures/p2/Date05_Sub06_backpack_back/t0026.000.jpg) |
| Date05_Sub06_backpack_back / t0038.000 | [图](figures/p2/Date05_Sub06_backpack_back/t0038.000.jpg) |
| Date05_Sub06_stool_sit / t0015.000 | [图](figures/p2/Date05_Sub06_stool_sit/t0015.000.jpg) |
| Date05_Sub06_stool_sit / t0027.000 | [图](figures/p2/Date05_Sub06_stool_sit/t0027.000.jpg) |
| Date05_Sub06_stool_sit / t0038.000 | [图](figures/p2/Date05_Sub06_stool_sit/t0038.000.jpg) |
| Date05_Sub06_yogaball_play / t0012.000 | [图](figures/p2/Date05_Sub06_yogaball_play/t0012.000.jpg) |
| Date05_Sub06_yogaball_play / t0024.000 | [图](figures/p2/Date05_Sub06_yogaball_play/t0024.000.jpg) |
| Date05_Sub06_yogaball_play / t0034.000 | [图](figures/p2/Date05_Sub06_yogaball_play/t0034.000.jpg) |
| Date06_Sub07_backpack_back / t0015.000 | [图](figures/p2/Date06_Sub07_backpack_back/t0015.000.jpg) |
| Date06_Sub07_backpack_back / t0027.000 | [图](figures/p2/Date06_Sub07_backpack_back/t0027.000.jpg) |
| Date06_Sub07_backpack_back / t0039.000 | [图](figures/p2/Date06_Sub07_backpack_back/t0039.000.jpg) |
| Date06_Sub07_stool_sit / t0015.000 | [图](figures/p2/Date06_Sub07_stool_sit/t0015.000.jpg) |
| Date06_Sub07_stool_sit / t0027.000 | [图](figures/p2/Date06_Sub07_stool_sit/t0027.000.jpg) |
| Date06_Sub07_stool_sit / t0038.000 | [图](figures/p2/Date06_Sub07_stool_sit/t0038.000.jpg) |
| Date06_Sub07_yogaball_play / t0017.000 | [图](figures/p2/Date06_Sub07_yogaball_play/t0017.000.jpg) |
| Date06_Sub07_yogaball_play / t0028.000 | [图](figures/p2/Date06_Sub07_yogaball_play/t0028.000.jpg) |
| Date06_Sub07_yogaball_play / t0039.000 | [图](figures/p2/Date06_Sub07_yogaball_play/t0039.000.jpg) |
