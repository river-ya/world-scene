> 历史实验文档：个人部署信息已替换为示例值。公开版实际操作以 [SLURM.md](SLURM.md) 为准，旧版本命令不应直接复制到新版目录。

# v0.1.3 Slurm 复现执行指南

适用单图＋文本室内三维生成；固定 FlashWorld 官方推理。以下是实际脚本对应的命令。GPU 环境、4090 用量和渲染结果尚未实测。主机 `your.cluster.example` 可达，当前自动执行环境 SSH 认证失败；用户在自己的终端登录执行即可，无需发送密码或私钥。

已完成 v0.1.1/v0.1.2 环境安装的用户，请先按 [离线加载修复与升级指南](v0.1.3离线加载修复与升级.md) 导入新源码并复用已有环境，不必重新下载模型或安装依赖。

## 1. 本地下载、完整校验与发布包

在 WSL/Linux 项目根目录执行。下载总量约 56.36 GB（十进制），除资产外另留环境、编译、结果空间；建议集群至少 120 GB 可用，按实际试验量增加。网络断开后原命令续传；`.part` 是有用断点，不视为已完成文件，也不随意删除。只运行一个下载进程。

```bash
cd /path/to/project
cat AGENTS.md
python3 -B world_scene/tools/assets.py status --root world_scene_assets --group all
# 若尚未完成且没有其他下载进程，继续下载：
python3 -B world_scene/tools/assets.py download --root world_scene_assets --group all --workers 3
python3 -B world_scene/tools/assets.py verify --root world_scene_assets --group all
python3 -B world_scene/tools/data.py --root world_scene_assets
cd 交付包
sha256sum -c world_scene-v0.1.3.tar.gz.sha256
```

源码包不含大模型和原始数据，两者分开传输。源码包已经包含固定上游源码，不需在集群重新拉取 Git 子模块。

## 2. 登录与导入新文件

端口采用 SSH 默认 22；如果集群实际配置改变，统一修改下列 `-p 22`。首次登录核对学校/管理员提供的主机指纹。不要将密码、私钥、Hugging Face token 写入版本库或聊天。

```bash
ssh -p 22 your_user@your.cluster.example
```

以下上传命令在本地 WSL/Linux 另一个终端执行，保留符号链接并支持断点；不带 `--delete`，不删除远端旧成果。避开正在运行的模型版本切换缓存。

```bash
cd /path/to/project
ssh -p 22 your_user@your.cluster.example 'mkdir -p /shared/your_user/releases /shared/your_user/world_scene_assets'
rsync -av --partial --progress -e 'ssh -p 22' \
  交付包/world_scene-v0.1.3.tar.gz 交付包/world_scene-v0.1.3.tar.gz.sha256 \
  your_user@your.cluster.example:/shared/your_user/releases/
rsync -av --partial --progress --exclude='*.part' --exclude='.download.lock' --exclude='ssh_known_hosts' -e 'ssh -p 22' \
  world_scene_assets/ your_user@your.cluster.example:/shared/your_user/world_scene_assets/
```

在集群登录终端执行。新版本必须解包到新目录，不能覆盖正在执行的代码。

```bash
cd /shared/your_user/releases
sha256sum -c world_scene-v0.1.3.tar.gz.sha256
# 仅首次解包；若目录已存在，先使用下方 inspect 核对，不覆盖。
if [ ! -e world_scene-v0.1.3 ]; then
  tar -xzf world_scene-v0.1.3.tar.gz
fi
cd world_scene-v0.1.3
python3 -B tools/experiment.py inspect
source slurm/config.sh
sinfo -N -n GPU1 -o '%N %P %G %m %t'
squeue -u "$USER"
df -h "$DATA_ROOT"
python3 -B tools/assets.py verify --root "$SCENE_ASSETS" --group all
```

如果仅上传代码，也可在集群联网且允许下载的登录/传输节点执行第 1 节下载命令，将 `--root` 改为 `"$SCENE_ASSETS"`。不在 GPU 排队时间内下载。缓存复制后必须完整校验，以生成匹配本机时间戳的回执。

