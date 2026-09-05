# Docker 数据库备份与恢复演练教程

> 适用于当前 Windows 11 本机第一阶段 Docker 演示版。本工具不覆盖正在使用的数据库，只执行在线备份和隔离恢复验证。

## 一句话操作

1. 保持 Docker Desktop 正常运行。
2. 双击项目根目录的 `Docker_Backup_Restore.cmd`。
3. 输入 `1` 并按回车。
4. 看到 `BACKUP PASSED` 和 `RESTORE DRILL PASSED` 才算成功。

菜单 `1` 会先使用 SQLite 官方在线备份机制生成一致性副本，再把副本恢复到随机命名的临时 Docker 卷中。工具会检查 SQLite 完整性、SHA-256、表清单和记录数量，随后删除它自己创建的临时验证容器和临时卷。

现役数据库卷 `physiotherapy-client_backend-data` 不会被停止、覆盖或删除，网页可以继续使用。

## 菜单说明

| 选项 | 用途 |
|---|---|
| `1` | 新建备份并立即完成隔离恢复演练，推荐日常使用 |
| `2` | 只新建备份 |
| `3` | 使用最新备份重新执行隔离恢复演练 |
| `4` | 查看已有备份、校验清单和演练记录 |
| `0` | 退出 |

## 自动备份

Windows 已配置计划任务 `Physiotherapy Client - Daily Database Backup`，每天 20:00 自动执行在线备份；如果电脑当时不可用，任务会在之后补跑。`Physiotherapy Client - Start Docker at Logon` 会在当前用户登录时启动 Docker Desktop。

两个任务已于 2026-08-11 实际试跑并返回 0；Windows 实际重启后，Docker Desktop 和项目容器已自动恢复。自动任务不会删除旧备份，也不会执行现役数据库覆盖。

## 文件位置

- 双击入口：`Docker_Backup_Restore.cmd`
- 执行脚本：`docker_backup_restore.ps1`
- 数据库备份：`backups\docker-sqlite\physiotherapy-日期时间.db`
- 校验清单：同名 `.db.json` 文件
- 演练记录：`backups\docker-sqlite\restore-drill-日期时间.json`
- 执行日志：`logs\docker-backup-日期时间.log`

备份文件包含账号和业务数据，不能发给别人、上传网盘或提交到 Git。项目 `.gitignore` 已忽略整个 `backups` 目录，但当前工程还不是 Git 仓库。

C、D、E 是同一块物理硬盘上的分区；把备份复制到 D 盘仍不能防止整盘损坏。接入移动硬盘、NAS 或另一台电脑后，还需要补充真正的异盘副本。

## 为什么演练不直接覆盖现役数据库

直接覆盖现役 Docker 卷会停止服务，并有误删当前数据的风险。隔离演练能证明下面的恢复链路真实可用，同时不碰正在运行的数据：

1. 在线生成一致的 SQLite 备份；
2. 将备份复制到新的 Docker 命名卷；
3. 在独立 Python 容器内打开恢复后的数据库；
4. 验证完整性、文件哈希、表和记录数量；
5. 删除本次演练创建的临时容器和临时卷；
6. 保留备份、校验清单和演练记录。

## 真正发生故障时

本工具当前故意不提供“覆盖现役数据库”按钮。真正恢复现役数据前，必须先确认：

- 选中的备份文件和日期正确；
- 已额外保存故障现场副本；
- 后端容器已经停止写入；
- 明确允许覆盖 `physiotherapy-client_backend-data`；
- 恢复后会重新执行健康检查和登录验证。

在这些条件没有全部确认前，不要手工复制数据库到现役卷，也不要执行 `docker compose down -v`。
