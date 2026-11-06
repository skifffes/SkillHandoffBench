#!/usr/bin/env bash
# SkillHandoffBench: 反复重试 curobo 的 CUDA 扩展构建。
#
# 现象（logs/curobo_setuppy2.log）：ninja 在并行编译时会有**某个 .cu 的 .o 没产出**，
# 但不打印 nvcc 的报错；用 `ninja -v -j1` 单独编同一个文件却能成功。
# 因此按"增量重试"处理：ninja 只重建缺失目标，每轮都会多完成一个扩展，
# 直到 build_ext 成功或连续两轮没有新的 .so 出现。
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
SRC="$ROOT/third_party/curobo076"
PY="$ROOT/envs/motus/bin/python"
LOG="$ROOT/logs/curobo_retry.log"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export CC=/scratch/lijh/.conda/envs/gdino_fix/bin/x86_64-conda-linux-gnu-gcc
export CXX=/scratch/lijh/.conda/envs/gdino_fix/bin/x86_64-conda-linux-gnu-g++
export CUDA_HOME="$ROOT/envs/cuda_home"; export CUDA_PATH="$CUDA_HOME"
export TORCH_CUDA_ARCH_LIST=8.6; export MAX_JOBS=1
export PATH="$CUDA_HOME/bin:/scratch/lijh/.conda/envs/gdino_fix/bin:$PATH"
export LD_LIBRARY_PATH="/scratch/lijh/.conda/envs/gdino_fix/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
cd "$SRC" || exit 2
: > "$LOG"

for i in $(seq 1 25); do
  before=$(ls build/lib.linux-x86_64-cpython-310/curobo/curobolib/*.so 2>/dev/null | wc -l)
  say "=== round $i (so=$before) ==="
  if "$PY" setup.py build_ext --inplace >> "$LOG" 2>&1; then
    say "build_ext OK after $i rounds"
    break
  fi
  after=$(ls build/lib.linux-x86_64-cpython-310/curobo/curobolib/*.so 2>/dev/null | wc -l)
  say "round $i failed (so=$after)"
  if [ "$after" = "$before" ]; then
    say "no progress in round $i -> stop"
    break
  fi
done

say "=== result ==="
ls build/lib.linux-x86_64-cpython-310/curobo/curobolib/*.so 2>/dev/null
"$PY" setup.py build_ext --inplace >/dev/null 2>&1 && say "FINAL OK" || say "FINAL FAILED"
