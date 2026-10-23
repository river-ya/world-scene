#!/usr/bin/env bash
# Deliberately independent from slurm/config.sh and its inherited FlashWorld vars.
export LUCID_CODE
LUCID_CODE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
if [[ -f "$LUCID_CODE/lucid.env" ]]; then source "$LUCID_CODE/lucid.env"; fi
export LUCID_VERSION
LUCID_VERSION=$(tr -d '\r\n' < "$LUCID_CODE/VERSION")
export LUCID_DATA_ROOT="${LUCID_DATA_ROOT:-${HOME}/world-scene-data}"
export LUCID_ENV="${LUCID_ENV:-$LUCID_DATA_ROOT/envs/world-scene-lucid-0.7.0}"
export LUCID_ASSETS="${LUCID_ASSETS:-$LUCID_DATA_ROOT/world_scene_lucid_assets}"
export LUCID_RUNS="$LUCID_DATA_ROOT/runs/world_scene_lucid/v$LUCID_VERSION"
export LUCID_LOGS="$LUCID_DATA_ROOT/logs/world_scene_lucid/v$LUCID_VERSION"
export LUCID_STATE="$LUCID_DATA_ROOT/state/world_scene_lucid/v$LUCID_VERSION"
export SCENE_ASSETS="$LUCID_DATA_ROOT/world_scene_assets"
export LUCID_PYTHON="$LUCID_ENV/bin/python"
export LUCID_PARTITION="${LUCID_PARTITION:-gpu}" LUCID_ACCOUNT="${LUCID_ACCOUNT:-}"
export LUCID_QOS="${LUCID_QOS:-}" LUCID_NODE="${LUCID_NODE-}"
export LUCID_CPUS="${LUCID_CPUS:-8}" LUCID_MEM="${LUCID_MEM:-64G}"
export LUCID_TIME="${LUCID_TIME:-08:00:00}" LUCID_ARRAY="${LUCID_ARRAY:-1%1}"
export HF_HOME="$LUCID_ASSETS/hf" HF_HUB_CACHE="$LUCID_ASSETS/hf/hub"
export TORCH_HOME="$LUCID_ASSETS/torch" GRADIO_ANALYTICS_ENABLED=False
export TORCH_EXTENSIONS_DIR="$LUCID_DATA_ROOT/torch_extensions/world-scene-lucid-0.7.0"
export CONDA_PKGS_DIRS="$LUCID_DATA_ROOT/conda_pkgs"
export PIP_CACHE_DIR="$LUCID_DATA_ROOT/pip_cache/world-scene-lucid"
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
unset TRANSFORMERS_CACHE PYTORCH_TRANSFORMERS_CACHE PYTORCH_PRETRAINED_BERT_CACHE
