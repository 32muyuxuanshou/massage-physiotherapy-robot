# 当前知识状态核对

仅同步本轮影响的入口与交付，不做仓库其它功能整改。

| 事实面 | 状态 | 本次证据/处理 |
|---|---|---|
| 三项实验代码/结果 | verified-current | 各包独立缓存核验、FILES_MANIFEST；本次1169 Git blob逐字节核验通过 |
| 新曲线学习代码 | pending GPU execution | 语法/解析XYZ数据sanity通过；模型正向、训练、真实评价未完成 |
| 运行态 | completed outputs + storage pending | 三阶段已实际运行，随后服务器可登录但既有数据目录不可见；最终镜像同步尚未完成 |
| 人类文档 | changed-and-verified | 更新根README、AI模块入口、CURRENT_STATUS、交付目录；运行与医学边界分清 |
| Agent规则 | verified-current, unchanged | 根AGENTS偏好最小改动；没有改split、噪声实现、网格或旧基线；新学习试验单独立项 |
| 生成记忆 | out-of-scope / read-only | 未写宿主生成记忆；项目事实写入docs |
| 工作区 | scoped delivery; unrelated work preserved | 用户讲稿修改及其它未跟踪实验保持原样；不是全仓库clean，不清除复核现场 |

服务器最终审查镜像与原型训练需既有存储恢复；不会把Git已推送描述为服务器运行完成。全部历史目录、原始数据和用户现场未清理，没有待执行的删除操作。
