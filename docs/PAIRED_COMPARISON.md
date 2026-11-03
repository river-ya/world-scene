# 客厅同条件对照：复现、监控、导出

先按 [Slurm 完整指南](SLURM.md) 第 1–3 节上传源码包、解压至独立版本目录、配置自己的 local.env / lucid.env、环境和固定权重。可以复用已验证环境，不升级已有包，也不覆盖正在运行的旧版本。

## 冻结输入和预检

examples/paired-room40/input.json 是原始同条件运行的自包含 JSON，图片为 PNG base64；input.png 方便查看。文本、相机和内参保持原样。JSON 里的历史 pending 字段是生成输入时的状态，实际运行状态以 result-summary.json 为准。

对应 LucidDreamer 索引 0，固定中心左转 40°。公开的左右视频使用同一 LucidDreamer PLY 的白底重渲染；以下原生 LucidDreamer 重跑仍按默认黑底导出，不能混称为已经统一背景。

刷新回执前等待共享相同资产的旧 FlashWorld 任务结束。

~~~bash
source slurm/config.sh
python3 -B tools/experiment.py inspect
"$PYTHON_BIN" -B tools/assets.py verify --root "$SCENE_ASSETS" --group models
"$PYTHON_BIN" -B tools/experiment.py preflight
~~~

## 提交 FlashWorld 单例

资源为 1 张 4090、8 CPU、96G 主机内存、4 小时。账户/QOS 为空时不传选项；需要至少一个可用提交名额。已记录单例时不重复提交。

~~~bash
(
  set -euo pipefail
  source slurm/config.sh
  mkdir -p "$SCENE_LOGS" "$SCENE_RUNS" "$SCENE_STATE"
  test ! -e "$SCENE_STATE/matched.jobid"
  args=(--parsable --nodes=1 --ntasks=1 --gres=gpu:1
    --cpus-per-task=8 --mem=96G --time=04:00:00
    --partition="$PARTITION" --job-name=matched-room40 --export=ALL
    --chdir="$SCENE_CODE"
    --output="$SCENE_LOGS/matched-%j.out" --error="$SCENE_LOGS/matched-%j.err")
  [[ -z "$ACCOUNT" ]] || args+=(--account="$ACCOUNT")
  [[ -z "$QOS" ]] || args+=(--qos="$QOS")
  [[ -z "$NODE" ]] || args+=(--nodelist="$NODE")
  MATCH_JOB=$(sbatch "${args[@]}" "$SCENE_CODE/slurm/matched_job.sh")
  MATCH_JOB=${MATCH_JOB%%;*}
  [[ "$MATCH_JOB" =~ ^[0-9]+$ ]]
  printf '%s\n' "$MATCH_JOB" > "$SCENE_STATE/matched.jobid"
  squeue -j "$MATCH_JOB"
)
~~~

## 相同 LucidDreamer 样例

首次使用该环境先运行独立 GPU check，见 [当前实验指南](CURRENT_EXPERIMENTS.md)。然后：

~~~bash
source slurm/lucid/config.sh
"$LUCID_PYTHON" -B tools/lucid_assets.py verify --root "$LUCID_ASSETS"
"$LUCID_PYTHON" -B tools/lucid.py preflight --array '0%1'
LUCID_ARRAY='0%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh run
~~~

## 实时状态

~~~bash
source slurm/config.sh
MATCH_JOB=$(cat "$SCENE_STATE/matched.jobid")
squeue -j "$MATCH_JOB"
sacct -j "$MATCH_JOB" --format=JobID,State%24,ExitCode,Elapsed,ReqMem,MaxRSS
tail -n 40 -F "$SCENE_LOGS/matched-$MATCH_JOB.out" "$SCENE_LOGS/matched-$MATCH_JOB.err"
~~~

Ctrl+C 只停止日志跟踪。结果为 matched-room40-作业号/outputs/input/video.mp4。需要 COMPLETED、退出码 0:0、manifest complete；视觉质量单独检查。

## 服务器打包

~~~bash
source slurm/config.sh
MATCH_JOB=$(cat "$SCENE_STATE/matched.jobid")
"$PYTHON_BIN" -B tools/export_results.py \
  --runs "$SCENE_RUNS" --logs "$SCENE_LOGS" \
  --names "matched-room40-$MATCH_JOB" \
  --output "$DATA_ROOT/exports/matched-room40-$MATCH_JOB.tar.gz"
~~~

## 本地下载和校验

将占位符改成自己的配置。原始导出包包含运行路径，仅用于自己的交付；公开发布前另挑素材和匿名化元数据。

~~~bash
(
  set -euo pipefail
  SCENE_SSH=your_user@your.cluster.example
  SCENE_REMOTE_BASE=/shared/your_user/world-scene-data
  read -r -p '输入单例作业号：' MATCH_JOB
  [[ "$MATCH_JOB" =~ ^[0-9]+$ ]]
  ARCHIVE="matched-room40-$MATCH_JOB.tar.gz"
  mkdir -p results
  rsync -av --partial --progress \
    "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/$ARCHIVE" \
    "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/$ARCHIVE.sha256" results/
  cd results
  sha256sum -c "$ARCHIVE.sha256"
  test ! -e "${ARCHIVE%.tar.gz}"
  mkdir "${ARCHIVE%.tar.gz}"
  tar -xzf "$ARCHIVE" -C "${ARCHIVE%.tar.gz}"
)
~~~

## 清理

正常任务会删除自己的 TMPDIR。异常强杀后先查看候选，确认用户无活动任务再应用；权重、环境、输入、失败记录和正式结果保留。

~~~bash
source slurm/config.sh
squeue -u "$USER"
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS"
# 确认候选均是废弃任务临时目录后执行：
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS" --apply
~~~
