# 完整逐seed结果

真实指标为独立Camera B可见表面距离；下面的median/P95是既定层级等权汇总，不是所有点混在一起的分位数。

|组别|seed|native GT Camera mm|真实VAL raw median/P95 mm|真实VAL +Txyz median/P95 mm|fallback /232|
|---|---:|---:|---:|---:|---:|
|continuation/mixed|11|29.620|45.081/106.661|37.937/93.116|0|
|continuation/mixed|23|30.828|34.194/81.339|24.082/67.368|0|
|continuation/mixed|37|30.445|33.667/78.468|22.860/62.857|0|
|continuation/native_only|11|29.997|57.349/157.322|50.237/133.278|1|
|continuation/native_only|23|31.282|46.206/111.265|33.155/90.021|0|
|continuation/native_only|37|30.661|41.500/100.781|33.967/91.669|0|
|native/metric_xyz|11|32.316|56.261/148.962|49.902/130.081|0|
|native/metric_xyz|23|33.628|40.018/100.176|28.933/82.232|0|
|native/metric_xyz|37|32.607|39.771/94.828|31.791/85.029|0|
|native/raw_bounded|11|32.712|48.872/116.264|41.285/100.750|0|
|native/raw_bounded|23|33.536|30.099/76.391|23.511/68.306|8|
|native/raw_bounded|37|33.414|43.201/108.586|38.467/103.050|0|
|native/rgb_only_xyz|11|75.252|87.320/175.918|52.282/129.202|33|
|native/rgb_only_xyz|23|75.859|103.752/197.022|87.661/172.395|68|
|native/rgb_only_xyz|37|76.817|80.411/164.756|44.296/115.237|45|

Official +Txyz：VAL {'median_mm': 11.226246945551962, 'p95_mm': 41.604291887991444, 'coverage_50mm': 0.9707183837890625}; fallback 11/232。确定性Official只计算一次，不把复制到3个seed表当3次独立推理。

所有15个cell各232帧完整保留。逐帧配对见PAIRED_FRAMES.json；逐人见PAIRED_IDENTITIES.json；11个历史fallback逐模型见OFFICIAL_FALLBACK_AUDIT.json。
