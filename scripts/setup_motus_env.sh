#!/usr/bin/env bash
# SkillHandoffBench: 建 Motus 独立运行环境（不覆盖 simulate_vla/venv、不动 openpi/.venv）。
# 目标：一个 py3.10 venv，同时满足 (a) RoboCombine 的仿真依赖 sapien/mplib、(b) Motus 的 torch/transformers。
# 设计取舍：
#   - torch 2.4.1 + cu124：与 RoboCombine pyproject 的 pin 一致，driver 550.120 支持 CUDA 12.4
#   - sapien==3.0.0b1 / mplib==0.2.1：与 pyproject pin 一致
#   - transformers 用 Motus 侧要求（Qwen3-VL 需要新版本），不跟随 pyproject 的 4.53.2
#   - flash_attn / deepspeed **不装**：本机无 nvcc（gcc 4.8.5），且 Motus 推理路径不 import 它们；
#     若后续证明必需，再单独评估（见 docs/01 的 BLOCKED 记录）
# 用法：bash scripts/setup_motus_env.sh
set -uo pipefail

ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
VENV="$ROOT/envs/motus"
LOGD="$ROOT/logs"
mkdir -p "$LOGD" "$ROOT/envs"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export UV_CACHE_DIR="${UV_CACHE_DIR:-/scratch/lijh/SkillHandoffBench/.uv_cache}"
export UV_LINK_MODE=copy
UV="${UV_BIN:-$HOME/.local/bin/uv}"

if [ ! -x "$VENV/bin/python" ]; then
  say "create venv: $VENV"
  "$UV" venv "$VENV" --python 3.10 2>&1 | tail -5
fi
PY="$VENV/bin/python"
say "python: $($PY -V 2>&1)"

PIP_ARGS="--no-input --disable-pip-version-check"
"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PY" -m pip install $PIP_ARGS -U pip setuptools wheel 2>&1 | tail -3

say "=== stage 1: torch 2.4.1 cu124 ==="
"$PY" -m pip install $PIP_ARGS --index-url https://download.pytorch.org/whl/cu124 \
  "torch==2.4.1" "torchvision==0.19.1" 2>&1 | tail -8

say "=== stage 2: simulator stack (sapien/mplib/...) ==="
"$PY" -m pip install $PIP_ARGS \
  "sapien==3.0.0b1" "mplib==0.2.1" "toppra" "transforms3d" "trimesh==4.4.3" \
  "gymnasium==0.29.1" "h5py" "opencv-python" "imageio==2.34.2" "imageio-ffmpeg" \
  "matplotlib" "pyyaml" "easydict" "ftfy" "omegaconf==2.3.0" "einops==0.8.1" "safetensors" \
  "numpy<2" "scipy" "tqdm" "pillow" 2>&1 | tail -8

say "=== stage 3: Motus stack (transformers for Qwen3-VL / Wan2.2) ==="
"$PY" -m pip install $PIP_ARGS \
  "transformers==5.0.0rc0" "tokenizers" "accelerate" "diffusers" "qwen-vl-utils" \
  "dashscope" "decord" 2>&1 | tail -8

say "=== stage 4: verify imports ==="
"$PY" - <<'PYEOF'
import importlib, sys
mods = ["numpy","torch","torchvision","sapien","mplib","toppra","transforms3d","trimesh",
        "h5py","cv2","imageio","yaml","easydict","omegaconf","einops","safetensors",
        "transformers","tokenizers","accelerate","diffusers"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f"OK   {m} {getattr(mod,'__version__','')}")
    except Exception as exc:
        print(f"FAIL {m}: {type(exc).__name__}: {exc}")
import torch
print("torch cuda:", torch.__version__, torch.version.cuda, "avail:", torch.cuda.is_available())
PYEOF
say "setup done"
