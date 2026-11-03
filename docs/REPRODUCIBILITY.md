# 当前版本复现

本页是公开仓库的统一运行入口，覆盖环境准备、单例提交、监控和导出。实验条件见 [数据与实验协议](数据与实验协议.md)，结果及两模型差异见 [RESULTS.md](RESULTS.md)。

## 源码与配置

在服务器克隆仓库，复现发布版本时检出对应 tag。以下以 v0.10.2 为例；配置中的路径、分区、节点和账户均需填写自己的值。两份配置的数据根使用同一共享目录，环境保持独立。

~~~bash
git clone https://github.com/river-ya/world-scene.git
cd world-scene
git checkout v0.10.2
cp -n local.env.example local.env
cp -n lucid.env.example lucid.env
nano local.env
nano lucid.env
python3 -B tools/experiment.py inspect
~~~

当前 GPU 检查面向 RTX 4090。FlashWorld 使用 Python 3.10 / torch 2.6.0 cu124，首次安装需 conda、CUDA 12.4 编译器和 C++ 工具链；LucidDreamer 使用独立 Python 3.9 / torch 2.0.1 cu118 环境，其脚本安装 CUDA 11.8 与 GCC 11。已有验证环境可在配置中指定，不必重装。

~~~bash
# 仅首次安装时执行。
bash slurm/create_env.sh
bash slurm/lucid/create_env.sh
~~~

## 固定权重与预检

以下客厅单例使用仓库内的作者示例，不需要下载完整数据集。下载需联网，GPU 作业使用本地权重。共享资产的完整校验应在使用这套资产的旧任务结束后执行。

~~~bash
(
  set -euo pipefail
  source slurm/config.sh
  unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
  python3 -B tools/assets.py download --root "$SCENE_ASSETS" --group models --workers 3
  python3 -B tools/assets.py verify --root "$SCENE_ASSETS" --group models
  "$PYTHON_BIN" -B tools/experiment.py preflight
)
(
  set -euo pipefail
  source slurm/lucid/config.sh
  unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
  "$LUCID_PYTHON" -B tools/lucid_assets.py download --root "$LUCID_ASSETS"
  "$LUCID_PYTHON" -B tools/lucid_assets.py verify --root "$LUCID_ASSETS"
  "$LUCID_PYTHON" -B tools/lucid.py preflight --array '0%1'
)
~~~

首次使用环境先分别提交 GPU 检查，确认 sacct 显示 COMPLETED 且退出码为 0:0 后，再提交生成任务。

~~~bash
DEPENDENCY= bash slurm/submit.sh check
LUCID_ARRAY='0%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh check
~~~

## 客厅左转 40° 单例

冻结输入在 [examples/paired-room40](../examples/paired-room40/)，对应 LucidDreamer 索引 0。FlashWorld 单例申请 1 张 GPU、8 CPU、96G 主机内存，使用 T5/VAE CPU offload。下面保留作业号，防止误重复提交。

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
)
LUCID_ARRAY='0%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh run
~~~

两模型共用图片、用户文本、内参和相机，保留各自生成算法。LucidDreamer 默认导出黑底；已发布的对比视频使用同一 PLY 另行白底重渲染。以上原生重跑不自动完成背景统一或左右拼接，具体显示条件见 [RESULTS.md](RESULTS.md)。

## 查看进度与导出

~~~bash
source slurm/config.sh
MATCH_JOB=$(cat "$SCENE_STATE/matched.jobid")
squeue -j "$MATCH_JOB"
sacct -j "$MATCH_JOB" --format=JobID,State%24,ExitCode,Elapsed,MaxRSS
tail -n 40 -F "$SCENE_LOGS/matched-$MATCH_JOB.out" "$SCENE_LOGS/matched-$MATCH_JOB.err"
~~~

Ctrl+C 退出日志跟踪。LucidDreamer 使用独立日志入口；GPU check 的作业号分别保存在两套 state 目录的 check.jobid 中，也可用 sacct 查询。

~~~bash
source slurm/lucid/config.sh
LUCID_JOB=$(cat "$LUCID_STATE/run.jobid")
sacct -j "$LUCID_JOB" --format=JobID,State%24,ExitCode,Elapsed,MaxRSS
bash slurm/lucid/logs.sh "$LUCID_JOB"
~~~

完成需同时检查调度器状态、manifest 的 complete 状态和视觉质量。以下导出工具校验输入、输出摘要，包含 PLY、视频和元数据；输出名需未被使用。

~~~bash
(
  set -euo pipefail
  source slurm/config.sh
  MATCH_JOB=$(cat "$SCENE_STATE/matched.jobid")
  "$PYTHON_BIN" -B tools/export_results.py --runs "$SCENE_RUNS" --logs "$SCENE_LOGS" \
    --names "matched-room40-$MATCH_JOB" \
    --output "$DATA_ROOT/exports/matched-room40-$MATCH_JOB.tar.gz"
)
(
  set -euo pipefail
  source slurm/lucid/config.sh
  LUCID_JOB=$(cat "$LUCID_STATE/case-0.jobid")
  "$LUCID_PYTHON" -B tools/lucid_export.py --indices 0 \
    --output "$LUCID_DATA_ROOT/exports/lucid-room40-$LUCID_JOB.tar.gz"
)
~~~

在本地下载归档及同名 .sha256 文件，再校验；下面用 FlashWorld 归档示例，LucidDreamer 替换文件名即可。

~~~bash
SCENE_SSH=your_user@your.cluster.example
SCENE_REMOTE_BASE=/shared/your_user/world-scene-data
MATCH_JOB=your_job_id
mkdir -p results
rsync -av --partial --progress \
  "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/matched-room40-$MATCH_JOB.tar.gz" \
  "$SCENE_SSH:$SCENE_REMOTE_BASE/exports/matched-room40-$MATCH_JOB.tar.gz.sha256" results/
cd results
sha256sum -c "matched-room40-$MATCH_JOB.tar.gz.sha256"
mkdir "matched-room40-$MATCH_JOB"
tar -xzf "matched-room40-$MATCH_JOB.tar.gz" -C "matched-room40-$MATCH_JOB"
~~~

## 批量与临时目录

十例所需的六张开发图通过以下命令准备。数组每项申请一张 GPU；%4 只限制同时运行数，全部数组元素仍计入提交配额，应按所在集群限制分批。

~~~bash
source slurm/config.sh
python3 -B tools/assets.py download --root "$SCENE_ASSETS" --group worldscore --workers 3
python3 -B tools/data.py --root "$SCENE_ASSETS"
# 按自身配额选择索引，再使用 LUCID_ARRAY='索引%并发数' 提交。
~~~

正常作业自动删除自身临时目录。异常终止后先查看候选；用户无活动任务且候选确认为废弃目录时，增加 --apply 执行清理。该工具保留权重、断点下载和正式结果。

~~~bash
source slurm/config.sh
python3 -B tools/cleanup.py --assets "$SCENE_ASSETS"
source slurm/lucid/config.sh
python3 -B tools/cleanup.py --assets "$LUCID_ASSETS"
~~~
