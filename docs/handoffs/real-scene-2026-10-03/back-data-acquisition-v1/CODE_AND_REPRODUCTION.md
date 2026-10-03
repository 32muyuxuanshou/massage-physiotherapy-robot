# 已执行代码与复查

本包 `code/` 保存本轮实际执行的获取与审计脚本副本。依赖沿用服务器既有 Python 环境，不新增训练环境。

| 脚本 | 本轮实际作用 |
|---|---|
| `prepare_pcdare_selection.py` | 使用本地已登录 GitHub CLI 读取固定 commit 的文件树，生成选定文件清单；不读取或打印 token |
| `acquire_pcdare.py` | 服务器 shallow clone + sparse checkout；逐选定文件核对字节数、Git blob SHA1，记录 SHA256 |
| `acquire_small_assets.py` | 服务器下载当前 DMD V2、读取 ZIP 实际条目；确认仅有声明 |
| `inspect_dmd_archive.py` | 通过公开 V1 接口与 HTTP Range 枚举 ZIP 文件目录；不保存临时签名下载地址 |
| `download_dmd_pilot.py` | 依据枚举清单选定并下载 205 组真实图片/JSON，ZIP CRC 校验与 SHA256 记录 |
| `audit_acquired_assets.py` | 全部 504 PLY/相关 JSON 与全部 205 图片的结构检查，生成对照页 |

脚本内默认资产根目录为 `/raid5/xuhd/datasets/back_prone_acquisition_20261003`。本轮所用 Python 为 `/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python`。

服务器已有下载证据与输出时，可独立重做读取检查：

```bash
cd /raid5/xuhd/datasets/back_prone_acquisition_20261003
/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python back-data-acquisition-v1/code/audit_acquired_assets.py
```

这条命令只重新生成本轮 `quality_audit/`，不训练、推理、拟合或改写原数据。若重新下载，请先检查 `source_metadata/dmd_bak_metadata.json`、`PCDARE_SELECTION.json` 与 `dmd_bak/VERSION1_REMOTE_INVENTORY.json`，并使用新的采集目录，保留本轮证据。PCdare 下载器会核对固定 commit；DMD 的未来公开可用性不由本轮保证。

`FILES_MANIFEST.json` 记录本交付文件的 SHA256，自身不纳入递归哈希。它用于交付核对，不代表模型实验的运行时冻结 Gate。数据完整解码、标签质量合格、模型实验完成三种状态分别记录，不能相互替代。
