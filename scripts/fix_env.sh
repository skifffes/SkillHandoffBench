#!/usr/bin/env bash
# SkillHandoffBench: 环境收尾（修正 v2 的 4 个具体问题）。
#
# v2 真实问题（logs/setup_v2.log）：
#   1) torch 2.4.1 把 numpy 带到 2.2.6、pillow 到 12.2.0 —— Motus 要求 numpy<2；
#   2) `--only-binary=:all:` 让 omegaconf==2.3.0 失败：它要 antlr4-python3-runtime==4.9.*，
#      而 4.9.3 只发 sdist（无 wheel）→ 整个 stage 2 事务回滚，sapien/mplib 全没装上；
#   3) diffusers 0.41.0 需要 torch>=2.10 的 torch.accelerator API，与 torch 2.4.1 不兼容；
#   4) 因此 import 验证大面积 FAIL。
#
# 对策：分开装，允许纯 Python 的 sdist（不含 C 扩展的包不需要编译器）。
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
PY="$ROOT/envs/motus/bin/python"
IDX="${PIP_INDEX_URL:-https://pypi.org/simple}"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
WHEEL="$PY -m pip install --no-input --disable-pip-version-check -i $IDX --only-binary=:all:"
ANY="$PY -m pip install --no-input --disable-pip-version-check -i $IDX"

say "=== 1) 降级 numpy / diffusers ==="
$WHEEL "numpy==1.26.4" "diffusers==0.31.0" 2>&1 | tail -3

say "=== 2) omegaconf（允许 antlr4 sdist）==="
$ANY "antlr4-python3-runtime==4.9.3" 2>&1 | tail -2
$ANY "omegaconf==2.3.0" 2>&1 | tail -2

say "=== 3) 仿真栈（wheel-only）==="
$WHEEL \
  "opencv-python==4.10.0.84" "imageio==2.34.2" "imageio-ffmpeg==0.5.1" \
  "matplotlib==3.9.2" "easydict==1.13" "ftfy==6.2.3" "einops==0.8.1" \
  "trimesh==4.4.3" "gymnasium==0.29.1" "h5py==3.11.0" "scipy==1.13.1" "tqdm==4.66.5" 2>&1 | tail -4

say "=== 4) sapien / mplib / toppra / transforms3d（逐个装，看清谁失败）==="
for pkg in "sapien==3.0.0b1" "mplib==0.2.1" "toppra==0.6.11" "transforms3d==0.4.2"; do
  say "install $pkg"
  $WHEEL "$pkg" 2>&1 | tail -2 || say "WHEEL-ONLY FAILED: $pkg, retry allowing sdist"
  "$PY" -c "import importlib,sys; m='${pkg%%==*}'; importlib.import_module(m); print('OK', m)" 2>/dev/null \
    || $ANY "$pkg" 2>&1 | tail -3
done

say "=== 5) import 验证 ==="
"$PY" - <<'PYEOF'
import importlib
mods = ["numpy","torch","torchvision","sapien","mplib","toppra","transforms3d","trimesh",
        "h5py","cv2","imageio","yaml","easydict","omegaconf","einops","safetensors",
        "transformers","tokenizers","accelerate","diffusers","qwen_vl_utils"]
bad=[]
for m in mods:
    try:
        mod=importlib.import_module(m)
        print(f"OK   {m} {getattr(mod,'__version__','')}")
    except Exception as exc:
        bad.append(m); print(f"FAIL {m}: {type(exc).__name__}: {exc}")
import numpy, torch
print("numpy", numpy.__version__, "| torch", torch.__version__, torch.version.cuda, "avail", torch.cuda.is_available())
raise SystemExit(1 if bad else 0)
PYEOF
say "fix done (exit=$?)"
