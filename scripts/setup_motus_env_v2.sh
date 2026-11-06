#!/usr/bin/env bash
# SkillHandoffBench: Motus 运行环境 v2（修正 v1 的三个真实失败）。
#
# v1 的失败（日志 logs/setup_motus_env.log）：
#   1) `--index-url download.pytorch.org/whl/cu124` 让 torchvision 的构建依赖（pillow→pybind11）
#      也去 pytorch 索引找 → 那里没有 → 整个事务回滚 → torch 一个都没装；
#   2) 未 pin 的 pillow / h5py / av 解析到**没有 cp310 wheel** 的新版本 → 走 sdist 源码编译
#      → 本机 gcc 4.8.5 + 无 libjpeg/libswresample 头 → 失败；
#   3) 因此 stage 4 全量 import 失败。
#
# v2 对策：
#   - 全部走 PyPI（torch 2.4.1 的 PyPI 轮子是 cu121，driver 550.120 支持；A40=sm_86 覆盖）；
#   - `--only-binary=:all:` 强制只接受 wheel（保证不再触发源码编译）；
#   - 关键包全部 pin 到**确认有 cp310 manylinux2014 轮子**的版本。
#
# 用法：bash scripts/setup_motus_env_v2.sh
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
VENV="$ROOT/envs/motus"
PY="$VENV/bin/python"
IDX="${PIP_INDEX_URL:-https://pypi.org/simple}"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
PIP="$PY -m pip install --no-input --disable-pip-version-check -i $IDX --only-binary=:all:"

say "python: $($PY -V 2>&1)"

say "=== stage 1: torch 2.4.1 (cu121 wheels, PyPI) ==="
$PIP "torch==2.4.1" "torchvision==0.19.1" 2>&1 | tail -6

say "=== stage 2: 仿真栈（sapien/mplib/...，全部 pin）==="
$PIP \
  "numpy==1.26.4" "pillow==10.4.0" "h5py==3.11.0" "scipy==1.13.1" \
  "opencv-python==4.10.0.84" "imageio==2.34.2" "imageio-ffmpeg==0.5.1" \
  "matplotlib==3.9.2" "pyyaml==6.0.2" "tqdm==4.66.5" "safetensors==0.4.5" \
  "easydict==1.13" "ftfy==6.2.3" "omegaconf==2.3.0" "einops==0.8.1" \
  "trimesh==4.4.3" "transforms3d==0.4.2" "gymnasium==0.29.1" "toppra==0.6.11" \
  "sapien==3.0.0b1" "mplib==0.2.1" 2>&1 | tail -8

say "=== stage 3: Motus 栈（Qwen3-VL 需要新 transformers）==="
$PIP \
  "transformers==5.0.0rc0" "accelerate" "diffusers" "qwen-vl-utils" \
  "regex" "requests" "pytest" 2>&1 | tail -8

say "=== stage 4: import 验证 ==="
"$PY" - <<'PYEOF'
import importlib
mods = ["numpy", "torch", "torchvision", "sapien", "mplib", "toppra", "transforms3d",
        "trimesh", "h5py", "cv2", "imageio", "yaml", "easydict", "omegaconf", "einops",
        "safetensors", "transformers", "tokenizers", "accelerate", "diffusers"]
bad = []
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f"OK   {m} {getattr(mod, '__version__', '')}")
    except Exception as exc:
        bad.append(m)
        print(f"FAIL {m}: {type(exc).__name__}: {exc}")
import torch
print("torch:", torch.__version__, "cuda:", torch.version.cuda, "avail:", torch.cuda.is_available())
raise SystemExit(1 if bad else 0)
PYEOF
say "setup v2 done (exit=$?)"
