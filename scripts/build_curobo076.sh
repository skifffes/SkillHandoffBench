#!/usr/bin/env bash
# SkillHandoffBench: 构建 CuRobo **v0.7.6**（RoboCombine 的 planner.py 用的是 v0.7 的旧 API）。
#
# 为什么不是 main：main（v0.9，commit 299d7a6）已改成 `curobo/_src/**` + `curobo/motion_planner.py`，
# 不再有 `curobo.types.math.Pose` / `curobo.wrap.reacher.motion_gen.MotionGen`，
# 而 `envs/robot/planner.py:26-31` 正是 import 这些旧路径。
#
# 工具链（全部用户空间）：
#   nvcc  : pip `nvidia-cuda-nvcc-cu12`（12.9.x；torch 2.4.1 是 cu121，同 major，minor 兼容）
#   gcc   : 复用本机 conda-forge gcc 11（系统 gcc 4.8.5 不被 CUDA 12 支持）
#   arch  : A40 = sm_86
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
PY="$ROOT/envs/motus/bin/python"
SRC="$ROOT/third_party/curobo076"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

[ -d "$SRC/src/curobo" ] || { say "MISSING $SRC"; exit 2; }

NVCC_DIR="${CUDA_HOME:-$ROOT/envs/cuda121}"
[ -x "$NVCC_DIR/bin/nvcc" ] || { say "MISSING nvcc at $NVCC_DIR/bin/nvcc（先跑 scripts/setup_nvcc.sh）"; exit 3; }
CC_BIN=""
for cand in /scratch/lijh/.conda/envs/gdino_fix/bin /scratch/lijh/.conda/pkgs/gcc_impl_linux-64-11.2.0-h1234567_1/bin; do
  [ -x "$cand/x86_64-conda-linux-gnu-gcc" ] && CC_BIN="$cand" && break
done
say "nvcc=$NVCC_DIR"; say "cc=$CC_BIN"

export CC="$CC_BIN/x86_64-conda-linux-gnu-gcc"
export CXX="$CC_BIN/x86_64-conda-linux-gnu-g++"
export CUDA_HOME="$NVCC_DIR"
export CUDA_PATH="$NVCC_DIR"
export TORCH_CUDA_ARCH_LIST="8.6"
export MAX_JOBS="${MAX_JOBS:-8}"
export PATH="$NVCC_DIR/bin:$CC_BIN:$PATH"
export LD_LIBRARY_PATH="$CC_BIN/lib:$NVCC_DIR/lib:${LD_LIBRARY_PATH:-}"

say "=== 依赖（--no-deps 逐个）==="
"$PY" -m pip install --no-input -q --no-deps "warp-lang==1.6.2" "numpy-quaternion" "yourdfpy" "pyyaml" "trimesh" "scipy" 2>&1 | tail -2

say "=== build curobo v0.7.6 ==="
cd "$SRC" || exit 2
"$PY" -m pip install --no-input --no-deps --no-build-isolation -e . 2>&1 | tail -30

say "=== import 测试 ==="
cd "$ROOT"
"$PY" -c "
from curobo.types.math import Pose
from curobo.types.robot import JointState
from curobo.wrap.reacher.motion_gen import MotionGen, MotionGenConfig
print('curobo import OK')
" 2>&1 | tail -8
say "done"
