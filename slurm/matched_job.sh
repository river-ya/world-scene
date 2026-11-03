#!/usr/bin/env bash
# Resource command: docs/PAIRED_COMPARISON.md.
set -euo pipefail
source "${SCENE_CODE:?请按 PAIRED_COMPARISON.md 提交}/slurm/config.sh"
export PATH="$SCENE_ENV/bin:$PATH"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
mkdir -p "$SCENE_ASSETS/tmp" "$SCENE_LOGS"
export TMPDIR
TMPDIR=$(mktemp -d "$SCENE_ASSETS/tmp/job-${SLURM_JOB_ID:?}.XXXXXX")
cleanup() {
  if [[ "$TMPDIR" == "$SCENE_ASSETS/tmp/job-${SLURM_JOB_ID}."* ]]; then rm -rf -- "$TMPDIR"; fi
}
trap cleanup EXIT
export GRADIO_TEMP_DIR="$TMPDIR/gradio"
"$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" check
"$PYTHON_BIN" -B "$SCENE_CODE/tools/assets.py" verify --root "$SCENE_ASSETS" --group models --quick
"$PYTHON_BIN" -B "$SCENE_CODE/tools/experiment.py" run \
  --inputs "$SCENE_CODE/examples/paired-room40" --run-root "$SCENE_RUNS" \
  --name "matched-room40-$SLURM_JOB_ID" --seed 0
