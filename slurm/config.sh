#!/usr/bin/env bash
SCENE_CODE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export SCENE_CODE
if [[ -f "$SCENE_CODE/local.env" ]]; then source "$SCENE_CODE/local.env"; fi
export SCENE_VERSION
SCENE_VERSION=$(tr -d '\r\n' < "$SCENE_CODE/VERSION")
export DATA_ROOT="${DATA_ROOT:-${HOME}/world-scene-data}"
export SCENE_ASSETS="${SCENE_ASSETS:-$DATA_ROOT/world_scene_assets}"
export SCENE_ENV="${SCENE_ENV:-$DATA_ROOT/envs/world-scene-$SCENE_VERSION}"
export SCENE_RUNS="${SCENE_RUNS:-$DATA_ROOT/runs/world_scene/v$SCENE_VERSION}"
export SCENE_LOGS="${SCENE_LOGS:-$DATA_ROOT/logs/world_scene/v$SCENE_VERSION}"
export SCENE_STATE="${SCENE_STATE:-$DATA_ROOT/state/world_scene/v$SCENE_VERSION}"
export PARTITION="${PARTITION:-gpu}" ACCOUNT="${ACCOUNT:-}" QOS="${QOS:-}"
export NODE="${NODE-}" CPUS="${CPUS:-8}" MEM="${MEM:-96G}"
export TIME_LIMIT="${TIME_LIMIT:-04:00:00}"
export HF_HOME="$SCENE_ASSETS/hf" HF_HUB_CACHE="$SCENE_ASSETS/hf/hub"
unset TRANSFORMERS_CACHE PYTORCH_TRANSFORMERS_CACHE PYTORCH_PRETRAINED_BERT_CACHE
export TORCH_HOME="$SCENE_ASSETS/torch_cache"
export TORCH_EXTENSIONS_DIR="$DATA_ROOT/torch_extensions/world-scene-$SCENE_VERSION"
export CONDA_PKGS_DIRS="$DATA_ROOT/conda_pkgs" PIP_CACHE_DIR="$DATA_ROOT/pip_cache/world-scene"
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export PYTHON_BIN="$SCENE_ENV/bin/python"
export TORCH_CUDA_ARCH_LIST=8.9