## 3. 队列与依赖环境

默认配置来自此前集群指南：节点 `GPU1`，分区 `debug`，账户 `stu`，QOS `normal`。GPU1 不是 GPU 型号；实际卡必须由 `nvidia-smi` 确认是 RTX 4090。每个任务申请一张卡、8 CPU、96 GB 主存，使用 T5/VAE CPU 卸载；4 个并发任务需要 384 GiB 主存。用户提供的 GPU1 总主存约 241.7 GiB，即使空闲也无法同时运行四个 96G 任务；数组的 `%4` 只是并发上限。check 不加载模型，下面单独覆盖为 16G、4 CPU、MAX_JOBS=2；此配置尚待 GPU 实测。没有足够主存时会排队，应先完成单卡 smoke。

若 `sinfo` 显示配置不同，在仓库根目录 `local.env` 中记录实际参数，再重新 `source slurm/config.sh`。不能根据未知配置直接猜分区。以下只是自定义配置格式示例，默认无需创建。

```bash
# local.env 示例：必须填写管理员确认的实际值后再使用。
# export DATA_ROOT=/shared/your_user
# export PARTITION=debug
# export NODE=GPU1
# export ACCOUNT=stu
# export QOS=normal
```

依赖环境需要 Conda、CUDA 编译工具链和兼容 GCC。使用集群已有指南提供的初始化方式加载后检查；不存在时先查询管理员可用模块，不能臆造 `module load` 名称。PyTorch wheel 使用 CUDA 12.4，建议编译工具链匹配 CUDA 12.4；`nvidia-smi` 显示的是驱动支持能力，不能代替 `nvcc --version`。

```bash
command -v conda
command -v nvcc
nvcc --version
gcc --version
bash slurm/create_env.sh
source slurm/config.sh
"$PYTHON_BIN" -m pip check
```

安装脚本固定主要依赖及 gsplat/diffusers/spz 提交，环境版本保存到 state。上游 uvicorn 0.37.9 在核对时没有对应 PyPI 发布，使用 0.37.0；未更改上游模型架构。环境尚未在此集群安装验证，安装失败应保留错误日志并修复后发新版本。不要安装云端专用的 `spaces` 包。

## 4. 提交实际 GPU 检查与单样例复现

先检查 BF16、实际 CUDA 运算和高斯栅格化内核；通过后再推理。若 local.env 写死 MEM/CPUS，它会覆盖命令行环境变量；应改为默认值形式或移除该项，并用 scontrol show job 核对实际请求。`submit.sh` 在最后输出作业号，并写入 state，之前的 JSON 输出是版本记录，不要把整段输出当作作业号。

```bash
source slurm/config.sh
MEM=16G CPUS=4 MAX_JOBS=2 DEPENDENCY= bash slurm/submit.sh check
CHECK_JOB=$(cat "$SCENE_STATE/check.jobid")
bash slurm/logs.sh "$CHECK_JOB"
```

`tail` 查看结束按 Ctrl+C，只停止日志跟踪。使用 sacct 确认 `COMPLETED` 且 `ExitCode=0:0`。

```bash
sacct -j "$CHECK_JOB" --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,AllocTRES
# check 成功后提交；smoke 自身仍会再次检查 GPU，不依赖旧作业号。
MEM=64G CPUS=8 MAX_JOBS=2 DEPENDENCY= bash slurm/submit.sh smoke
SMOKE_JOB=$(cat "$SCENE_STATE/smoke.jobid")
bash slurm/logs.sh "$SMOKE_JOB"
```

smoke/batch/ui 在 sbatch 前自动执行 CPU preflight（tokenizer、配置、分片索引），失败时不提交 GPU 作业。64G 是待实测预算，不保证完整模型加载足够；失败时先看错误日志。

