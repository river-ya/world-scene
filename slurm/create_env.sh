#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
command -v conda >/dev/null
command -v nvcc >/dev/null
nvcc --version
gcc --version
if [[ ! -x "$PYTHON_BIN" ]]; then conda create -y --prefix "$SCENE_ENV" python=3.10 pip; fi
export PATH="$SCENE_ENV/bin:$PATH"
"$PYTHON_BIN" -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
"$PYTHON_BIN" -m pip install -r "$SCENE_CODE/requirements-runtime.txt"
"$PYTHON_BIN" -m pip install --no-build-isolation 'git+https://github.com/nerfstudio-project/gsplat.git@32f2a54d21c7ecb135320bb02b136b7407ae5712'
"$PYTHON_BIN" -m pip install 'git+https://github.com/huggingface/diffusers.git@447e8322f76efea55d4769cd67c372edbf0715b8'
"$PYTHON_BIN" -m pip install 'git+https://github.com/nianticlabs/spz.git@a4fc69e7948c7152e807e6501d73ddc9c149ce37'
"$PYTHON_BIN" -m pip check
mkdir -p "$SCENE_STATE"
"$PYTHON_BIN" -m pip freeze > "$SCENE_STATE/environment.freeze.txt"
"$PYTHON_BIN" - <<'PY'
import importlib.util, torch
assert torch.__version__.split('+')[0]=='2.6.0'
assert torch.version.cuda=='12.4', torch.version.cuda
assert importlib.util.find_spec('spaces') is None, '不要在本地环境安装 Spaces 专用包'
print('依赖安装完成；尚需提交 GPU check 和 smoke。')
PY
