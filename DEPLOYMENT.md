# world-scene 的 GitHub Pages 部署

## 地址与分支

- GitHub仓库：https://github.com/river-ya/world-scene
- 网站目标：https://river-ya.github.io/world-scene/
- 站点基础路径：`/world-scene/`
- `main`：保留科研源码，增加 `.github/workflows/pages.yml` 发布工作流。
- `website`：独立保存网页源码、正式视频、字体与架构图。
- 发布工作流从 `website` 分支构建，只发布 `dist/` 内部内容。

本地目录仍为 `worldmodels_baseline`，不需要改名。采用分支隔离是因为科研源码的现有检查禁止MP4与大文件进入源码发布包；没有为网站放宽该检查。

`README.md` 和 `CONTENT_GUIDE.md` 仅保留在本地，由 `.gitignore` 排除，不参与网页构建和后续上传。

## 本次发布记录

2026-11-03已发布：[打开网站](https://river-ya.github.io/world-scene/)。

- 网站构建来源：`website` 分支提交 `1470ce05a9488542a01130954fbab456f59cc8f8`。
- 主分支仅新增发布工作流：`4b1cc7af992d6768be45a40481f2b61f162558f4`，科研源码检查通过。
- [发布工作流运行记录](https://github.com/river-ya/world-scene/actions/runs/41593491566)：构建与部署均成功。
- 首页、案例JSON、31条MP4及两张SVG共35个线上地址均返回HTTP 200。
- Chromium实际播放检查：两种方法各前两个案例选图切换、自动播放与原始文本对应正常；配对视频同步播放、角度切换、两张SVG加载正常。
- 1440、390与320px宽度未出现横向溢出，浏览器未捕获页面脚本错误。本地完整9项浏览器验收也全部通过。

此次发布包含约248 MiB的网站素材。公开仓库的 `website` 分支含网页源码、31条MP4、输入图片、字体、架构图及相关配置，其他人可以查看与下载。PLY/SPZ、模型权重和完整实验目录未纳入网站。

## 本地检查与预览

```bash
cd '/mnt/d/aaaoffice/科研实习/轮转科研项目/项目1/worldmodels_baseline'
python3 -B tools/site.py check
python3 -B tools/site.py build
python3 -B tools/site.py preview
```

打开 http://127.0.0.1:8000/world-scene/ 。Ctrl+C 停止预览；已有服务时重新构建后 Ctrl+F5。构建器检查相对路径、视频体积与基本案例配置。

## 发布更新

在网站目录的 `website` 分支操作，避免把网站文件提交到科研源码的 `main`：

```bash
git branch --show-current
git status --short
# 上一条分支输出应为 website。
python3 -B tools/site.py build
git add src tools tests .github .gitignore requirements-dev.txt DEPLOYMENT.md
git diff --cached --stat
git commit -m 'Update World Scene website'
git push origin website
```

推送本身不自动发布。手动触发主分支上的工作流：

```bash
gh workflow run pages.yml --repo river-ya/world-scene --ref main
gh run list --repo river-ya/world-scene --workflow pages.yml --limit 5
read -r -p '输入本次Actions运行ID：' PAGES_RUN_ID
gh run watch "$PAGES_RUN_ID" --repo river-ya/world-scene --exit-status
```

WSL中若未安装Linux版 `gh`，可在当前终端定义下面的函数，调用现有Windows GitHub CLI：

```bash
gh() { /mnt/d/GitHubCli/gh.exe "$@"; }
```

无需读取或复制令牌。Git推送若需要调用同一份凭据，可以对该次命令显式指定：

```bash
git -c 'credential.helper=!/mnt/d/GitHubCli/gh.exe auth git-credential' push origin website
```

## 实时日志与失败检查

```bash
gh run watch "$PAGES_RUN_ID" --repo river-ya/world-scene --exit-status
gh run view "$PAGES_RUN_ID" --repo river-ya/world-scene --log-failed
gh api repos/river-ya/world-scene/pages --jq '{url: .html_url, status: .status, build_type: .build_type}'
```

只有工作流成功且目标网页能够访问后，才完成上线核验。检查网站、案例配置、SVG和视频，再实际播放确认：

```bash
curl -I https://river-ya.github.io/world-scene/
curl -I https://river-ya.github.io/world-scene/data/cases.json
curl -I https://river-ya.github.io/world-scene/media/architecture/luciddreamer-v0.10.0.svg
curl -I https://river-ya.github.io/world-scene/media/room/video.mp4
```

## 回滚

只回滚 `website` 的网页提交，不回退科研源码主分支：

```bash
git branch --show-current
git status --short
git log --oneline -10
read -r -p '输入要撤销的网页更新提交SHA：' WEBSITE_BAD_COMMIT
git revert "$WEBSITE_BAD_COMMIT"
python3 -B tools/site.py build
git push origin website
gh workflow run pages.yml --repo river-ya/world-scene --ref main
```

针对普通单次更新使用上述方式，多次更新需要检查回退顺序。不要强推或删除原实验结果。

## 限定清理与离线导出

```bash
# 仅清理本站构建与Python缓存，再重建
python3 -B tools/site.py clean
python3 -B tools/site.py build
# 如需导出离线静态文件
tar -czf worldmodels-baseline-static.tar.gz -C dist .
sha256sum worldmodels-baseline-static.tar.gz > worldmodels-baseline-static.tar.gz.sha256
```

复制/下载离线包后，不再需要时仅删除这两个生成文件：

```bash
rm -f -- worldmodels-baseline-static.tar.gz worldmodels-baseline-static.tar.gz.sha256
```

本次部署只处理网站，模型权重、PLY/SPZ、原始运行目录和科研环境没有进入网页分支；不涉及Slurm训练或新视频生成。当前媒体约248 MiB，后续增加视频时再次检查文件体积与托管限制。

## 官方参考

[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[Pages API](https://docs.github.com/en/rest/pages/pages)、[托管限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)。
