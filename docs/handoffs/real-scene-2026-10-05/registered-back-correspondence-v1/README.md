# 注册后背对应机制：完整交付

[最终报告](FINAL_REPORT.md) · [主结果](RESULTS.json) · [逐来源](PER_SOURCE_RESULTS.csv) · [协议](PROTOCOL.md) · [作者强参考](AUTHOR_BASELINE_RESULTS.json) · [查询阶段](query-stage-v1/RESULTS.json) · [缓存复查](CACHE_VERIFICATION.json) · [数据库存](DATA_INVENTORY.json)

实际完成9个身份场模型+6个query模型，1800+1080评价；原始/带几何的缓存与权重在服务器，不入Git。单位面积对应误差不是穴位mm精度。临床/部署未放行。所有20来源图在figures；运行脚本在code。

服务器根：/raid5/xuhd/datasets/registered_human_correspondence_20261005。环境：原SAM研究venv，作者DiffusionNet新增依赖仅根目录author_deps（robust-laplacian1.0.0、potpourri3d1.3、sklearn1.6.1、joblib1.5.2、threadpoolctl3.6.0），不改现有venv。
