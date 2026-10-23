#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
job="${1:?Usage: bash slurm/logs.sh JOB_ID}"
[[ "$job" =~ ^[0-9]+$ ]] || exit 2
shopt -s nullglob
files=("$SCENE_LOGS/"*"-$job"_*.out "$SCENE_LOGS/"*"-$job"_*.err)
if ((${#files[@]})); then
  tail -n 30 -F "${files[@]}"
else
  echo '尚无日志，作业可能在排队。启动后重新运行此命令。'
  squeue -j "$job"
fi
