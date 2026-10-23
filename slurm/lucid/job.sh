#!/usr/bin/env bash
set -euo pipefail
source "${LUCID_CODE:?请使用 slurm/lucid/submit.sh 提交}/slurm/lucid/config.sh"
export PATH="$LUCID_ENV/bin:$PATH" LD_LIBRARY_PATH="$LUCID_ENV/lib:${LD_LIBRARY_PATH:-}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS="$LUCID_CPUS" OPENBLAS_NUM_THREADS="$LUCID_CPUS"
mkdir -p "$LUCID_ASSETS/tmp"
export TMPDIR
TMPDIR=$(mktemp -d "$LUCID_ASSETS/tmp/job-${SLURM_JOB_ID:?}.XXXXXX")
export GRADIO_TEMP_DIR="$TMPDIR/gradio"
monitor=''
cleanup() {
  [[ -z "$monitor" ]] || kill "$monitor" 2>/dev/null || true
  rm -rf -- "$TMPDIR"
}
trap cleanup EXIT
stage="${1:?missing stage}"
job="${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}"
index="${SLURM_ARRAY_TASK_ID:-1}"
nvidia-smi
nvidia-smi --query-gpu=timestamp,index,name,memory.used,utilization.gpu --format=csv -l 10 \
  > "$LUCID_LOGS/gpu-$job-$index.csv" &
monitor=$!
if [[ "$stage" == check ]]; then name="check-$job"; else name="lucid-$(printf '%02d' "$index")-$job-$index"; fi
"$LUCID_PYTHON" -B "$LUCID_CODE/tools/lucid.py" "$stage" \
  --index "$index" --name "$name" --run-root "$LUCID_RUNS"
