# 公开版 v0.10.2：Slurm 从导入到结果导出

所有 `your_user`、`your.cluster.example`、`/shared/your_user`、`your_gpu_partition`、`your_4090_node` 都是占位符，先换成自己的配置。本公开版没有预设个人账号或服务器。已有内部 v0.8.0 任务继续使用原目录，不覆盖正在运行的版本。

## 1. 本地上传源码

源码包和 SHA256 在同一目录。GitHub 仓库用于存代码，服务器运行使用独立版本目录；源码包不包含权重。

```bash
cd /path/to/downloads
sha256sum -c world_scene-v0.10.2.tar.gz.sha256
SCENE_SSH=your_user@your.cluster.example
SCENE_REMOTE_BASE=/shared/your_user/world-scene-data
ssh "$SCENE_SSH" mkdir -p "$SCENE_REMOTE_BASE/releases"
rsync -av --partial --progress \
  world_scene-v0.10.2.tar.gz world_scene-v0.10.2.tar.gz.sha256 \
  "$SCENE_SSH:$SCENE_REMOTE_BASE/releases/"
```

## 2. 服务器导入与配置

以下在服务器执行。`local.env` 和 `lucid.env` 是各自的私有配置，受 `.gitignore` 排除；源码包校验不包含这些本机文件。

```bash
set -euo pipefail
cd /shared/your_user/world-scene-data/releases
sha256sum -c world_scene-v0.10.2.tar.gz.sha256
if [[ ! -e world_scene-v0.10.2 ]]; then tar -xzf world_scene-v0.10.2.tar.gz; fi
cd world_scene-v0.10.2
if [[ ! -e local.env ]]; then cp local.env.example local.env; fi
if [[ ! -e lucid.env ]]; then cp lucid.env.example lucid.env; fi
# 用编辑器修改两份配置中的存储路径、分区、节点及所需 account/QOS。
nano local.env
nano lucid.env
unset SCENE_ENV SCENE_RUNS SCENE_LOGS SCENE_STATE PYTHON_BIN
source slurm/config.sh
python3 -B tools/experiment.py inspect
```

FlashWorld 与 LucidDreamer 的 DATA_ROOT 应指向同一公共数据根，二者的模型资产目录和环境仍彼此独立。空 account/QOS 不传对应 sbatch 参数；节点留空时由调度器选择，需保证分区内分到的是 4090。本版 GPU 检查明确要求 4090。

如果已安装验证过 FlashWorld 环境，在 `local.env` 的 SCENE_ENV 填已有环境绝对路径，跳过环境创建。不要为了这个公开整理版升级已有环境中的依赖。

## 3. 环境、权重及开发图片

首次安装 FlashWorld 需要 conda、可用的 CUDA 12.4 编译器与 C++ 工具链，环境创建脚本会打印版本；具体 module 加载方式按所在集群设置。不要在已有其他项目环境中直接 pip 安装。

```bash
# 仅首次创建环境时执行；已经配置已有验证环境时跳过。
bash slurm/create_env.sh
```

准备固定权重与 WorldScore 数据。已有资产可复用，代码会校验而非静默覆盖损坏文件。下载可能耗时较长且需要几十 GB 空间；保留 .part 断点，不运行并发的重复下载进程。版本锁变化需重新完整校验回执，等共享这套资产的旧 FlashWorld 任务结束再做，避免交替回写回执。

```bash
source slurm/config.sh
python3 -B tools/assets.py status --root "$SCENE_ASSETS" --group all
python3 -B tools/assets.py download --root "$SCENE_ASSETS" --group all --workers 3
python3 -B tools/assets.py verify --root "$SCENE_ASSETS" --group all
python3 -B tools/data.py --root "$SCENE_ASSETS"
"$PYTHON_BIN" -B tools/experiment.py preflight
"$PYTHON_BIN" -B tools/angles.py verify --assets "$SCENE_ASSETS" --array '0-2%1' --runtime
```

## 4. 先做 GPU 检查与官方单例

