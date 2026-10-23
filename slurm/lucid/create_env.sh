#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
command -v conda >/dev/null
command -v curl >/dev/null
mkdir -p "$LUCID_STATE" "$LUCID_ASSETS/tmp"
exec 9>"$LUCID_STATE/environment-install.lock"
flock -n 9 || { echo '另一个安装进程正在运行' >&2; exit 2; }
python3 -B "$LUCID_CODE/tools/lucid_assets.py" source-check
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
# CUDA compiler and C++ compiler are isolated; no modification of /usr/local/cuda.
if [[ ! -x "$LUCID_PYTHON" ]]; then
  conda create -y --prefix "$LUCID_ENV" --override-channels \
    -c nvidia/label/cuda-11.8.0 -c conda-forge \
    python=3.9 pip cuda-toolkit=11.8 gcc_linux-64=11 gxx_linux-64=11
fi
export PATH="$LUCID_ENV/bin:$PATH" CUDA_HOME="$LUCID_ENV"
export CC="$LUCID_ENV/bin/x86_64-conda-linux-gnu-cc"
export CXX="$LUCID_ENV/bin/x86_64-conda-linux-gnu-c++"
export LD_LIBRARY_PATH="$LUCID_ENV/lib:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST=8.9 MAX_JOBS="${LUCID_BUILD_JOBS:-2}"
[[ -x "$CC" && -x "$CXX" && -x "$CUDA_HOME/bin/nvcc" ]] || {
  echo '独立环境不完整：需要 CUDA 11.8 和 conda GCC/G++ 11；见手册恢复安装段。' >&2; exit 2;
}
"$CUDA_HOME/bin/nvcc" --version | grep -q 'release 11.8'
"$LUCID_PYTHON" -m pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cu118
"$LUCID_PYTHON" -m pip install -r "$LUCID_CODE/requirements-lucid.txt" \
  -c "$LUCID_CODE/constraints-lucid-py39.txt"
# Compile from a disposable copy, keeping released sources immutable.
build=$(mktemp -d "$LUCID_ASSETS/tmp/build.XXXXXX")
trap 'rm -rf -- "$build"' EXIT
cp -a "$LUCID_CODE/upstream/LucidDreamer/submodules" "$build/"
mkdir -p "$build/submodules/depth-diff-gaussian-rasterization-min/third_party/glm"
cp -a "$LUCID_CODE/upstream/glm/glm" "$build/submodules/depth-diff-gaussian-rasterization-min/third_party/glm/"
"$LUCID_PYTHON" -m pip install --no-build-isolation --no-deps \
  "$build/submodules/depth-diff-gaussian-rasterization-min" "$build/submodules/simple-knn"
"$LUCID_PYTHON" -m pip check
"$LUCID_PYTHON" -m pip freeze > "$LUCID_STATE/environment.freeze.txt"
conda list --prefix "$LUCID_ENV" --explicit > "$LUCID_STATE/conda-explicit.txt"
python3 -B "$LUCID_CODE/tools/lucid_assets.py" source-check
echo '独立环境已安装；接着下载权重、完整校验，并提交 lucid check。'
