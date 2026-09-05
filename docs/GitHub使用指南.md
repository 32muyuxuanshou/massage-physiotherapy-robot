# Git 与 GitHub 使用指南

## 当前准备情况

- 项目根目录已初始化为 Git 仓库，主分支为 `main`。
- 已配置 `.gitignore` 与 `.gitattributes`，两个官网 ZIP 已展开为可追踪源码。
- GitHub CLI 已安装。本机首次使用需完成 `gh auth login --web` 授权。
- 远程仓库地址、首次推送和交付链接须在账号授权与访问范围确定后完成；本说明不代表已上传。

以下命令在项目根目录的 PowerShell 运行。新安装 CLI 后请重新打开终端；若 `gh` 未识别，
可使用 `& 'C:/Program Files/GitHub CLI/gh.exe'` 替代 `gh`。

## 保存一个版本

```powershell
git status
git diff
git add -- '实际修改的文件或目录'
git commit -m '说明这次修改的内容'
git push
```

`commit` 在本机保存版本，`push` 上传已提交的版本；未提交的修改不会自动备份。
每完成一个可用阶段就提交一次。也可直接让开发助手“检查改动并提交、推送”。

## 查看和回退

```powershell
git log --oneline -15
git show 提交编号
```

撤销一个已提交的修改并保留完整历史：先保存当前工作，再执行：

```powershell
git revert 提交编号
git push
```

仅恢复指定文件到某个历史版本（会覆盖该文件当前内容，先提交需要保留的改动）：

```powershell
git restore --source=提交编号 -- '文件路径'
git add -- '文件路径'
git commit -m '恢复指定文件到历史版本'
git push
```

首次导入前的历史无法重建；Git 只能恢复已经提交过的内容。被 `.gitignore` 排除的资源需单独备份。

## 分支开发

```powershell
git switch -c feature/功能名称
# 修改、验证、提交后
git push -u origin HEAD
gh pr create
```

## 上传交付文件

小型 Markdown、图片、PDF 可放入 `deliverables/`，正常提交并推送。
安装包、视频和较大的 PPTX 通过 Releases 单独上传，避免反复进入源码历史。

在远程已有相应提交和标签时，以下示例创建一个待检查的交付草稿：

```powershell
git tag -a v0.1.0 -m '第一版交付'
git push origin v0.1.0
gh release create v0.1.0 --verify-tag --draft --title '第一版交付' --notes '本次交付内容与使用说明'
gh release upload v0.1.0 '交付文件的完整路径'
gh release view v0.1.0 --web
```

检查草稿附件后，在网页点击 Publish release 发布。不要重复创建已有标签。
每个 Release 附件须小于 2 GiB。私有仓库的交付文件需要访问者有仓库读取权限。
若源码私有但部分交付物要公开，可用独立公开交付仓库，明确挑选要发布的文件。

## 网页查看

- GitHub 仓库页面可查看 Markdown、图片、PDF 与源代码。
- PPTX、DOCX 和 ZIP 应提供下载；需要在线阅读的文稿可同时提供 PDF。
- HTML 在仓库中主要以源码呈现；需要完整网页体验时，需另配 GitHub Pages 等静态托管。
- 私有仓库需给查看者添加访问权限；仅有链接并不等于有权限。
- AI 网页端读取私有仓库需在该网页端连接 GitHub 并授权仓库；本机 CLI 登录不会自动完成此连接。

## 让 ChatGPT 等 AI 网页端读取项目

本项目选择公开源码与可公开交付资料。远程创建完成后，给 AI 提供仓库链接，并让它先读
根目录 `README.md`、`AI感知模块/README.md` 和 `deliverables/README.md`。
公开链接是否能直接读取，取决于该 AI 网页端的浏览工具；不会仅因公开就自动索引全部文件。

ChatGPT 网页端可在 Plugins（插件）入口搜索并安装 GitHub，按提示连接账号和授权仓库，
然后新建对话使用该插件。该连接独立于本机 GitHub CLI 登录。
官方说明：[Plugins](https://learn.chatgpt.com/docs/plugins)。

可复制的请求示例：

> 请使用 GitHub 读取这个项目：粘贴仓库链接。先读 README.md、AI感知模块/README.md、
> deliverables/README.md，再根据我的问题查看具体源码或交付文件。请说明实际读取的分支与文件，
> 对未能读取的附件明确说明，不要仅根据文件名推断内容。

为 AI 阅读优先提供 Markdown 或纯文本说明；PPTX、安装包等二进制附件是否能解析取决于网页端能力。
不需要为此启用 GitHub Pages。

官方说明：[文件预览](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files)、
[Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)、
[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages)。
