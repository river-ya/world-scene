# 创建 GitHub 仓库与维护公开源码

推荐仓库名：`world-scene`；推荐描述：`Reproducible image-and-text-conditioned 3D scene generation with FlashWorld, LucidDreamer, and controlled camera experiments.`

本目录已经整理为独立公开源码。不要把上一级个人科研文件夹、旧内部 Git bundle、模型缓存或实验结果一起推送。ZIP 与 tar.gz 是同一份源码的两种包装，选择一种即可。

## 1. 选择源码目录

本地已整理目录为 `GitHub发布/world-scene`。如果使用压缩包，先校验摘要并解压，之后进入其顶层 `world_scene-v0.10.1` 目录：

```bash
cd /path/to/downloads
sha256sum -c world_scene-v0.10.1.tar.gz.sha256
tar -xzf world_scene-v0.10.1.tar.gz
cd world_scene-v0.10.1
```

仓库首页应直接看到 README.md、tools/、slurm/ 等，不要再把完整源码套进一个多余的目录上传，也不要只把 ZIP 文件放进仓库。

## 2. 在 GitHub 创建空仓库

创建新仓库后复制 SSH 或 HTTPS 地址。初始化选项里的 README、.gitignore、license 先不勾选，避免与本地已有文件冲突。可先选私有，整理好展示素材与许可后再决定公开；是否公开由维护者选择。

源目录不含密码或认证材料；GitHub 登录使用自己的 SSH key 或系统凭据管理器，不把 token 写进代码和远端 URL。上述初始化流程对应 [GitHub 官方本地代码导入指南](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)。

## 3. 提交并推送

先进入选定的源码根目录执行。自动整理的本地目录若已初始化 Git，则保留它的新公开历史；压缩包不带 `.git`，会新建仓库。`RELEASE.json` 只适用于不可变部署归档：从压缩包转为可编辑 Git 仓库时移除这一份生成的身份文件，源码与配置不删。

```bash
set -euo pipefail
python3 -B tools/check_public.py
if [[ -f RELEASE.json ]]; then rm -- RELEASE.json; fi
if [[ ! -d .git ]]; then git init -b main; fi
read -r -p 'Git 提交署名：' PUBLIC_GIT_NAME
read -r -p 'Git 提交邮箱（可填 GitHub noreply 邮箱）：' PUBLIC_GIT_EMAIL
git config user.name "$PUBLIC_GIT_NAME"
git config user.email "$PUBLIC_GIT_EMAIL"
git add .
git status --short
if ! git diff --cached --quiet; then
  git commit -m 'Publish reproducible world scene research code'
fi
read -r -p '新仓库 SSH 或 HTTPS URL：' PUBLIC_REPO_URL
if git remote get-url origin >/dev/null 2>&1; then
  [[ "$(git remote get-url origin)" == "$PUBLIC_REPO_URL" ]] || {
    echo '已有 origin 指向不同地址，请核对，不自动覆盖。' >&2
    exit 2
  }
else
  git remote add origin "$PUBLIC_REPO_URL"
fi
git push -u origin main
```

若远端已经有自己的提交，先核对远端内容；不要直接 force push。此处没有自动建立或推送远端仓库。

## 4. 发布源码归档与后续修改

仓库用于浏览与协作，GitHub Releases 可另外附源码 ZIP/tar.gz 与 SHA256。不要把数十 GB 权重或大型 PLY/MP4 提交进 Git；GitHub 普通 Git 会阻止超过 100 MiB 的文件，浏览器上传单文件上限更小。见 [官方大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

公开版采用源码快照而非子模块；不要擅自替换 upstream 文件，来源摘要会拒绝变化。更新第三方组件时，应同时维护来源、许可、锁文件和回归验证。自有代码的许可证尚未指定；选择时仅覆盖有权授权的部分，并保留第三方目录例外，见 [LICENSING.md](../LICENSING.md)。

后续开发从本公开目录进行，使用自己的分支和提交；更改运行代码后升级 VERSION 与 configs/versions.lock.json 的 project_version。提交干净后加对应版本标签，再打源码包。首次公开归档版本为 0.8.1；不要覆盖已经发布的同版本包。

```bash
python3 -B tools/check_public.py
python3 -B -m unittest discover -s tests -v
# 完成版本更新和提交后，给当前提交添加对应的、尚不存在的版本标签：
PUBLIC_VERSION=$(tr -d '\r\n' < VERSION)
git tag -a "v$PUBLIC_VERSION" -m "Release v$PUBLIC_VERSION"
python3 -B tools/release.py --output ../release-artifacts
# 确认希望发布该标签后，自行执行：
git push origin "v$PUBLIC_VERSION"
```

已经存在标签时无需重复创建。源码包内含不可变 RELEASE.json；GitHub 仓库不跟踪该生成文件。`.github/workflows/ci.yml` 只执行源码/CPU 及 shell 语法检查，外部图片与 GPU 相关检查可能 skipped，不能以 CI 绿灯宣称 GPU 推理完成。

## 5. 实验展示素材

仓库目前不包含个人实验视频，避免大文件和未审核素材自动公开。后续可单独挑选可展示的短视频或 GIF，记录模型、输入、相机轨迹和实际运行状态，再通过 Release 或专门展示页发布。不要把旧 gallery 与新的纯旋转实验混写成同一协议。


## 当前展示资产

README 包含同条件对照图与 Release 视频/三维样例链接。大型 MP4/SPZ 只放 Release，不进入 Git 历史。原始模型权重沿用作者下载地址。新公开状态见 [结果记录](RESULTS.md)。
