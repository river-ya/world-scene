#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
job="${1:?Usage: bash slurm/lucid/logs.sh JOB_ID}"
[[ "$job" =~ ^[0-9]+$ ]] || exit 2
shopt -s nullglob
files=("$LUCID_LOGS/"*"-$job"_*.out "$LUCID_LOGS/"*"-$job"_*.err)
if ((${#files[@]})); then tail -n 40 -F "${files[@]}";
else echo '尚无日志，作业可能在排队；无需重复提交。'; squeue -r -j "$job"; fi
