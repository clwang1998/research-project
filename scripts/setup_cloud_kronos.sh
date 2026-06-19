#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
PYTORCH_INDEX_URL="${PYTORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
KRONOS_ROOT="${KRONOS_ROOT:-external/Kronos}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip

# Project/report dependencies.
python -m pip install -r requirements.txt

# Kronos runtime dependencies not present in the base report requirements.
python -m pip install \
  einops==0.8.1 \
  huggingface_hub==0.33.1 \
  safetensors==0.6.2 \
  tqdm \
  matplotlib \
  comet_ml

# Install CUDA PyTorch if the environment does not already provide a CUDA build.
if ! python - <<'PY'
import sys
try:
    import torch
    sys.exit(0 if torch.cuda.is_available() else 1)
except Exception:
    sys.exit(1)
PY
then
  python -m pip install torch --index-url "$PYTORCH_INDEX_URL"
fi

if [[ ! -d "$KRONOS_ROOT/.git" ]]; then
  mkdir -p "$(dirname "$KRONOS_ROOT")"
  git clone --depth=1 https://github.com/shiyu-coder/Kronos.git "$KRONOS_ROOT"
fi

python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda_available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("cuda_device:", torch.cuda.get_device_name(0))
PY

echo "Cloud Kronos setup complete."