smoke 默认运行官方样例 3、原文本、24 帧相机采样、480×704、seed 0，并开启 T5/VAE 卸载。正式运行前校验缓存；每次结果保存在 `$SCENE_RUNS/room_b1-作业号-0`。该流程是生成推理，日志不是训练 loss。

## 5. 四任务对照与实时监控

先检查 smoke 的输出与视觉质量，再启动 B0/B1 对照。batch 是最多 4 并发的单卡任务数组，分别为两个室内样例×空用户文本/官方文本；不是四卡分布式训练。

```bash
sacct -j "$SMOKE_JOB" --format=JobID,State,ExitCode,Elapsed,MaxRSS
MEM=64G MAX_JOBS=2 DEPENDENCY= bash slurm/submit.sh batch
BATCH_JOB=$(cat "$SCENE_STATE/batch.jobid")
squeue -u "$USER" -o '%.18i %.12P %.24j %.8T %.10M %.20R'
bash slurm/logs.sh "$BATCH_JOB"
```

查看显存和利用率；登录节点上的 `nvidia-smi` 不代表作业 GPU。

```bash
source slurm/config.sh
ls "$SCENE_LOGS"/gpu-*.csv
# 实时跟踪所有当前已创建的 GPU 监控文件。
tail -f "$SCENE_LOGS"/gpu-*.csv
sacct -j "$BATCH_JOB" --format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocTRES
ls "$SCENE_RUNS"
```

取消特定任务可用 `scancel "$BATCH_JOB"`，不执行无筛选的批量取消。失败结果保留；重新提交产生新 job ID 和新目录。只有 manifest 的 `status=complete` 且资产校验通过表示推理自动检查成功，视觉验收仍待人工完成。

## 6. 导出成果和实验记录

以下以本次 smoke 为例；在同一集群终端中执行。导出包括 PLY、SPZ、MP4、输入快照、环境、版本清单及日志，不打包几十 GB 模型。工具拒绝覆盖已有归档，也拒绝输出摘要发生变化的实验。

```bash
source slurm/config.sh
SMOKE_JOB=$(cat "$SCENE_STATE/smoke.jobid")
SCENE_EXPORT="$DATA_ROOT/exports/world_scene-v$SCENE_VERSION-smoke-$SMOKE_JOB.tar.gz"
"$PYTHON_BIN" -B tools/export_results.py \
  --runs "$SCENE_RUNS" --logs "$SCENE_LOGS" \
  --names "room_b1-$SMOKE_JOB-0" --output "$SCENE_EXPORT"
cd "$DATA_ROOT/exports"
sha256sum -c "world_scene-v$SCENE_VERSION-smoke-$SMOKE_JOB.tar.gz.sha256"
```

batch 导出时给 `--names` 传实际存在的四个完成目录，依次为 `room_b0-数组号-0`、`room_b1-数组号-1`、`studio_b0-数组号-2`、`studio_b1-数组号-3`。不要以为所有数组元素自动成功。

本地下载命令中先输入刚完成的 smoke 作业号，然后核验并解包。

```bash
cd /path/to/project
read -r -p '输入 smoke 作业号: ' SCENE_SMOKE_JOB
mkdir -p 实验结果
rsync -av --partial --progress -e 'ssh -p 22' \
  "your_user@your.cluster.example:/shared/your_user/exports/world_scene-v0.1.3-smoke-$SCENE_SMOKE_JOB.tar.gz*" 实验结果/
cd 实验结果
sha256sum -c "world_scene-v0.1.3-smoke-$SCENE_SMOKE_JOB.tar.gz.sha256"
mkdir -p "smoke-$SCENE_SMOKE_JOB"
tar -xzf "world_scene-v0.1.3-smoke-$SCENE_SMOKE_JOB.tar.gz" -C "smoke-$SCENE_SMOKE_JOB"
```

可迁移输入位于归档的 `portable_inputs`，图像路径相对该目录；原 inputs 与 manifest 保存原始实验记录不改写。不要把渲染 MP4 当作唯一最终成果，必须保留 PLY/SPZ 三维资产。

## 7. 网页及 Blender 验收