已有相同硬件/环境的成功检查可直接进入第 5 节。下面两次提交都只在成功时读取新作业号。先等待 check 在 sacct 显示 COMPLETED，再提交 smoke；这里不使用可能过期的 dependency 作业号。

```bash
if MEM=16G CPUS=4 DEPENDENCY= bash slurm/submit.sh check; then
  CHECK_JOB=$(cat "$SCENE_STATE/check.jobid")
  printf 'check job: %s\n' "$CHECK_JOB"
  sacct -j "$CHECK_JOB" --format=JobID,State%24,ExitCode,Elapsed
  bash slurm/logs.sh "$CHECK_JOB"
else
  echo '检查提交失败，不读取旧作业号。'
fi
```

```bash
# 仅 check 已完成且成功后执行。
if MEM=96G CPUS=8 MAX_JOBS=2 DEPENDENCY= bash slurm/submit.sh smoke; then
  SMOKE_JOB=$(cat "$SCENE_STATE/smoke.jobid")
  printf 'smoke job: %s\n' "$SMOKE_JOB"
  bash slurm/logs.sh "$SMOKE_JOB"
else
  echo '单例提交失败，不读取旧作业号。'
fi
```

FlashWorld 的 96G 是主存，不是显存；64G 曾在模型量化阶段 OOM。检查任务不需要申请同样大的主存。

## 5. 同一客厅图三档角度生成

索引 0/1/2 对应水平向左 30/45/75°。固定图文、seed 0、相机中心、裁剪、内参、24 个相机和正参考尺度。视频第 0 帧为输入视角，346 帧、15 fps。新轨迹尚待视觉验收，纯旋转不检验解除遮挡后的背面。

以下默认串行，每例 96G/8 CPU/单卡、4 小时时限。三例约 3–4 GPU 小时仅为此前运行数据推算，另计排队。

```bash
(
  set -euo pipefail
  source slurm/config.sh
  if [[ -e "$SCENE_STATE/angles-main.jobid" ]]; then
    echo '已有主数组记录；先查状态，勿重复提交。' >&2
    exit 2
  fi
  if MEM=96G CPUS=8 MAX_JOBS=2 SEED=0 DEPENDENCY= \
    ANGLES_ARRAY='0-2%1' bash slurm/submit.sh angles; then
    ANGLES_JOB=$(cat "$SCENE_STATE/angles.jobid")
    [[ "$ANGLES_JOB" =~ ^[0-9]+$ ]]
    printf '%s\n' "$ANGLES_JOB" > "$SCENE_STATE/angles-main.jobid"
    for i in 0 1 2; do printf '%s\n' "$ANGLES_JOB" > "$SCENE_STATE/angles-task-$i.jobid"; done
    squeue -r -j "$ANGLES_JOB"
  else
    echo '预检或提交失败；不读取旧作业号。' >&2
    exit 1
  fi
)
```

## 6. 实时查看、断线恢复与失败重提

断线后重新登录并进入实际发布目录。`logs.sh` 的 Ctrl+C 只停止跟踪；不取消 Slurm 作业。后续数组元素启动后重新运行日志命令。排队时无日志正常，结束任务用 sacct 查询。

```bash
cd /shared/your_user/world-scene-data/releases/world_scene-v0.10.2
unset SCENE_ENV SCENE_RUNS SCENE_LOGS SCENE_STATE PYTHON_BIN
source slurm/config.sh
ANGLES_JOB=$(cat "$SCENE_STATE/angles-main.jobid")
squeue -r -j "$ANGLES_JOB"
sacct -S 2026-10-23 -j "$ANGLES_JOB" \
  --format=JobID%24,State%24,ExitCode,Elapsed,ReqMem,MaxRSS,NodeList
bash slurm/logs.sh "$ANGLES_JOB"
```

直接查看指定档位；索引 0/1/2 分别对应 30/45/75°：

