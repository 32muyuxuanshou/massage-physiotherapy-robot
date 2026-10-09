# 核心数值表

全部数值由原始 JSON 汇总，未挑 seed 或删失败。真实误差是 subject-equal mean of frame medians / P95，非 pooled median。

## 四组匹配小规模训练

|模型|camera 顶点 mm|去平移顶点 mm|Camera mm|关节camera mm|Depth median mm|Depth hit|trainable|
|---|---|---|---|---|---|---|
|rgb_only|97.687|63.239|75.858|99.847|74.387|0.942|656897|
|cross_attention|108.878|67.247|85.860|111.997|83.030|0.936|1454977|
|geometry_attention|107.492|65.758|86.315|110.374|82.300|0.939|1852545|
|mhr_refinement|83.233|68.232|47.452|86.317|49.269|0.920|2293460|

## 同一232帧真实开发评价

|模型|TRAIN med/P95 mm|VAL med/P95 mm|VAL coverage50|
|---|---|---|---|
|official|53.971 / 119.743|30.586 / 69.835|0.7443|
|official_txyz|24.645 / 80.317|11.226 / 41.604|0.9707|
|rgb_only|44.890 / 108.655|21.310 / 54.510|0.8867|
|cross_attention|48.148 / 113.513|21.583 / 55.923|0.8745|
|geometry_attention|48.661 / 114.859|21.404 / 54.541|0.8691|
|mhr_refinement|34.678 / 94.903|24.352 / 60.460|0.8426|

## 候选机制：合成 VAL 推理干预

|模型|条件|camera 顶点 mm|Camera mm|
|---|---|---|---|
|geometry_attention|correct|107.492|86.315|
|geometry_attention|flat_center|108.272|87.137|
|geometry_attention|lowpass_shape|107.602|86.488|
|geometry_attention|local_shuffle_fixed_mask|107.493|86.314|
|geometry_attention|cross_identity_fixed_mask|108.039|86.839|
|geometry_attention|offset_-0.2|107.498|86.323|
|geometry_attention|offset_0.2|107.495|86.330|
|geometry_attention|missing|157.121|153.357|
|geometry_attention|no_3d_attention_bias|107.096|85.558|
|geometry_attention|no_global_metric_context|107.404|86.242|
|mhr_refinement|correct|83.233|47.452|
|mhr_refinement|flat_center|105.953|79.387|
|mhr_refinement|lowpass_shape|85.451|50.679|
|mhr_refinement|local_shuffle_fixed_mask|83.233|47.450|
|mhr_refinement|cross_identity_fixed_mask|355.689|347.644|
|mhr_refinement|offset_-0.2|140.100|123.950|
|mhr_refinement|offset_0.2|160.627|151.376|
|mhr_refinement|missing|157.121|153.357|
|mhr_refinement|no_local_correspondence|135.525|123.474|
|mhr_refinement|translation_only|102.840|47.452|
