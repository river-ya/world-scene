#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
stage="${1:?Usage: bash slurm/submit.sh check|smoke|batch|showcase|viewcheck|studioview|gallery|angles|wideview|ui}"
case "$stage" in check|smoke|batch|showcase|viewcheck|studioview|gallery|angles|wideview|ui) ;; *) echo '不支持该阶段；训练入口尚未验收。' >&2; exit 2;; esac
mkdir -p "$SCENE_LOGS" "$SCENE_STATE" "$SCENE_RUNS"
python3 -B "$SCENE_CODE/tools/experiment.py" inspect
if [[ "$stage" == showcase ]]; then
  export SHOWCASE_ARRAY="${SHOWCASE_ARRAY:-2-9%1}"
  python3 -B "$SCENE_CODE/tools/showcase.py" verify --assets "$SCENE_ASSETS" --array "$SHOWCASE_ARRAY"
fi
if [[ "$stage" == gallery ]]; then
  export GALLERY_ARRAY="${GALLERY_ARRAY:-3-9%1}"
  [[ "${SEED:-0}" == 0 ]] || { echo 'gallery 固定 SEED=0' >&2; exit 2; }
  python3 -B "$SCENE_CODE/tools/gallery.py" verify --assets "$SCENE_ASSETS" --array "$GALLERY_ARRAY"
fi
if [[ "$stage" == angles ]]; then
  export ANGLES_ARRAY="${ANGLES_ARRAY:-0-2%1}"
  [[ "${SEED:-0}" == 0 ]] || { echo 'angles 固定 SEED=0' >&2; exit 2; }
  python3 -B "$SCENE_CODE/tools/angles.py" verify --assets "$SCENE_ASSETS" --array "$ANGLES_ARRAY"
fi
if [[ "$stage" != check ]]; then
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" preflight
fi
if [[ "$stage" == wideview ]]; then
  export WIDEVIEW_ARRAY="${WIDEVIEW_ARRAY:-4-9%1}"
  [[ "${SEED:-0}" == 0 ]] || { echo 'wideview 固定 SEED=0' >&2; exit 2; }
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/wideview.py" verify --assets "$SCENE_ASSETS" --array "$WIDEVIEW_ARRAY" --runtime
fi
if [[ "$stage" == viewcheck || "$stage" == studioview ]]; then
  [[ "${SEED:-0}" == 0 ]] || { echo "$stage 固定 SEED=0，与 70462 一致。" >&2; exit 2; }
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/$stage.py" verify --assets "$SCENE_ASSETS" --runtime
fi
if [[ "$stage" == gallery ]]; then
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/gallery.py" verify --assets "$SCENE_ASSETS" --array "$GALLERY_ARRAY" --runtime
fi
if [[ "$stage" == angles ]]; then
  "$PYTHON_BIN" -B "$SCENE_CODE/tools/angles.py" verify --assets "$SCENE_ASSETS" --array "$ANGLES_ARRAY" --runtime
fi
args=(--parsable --partition="$PARTITION"
      --nodes=1 --ntasks=1 --gres=gpu:1 --cpus-per-task="$CPUS" --mem="$MEM"
      --time="$TIME_LIMIT" --job-name="scene-$stage" --chdir="$SCENE_CODE"
      --output="$SCENE_LOGS/$stage-%A_%a.out" --error="$SCENE_LOGS/$stage-%A_%a.err" --export=ALL)
[[ -z "$ACCOUNT" ]] || args+=(--account="$ACCOUNT")
[[ -z "$QOS" ]] || args+=(--qos="$QOS")
[[ -z "$NODE" ]] || args+=(--nodelist="$NODE")
[[ "$stage" != check ]] || args+=(--time=00:20:00)
[[ "$stage" != batch ]] || args+=(--array=0-3%4)
[[ "$stage" != showcase ]] || args+=(--array="$SHOWCASE_ARRAY")
[[ "$stage" != gallery ]] || args+=(--array="$GALLERY_ARRAY")
[[ "$stage" != angles ]] || args+=(--array="$ANGLES_ARRAY")
[[ "$stage" != wideview ]] || args+=(--array="$WIDEVIEW_ARRAY")
[[ -z "${DEPENDENCY:-}" ]] || args+=(--dependency="afterok:$DEPENDENCY")
job=$(sbatch "${args[@]}" "$SCENE_CODE/slurm/job.sh" "$stage")
job=${job%%;*}
printf '%s\n' "$job" > "$SCENE_STATE/$stage.jobid"
printf '%s\n' "$job"
