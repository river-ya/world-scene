#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
stage="${1:?Usage: bash slurm/lucid/submit.sh check|run}"
[[ "$stage" == check || "$stage" == run ]] || exit 2
mkdir -p "$LUCID_LOGS" "$LUCID_STATE" "$LUCID_RUNS"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$LUCID_PYTHON" -B "$LUCID_CODE/tools/lucid.py" preflight --array "$LUCID_ARRAY"
args=(--parsable --partition="$LUCID_PARTITION"
      --nodes=1 --ntasks=1 --gres=gpu:1 --cpus-per-task="$LUCID_CPUS"
      --mem="$LUCID_MEM" --time="$LUCID_TIME" --job-name="lucid-$stage"
      --chdir="$LUCID_CODE" --export=ALL
      --output="$LUCID_LOGS/$stage-%A_%a.out" --error="$LUCID_LOGS/$stage-%A_%a.err")
[[ -z "$LUCID_ACCOUNT" ]] || args+=(--account="$LUCID_ACCOUNT")
[[ -z "$LUCID_QOS" ]] || args+=(--qos="$LUCID_QOS")
[[ -z "$LUCID_NODE" ]] || args+=(--nodelist="$LUCID_NODE")
[[ "$stage" != check ]] || args+=(--time=00:45:00)
[[ "$stage" != run ]] || args+=(--array="$LUCID_ARRAY")
[[ -z "${LUCID_DEPENDENCY:-}" ]] || args+=(--dependency="afterok:$LUCID_DEPENDENCY")
job=$(sbatch "${args[@]}" "$LUCID_CODE/slurm/lucid/job.sh" "$stage")
job=${job%%;*}
[[ "$job" =~ ^[0-9]+$ ]] || { echo 'sbatch 未返回有效作业号' >&2; exit 2; }
printf '%s\n' "$job" > "$LUCID_STATE/$stage.jobid"
if [[ "$stage" == run ]]; then
  indices=$(python3 -B -c 'import sys;sys.path.insert(0,sys.argv[1]);from showcase import task_indices;print(" ".join(map(str,task_indices(sys.argv[2]))))' "$LUCID_CODE/tools" "$LUCID_ARRAY")
  for index in $indices; do printf '%s\n' "$job" > "$LUCID_STATE/case-$index.jobid"; done
  printf '%s\n' "$LUCID_ARRAY" > "$LUCID_STATE/run-$job.selection"
fi
printf '%s\n' "$job"