```bash
ANGLE_INDEX=0
ANGLE_DEGREES=(30 45 75)
ANGLE_CASE="angles-living-left-${ANGLE_DEGREES[$ANGLE_INDEX]}"
ANGLE_JOB=$(cat "$SCENE_STATE/angles-task-$ANGLE_INDEX.jobid")
tail -n 100 "$SCENE_LOGS/angles-${ANGLE_JOB}_${ANGLE_INDEX}.err"
tail -n 80 "$SCENE_LOGS/angles-${ANGLE_JOB}_${ANGLE_INDEX}.out"
cat "$SCENE_RUNS/$ANGLE_CASE-$ANGLE_JOB-$ANGLE_INDEX/manifest.json"
```

只在对应任务确已结束且失败后重提。例如只有 75° 执行失败：

```bash
(
  set -euo pipefail
  source slurm/config.sh
  RETRY_SELECTION='2%1'
  RETRY_INDICES=$(python3 -B -c 'import sys;sys.path.insert(0,"tools");from angles import task_indices;print(" ".join(map(str,task_indices(sys.argv[1]))))' "$RETRY_SELECTION")
  if MEM=96G CPUS=8 MAX_JOBS=2 SEED=0 DEPENDENCY= \
    ANGLES_ARRAY="$RETRY_SELECTION" bash slurm/submit.sh angles; then
    RETRY_JOB=$(cat "$SCENE_STATE/angles.jobid")
    [[ "$RETRY_JOB" =~ ^[0-9]+$ ]]
    for i in $RETRY_INDICES; do printf '%s\n' "$RETRY_JOB" > "$SCENE_STATE/angles-task-$i.jobid"; done
    printf 'retry job: %s\n' "$RETRY_JOB"
  else
    echo '重试提交失败，保留旧状态。' >&2
    exit 1
  fi
)
```

已执行成功但画面差，属于视觉失败；保留记录，同种子原样重跑不作为修复。

## 7. 推理完成后导出与下载

三档 manifest 都应为 complete，且 sacct 为 COMPLETED。导出工具再次核验产物摘要，使用各档实际重试作业号。默认不覆盖已有同名归档。

```bash
(
  set -euo pipefail
  source slurm/config.sh
  ANGLES_MAIN_JOB=$(cat "$SCENE_STATE/angles-main.jobid")
  [[ "$ANGLES_MAIN_JOB" =~ ^[0-9]+$ ]]
  ANGLE_DEGREES=(30 45 75)
  ANGLE_NAMES=()
  for i in 0 1 2; do
    j=$(cat "$SCENE_STATE/angles-task-$i.jobid")
    [[ "$j" =~ ^[0-9]+$ ]]
    ANGLE_NAMES+=("angles-living-left-${ANGLE_DEGREES[$i]}-$j-$i")
  done
  "$PYTHON_BIN" -B tools/export_results.py \
    --runs "$SCENE_RUNS" --logs "$SCENE_LOGS" --names "${ANGLE_NAMES[@]}" \
    --output "$DATA_ROOT/exports/world_scene-v0.10.2-angles-$ANGLES_MAIN_JOB.tar.gz"
)
```

本地下载（只填主数组号数字），先修改 SSH 和远端存储路径：

```bash
(
  set -euo pipefail
  SCENE_SSH=your_user@your.cluster.example
  SCENE_REMOTE_BASE=/shared/your_user/world-scene-data
  read -r -p '主数组号（数字）：' ANGLES_MAIN_JOB
  [[ "$ANGLES_MAIN_JOB" =~ ^[0-9]+$ ]]
  ARCHIVE="world_scene-v0.10.2-angles-$ANGLES_MAIN_JOB.tar.gz"
  mkdir -p experiment-results
  rsync -av --partial --progress \
    "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/$ARCHIVE" \
    "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/$ARCHIVE.sha256" experiment-results/
  cd experiment-results
  sha256sum -c "$ARCHIVE.sha256"
  mkdir -p "${ARCHIVE%.tar.gz}"
  tar -xzf "$ARCHIVE" -C "${ARCHIVE%.tar.gz}"
)
```

视频位于各运行目录 `outputs/angles-living-left-角度/video.mp4`。首先检查首帧输入保持，再检查新增区域及几何破损。共同 30° 视角分别约在三档视频的 23、15.33、9.2 秒。

