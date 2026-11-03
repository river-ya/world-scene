#!/usr/bin/env bash
set -euo pipefail
# Slurm runs a spool copy of this file; sibling files are not copied.
# submit.sh exports the absolute release path through --export=ALL.
source "${SCENE_CODE:?请通过 slurm/submit.sh 提交作业}/slurm/config.sh"
export PATH="$SCENE_ENV/bin:$PATH"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
mkdir -p "$SCENE_ASSETS/tmp" "$SCENE_LOGS"
export TMPDIR
TMPDIR=$(mktemp -d "$SCENE_ASSETS/tmp/job-${SLURM_JOB_ID:?}.XXXXXX")
export GRADIO_TEMP_DIR="$TMPDIR/gradio"
mkdir -p "$GRADIO_TEMP_DIR"
monitor_pid=''
cleanup() {
  [[ -z "$monitor_pid" ]] || kill "$monitor_pid" 2>/dev/null || true
  if [[ "$TMPDIR" == "$SCENE_ASSETS/tmp/job-${SLURM_JOB_ID}."* ]]; then rm -rf -- "$TMPDIR"; fi
}
trap cleanup EXIT
nvidia-smi
"$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" check
stage="${1:?missing stage}"
[[ "$stage" != check ]] || exit 0
"$PYTHON_BIN" -B "$SCENE_CODE/tools/assets.py" verify --root "$SCENE_ASSETS" --group models --quick
run_id="${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-0}"
nvidia-smi --query-gpu=timestamp,index,name,memory.used,utilization.gpu --format=csv -l 10 > "$SCENE_LOGS/gpu-$run_id.csv" &
monitor_pid=$!
if [[ "$stage" == ui ]]; then
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" ui --run-root "$SCENE_RUNS" --name "ui-$run_id"
else
  case_id=room_b1
  if [[ "$stage" == batch ]]; then
    cases=(room_b0 room_b1 studio_b0 studio_b1)
    case_id="${cases[$SLURM_ARRAY_TASK_ID]}"
  fi
  if [[ "$stage" == viewcheck || "$stage" == studioview ]]; then
    [[ "${SEED:-0}" == 0 ]] || { echo "$stage 必须使用 SEED=0" >&2; exit 2; }
    case_id=kitchen-small
    [[ "$stage" != studioview ]] || case_id=kitchen-studio
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/$stage.py" prepare --assets "$SCENE_ASSETS" \
      --runtime --output "$TMPDIR/inputs"
  elif [[ "$stage" == angles ]]; then
    [[ "${SEED:-0}" == 0 ]] || { echo 'angles 必须使用 SEED=0' >&2; exit 2; }
    angles=(30 45 75)
    index="${SLURM_ARRAY_TASK_ID:?}"
    [[ "$index" =~ ^[0-2]$ ]] || { echo 'angles 索引必须为 0–2' >&2; exit 2; }
    case_id="angles-living-left-${angles[$index]}"
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/angles.py" prepare --assets "$SCENE_ASSETS" \
      --index "$index" --runtime --output "$TMPDIR/inputs"
  elif [[ "$stage" == wideview ]]; then
    [[ "${SEED:-0}" == 0 ]] || { echo 'wideview 必须使用 SEED=0' >&2; exit 2; }
    index="${SLURM_ARRAY_TASK_ID:?}"
    [[ "$index" =~ ^[4-9]$ ]] || { echo 'wideview 索引必须为 4–9' >&2; exit 2; }
    case_id=$(printf 'wideview-%02d' "$index")
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/wideview.py" prepare --assets "$SCENE_ASSETS" \
      --index "$index" --runtime --output "$TMPDIR/inputs"
  elif [[ "$stage" == gallery ]]; then
    [[ "${SEED:-0}" == 0 ]] || { echo 'gallery 必须使用 SEED=0' >&2; exit 2; }
    case_id=$(printf 'gallery-%02d' "${SLURM_ARRAY_TASK_ID:?}")
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/gallery.py" prepare --assets "$SCENE_ASSETS" \
      --index "$SLURM_ARRAY_TASK_ID" --runtime --output "$TMPDIR/inputs"
  elif [[ "$stage" == showcase ]]; then
    case_id=$(printf 'showcase-%02d' "${SLURM_ARRAY_TASK_ID:?}")
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/showcase.py" prepare --assets "$SCENE_ASSETS" \
      --index "$SLURM_ARRAY_TASK_ID" --output "$TMPDIR/inputs"
  else
    "$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" prepare --output "$TMPDIR/inputs" --case "$case_id"
  fi
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" run --inputs "$TMPDIR/inputs" \
    --run-root "$SCENE_RUNS" --name "$case_id-$run_id" --seed "${SEED:-0}"
fi
