# CT解剖参考来源 V1：完成

实际下载作者 TotalSegmentator small v2.0.1：102例、3.2446 GB，MD5与作者一致。原始CT留在172.18.18.151，位置 `/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005/raw`。

用CT本身的外边界生成后侧高度图，骨标签只用于生成参考答案。102例全部处理、17页全量图全部查看。一例倾斜CT按物理坐标重采样；一例s1373的C7标签明显逆序，保留原记录，在后续训练前排除整例，不人工改标签。

|等级|存在标签|未接触原扫描边界|中心定义与后侧极值定义的纵向差异中位/mm|
|---|---:|---:|---:|
|C7|78|24|4.5|
|T3|78|78|4.5|
|T5|79|78|15.0|
|T9|92|86|21.0|
|L2|87|69|15.0|

**这份数据新增了外表面与内部解剖之间的对应证据，仍不是俯卧或穴位真值。**同一节椎骨的标签中心和后侧极值，投到表面的水平也能差十几毫米，不能混用作“某节棘突下凹陷”。有标签也不代表标签都正确。

下一项已单独注册：只看外表面，定位五个椎骨代理水平，比较固定训练中位位置、全局回归、独立热图、有序查询。预先分配角色并过滤源资格后：51训练、11开发、12测试、4作者val支持。病例ID数量不另称独立病人数；测试不是作者官方benchmark。

可复查文件：`DOWNLOAD_RESULT.json`、`ALL_SOURCE_QUALIFICATION.json`、`SOURCE_QUALIFICATION.csv`、`SOURCE_VISUAL_REVIEW.json`及`montages/`。源包解压/物理单位/标签投影均在`code/`，训练结果属于相邻`ct-anatomical-query-pilot-v1`目录。

来源与派生归属：[作者102例小包](https://zenodo.org/records/10047263)，Jakob Wasserthal / University Hospital Basel，CC BY 4.0；本项目另做HU外表面和骨标签投影，修改已明确记录。[作者论文](https://doi.org/10.1148/ryai.230024)。