## 8. 第二模型：独立安装、检查、运行和导出

先完成 lucid.env 配置。以下为现有 gallery 对照协议，**不是新的 angles 纯旋转协议**；索引 1 是官方 studio 图片。先试跑一例，完整 GPU 效果尚待验收。

```bash
source slurm/lucid/config.sh
bash slurm/lucid/create_env.sh
"$LUCID_PYTHON" -B tools/lucid_assets.py download --root "$LUCID_ASSETS"
"$LUCID_PYTHON" -B tools/lucid_assets.py verify --root "$LUCID_ASSETS"
if LUCID_ARRAY='1%1' LUCID_MEM=32G LUCID_CPUS=4 LUCID_DEPENDENCY= \
  bash slurm/lucid/submit.sh check; then
  LUCID_CHECK_JOB=$(cat "$LUCID_STATE/check.jobid")
  bash slurm/lucid/logs.sh "$LUCID_CHECK_JOB"
fi
```

等待 check 的 sacct 为 COMPLETED 后再执行：

```bash
if LUCID_ARRAY='1%1' LUCID_MEM=64G LUCID_CPUS=8 LUCID_DEPENDENCY= \
  bash slurm/lucid/submit.sh run; then
  LUCID_RUN_JOB=$(cat "$LUCID_STATE/run.jobid")
  squeue -r -j "$LUCID_RUN_JOB"
  bash slurm/lucid/logs.sh "$LUCID_RUN_JOB"
else
  echo '第二模型提交失败，不读取旧作业号。'
fi
```

这里 GS_ITER/loss 为逐场景高斯优化，不是基础模型训练。需要断线恢复时进入该发布目录，重新 source lucid/config.sh，再从 run.jobid 读取作业号。重试时只选择失败的索引，例如 `LUCID_ARRAY='1%1'`；提交工具成功后自动更新该索引对应的实际作业号，旧运行目录不覆盖。

```bash
source slurm/lucid/config.sh
LUCID_RUN_JOB=$(cat "$LUCID_STATE/run.jobid")
sacct -S 2026-10-23 -j "$LUCID_RUN_JOB" --format=JobID%24,State%24,ExitCode,Elapsed,ReqMem,MaxRSS
python3 -B tools/lucid_export.py --runs "$LUCID_RUNS" --state "$LUCID_STATE" \
  --logs "$LUCID_LOGS" --indices 1 \
  --output "$LUCID_DATA_ROOT/exports/world_scene-v0.10.2-lucid-$LUCID_RUN_JOB.tar.gz"
```

第二模型归档及同名 `.sha256` 的 rsync/sha256sum/tar 操作与第 7 节相同，将 ARCHIVE 替换为上面打印的实际文件名。更多实现细节见 [适配说明](LucidDreamer适配说明.md)。

## 9. 清理无用临时文件

作业正常退出会删除自己的临时输入。异常退出后先列候选；当前用户有任何排队或运行任务时清理工具拒绝删除。核对后再执行 --apply。不删除权重、环境、断点下载、已有发布版和成功/失败结果。

```bash
source slurm/config.sh
squeue -u "$USER"
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS"
# 无排队/运行任务且确认候选后执行：
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS" --apply
# 第二模型的废弃作业临时目录同理，使用自己的 assets：
source slurm/lucid/config.sh
python3 -B tools/cleanup.py --assets "$LUCID_ASSETS"
# 核对后：
python3 -B tools/cleanup.py --assets "$LUCID_ASSETS" --apply
```

没有需要为了升级而批量删除的旧源码。旧版保留用于回滚；本版可复用已验证环境，不要在正在运行的目录覆盖文件。


## 当前多样相机和同条件对照

本版 LucidDreamer 使用十例不同幅度的水平转向。相机表、QOS 分批、单例预检和导出见 [当前实验流程](CURRENT_EXPERIMENTS.md)。同条件客厅示例及完整提交/监控/导出脚本见 [模型对照](PAIRED_COMPARISON.md)。历史结果保持原始版本身份，不视作公开整理版重新实测。