先使用官方前端进行模型输出检查；网页入口属于可选交互复现，尚未验证集群端口转发。

```bash
cd /shared/your_user/releases/world_scene-v0.1.3
source slurm/config.sh
bash slurm/submit.sh ui
UI_JOB=$(cat "$SCENE_STATE/ui.jobid")
bash slurm/logs.sh "$UI_JOB"
squeue -j "$UI_JOB" -o '%.18i %.8T %.30N'
```

服务默认监听作业节点回环地址 7860，需要通过登录节点转发至作业节点。只有集群允许从登录节点 SSH 到计算节点时，才在本地使用以下方式（先确认实际节点名；默认 GPU1）：

```bash
ssh -N -J your_user@your.cluster.example:22 -L 7860:127.0.0.1:7860 your_user@GPU1
```

然后浏览本地 `http://127.0.0.1:7860`。如果计算节点禁用 SSH，使用集群认可的隧道方式；此处不能保证上述命令可用。网页缓存为临时文件，作业结束清理，正式成果使用 CLI 和第 6 节导出。

Blender 使用支持 3D Gaussian Splatting 的插件，例如 [KIRI 官方插件](https://github.com/Kiri-Innovation/3dgs-render-blender-addon)。按其当前兼容说明安装匹配的 Blender/插件版本，在实验验收记录中写清版本，导入 `gaussians.ply`，在生成区域内切换观察位置并设置相机路径渲染视频。普通点云 PLY 导入不等价于高斯渲染。插件运行、轴向/尺度、颜色和视角一致性都需实际验收，本版不预先宣称兼容完成。

## 8. 删除无用临时文件

每个任务退出时只删除自己创建的 `assets/tmp/job-ID.随机后缀`。断电/强制取消可能遗留目录；工具默认只列清理候选，且必须能查询 Slurm。执行删除时要求当前用户没有任何排队/运行作业，避免数组内部 job ID 差异导致误删。

```bash
cd /shared/your_user/releases/world_scene-v0.1.3
source slurm/config.sh
squeue -u "$USER"
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS"
# 核对候选，确认当前用户无作业后删除：
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS" --apply
```

此工具不删除权重、原始数据 ZIP、断点下载、历史代码、环境、旧方向资产或实验结果。它们不是临时文件。删除旧环境/旧结果之前先确认归档、校验和无运行引用；本版不提供泛化的 `rm -rf` 清仓命令。

## 9. 故障与后续训练

| 现象 | 下一步 |
|---|---|
| spool 目录下找不到 config.sh | v0.1.1 启动缺陷，当前版本已修复；不要修改旧发布包摘要 |
| OfflineModeIsEnabled / model_info | 按升级指南使用固定本地快照加载；不通过取消离线模式解决 |
| 升级后资产锁定文件变化 | 在登录节点完整 verify models 刷新回执，再 preflight |
| Permission denied | 在自己的终端使用已有学校登录方式；不传密码/私钥到聊天 |
| 缺少 nvcc/Conda | 核对既有集群初始化与管理员模块列表 |
| 资产 quick 校验失败 | 完整 verify；摘要不同则保留错误，重新获取对应固定文件 |
| CUDA/gsplat 编译失败 | 保存环境与错误日志，核对驱动、12.4 编译器和 4090；修复后升级版本 |
| CUDA OOM | 核对卸载确实开启、单卡可用显存与主存；不要直接宣称 4090 不支持 |
| 输入 PLY 有洞/漂浮 | 记录视角及输入，不按一次失败擅自换数据协议 |
| WorldScore 尚未执行 | 相机适配/人工复核 pending 属实，先通过官方 smoke |

FlashWorld 公开入口当前以推理为主，训练代码需依官方渠道获取并验收。未确认训练目标、数据和训练入口前不编写虚构的四卡训练命令。训练获准且实际入口可用时，新版本必须补齐提交、实时 loss/显存监控、checkpoint 保存、恢复与导出命令；当前执行链完成的是基线推理准备。
