#!/usr/bin/env bash
# SkillHandoffBench: 在用户空间拿到真正的 `nvcc`（pip 的 nvidia-cuda-nvcc-cu12 只有 ptxas，没有 nvcc）。
#
# 做法：microMamba（静态二进制，不需要 root）+ conda-forge/nvidia 的 cuda-nvcc 12.1。
# 产物：$ROOT/envs/cuda/bin/nvcc（供 torch cpp_extension 用 CUDA_HOME 指向）。
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
MM="$ROOT/envs/_mm"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p "$MM" "$ROOT/envs"

if [ ! -x "$MM/bin/micromamba" ]; then
  say "download micromamba"
  curl -sL --fail -o /tmp/micromamba.tar.bz2 "https://micro.mamba.pm/api/micromamba/linux-64/latest" || exit 3
  tar xjf /tmp/micromamba.tar.bz2 -C "$MM" --strip-components=1 bin/micromamba
fi
"$MM/bin/micromamba" --version

say "=== create cuda env with nvcc 12.1 ==="
export MAMBA_ROOT_PREFIX="$MM/root"
"$MM/bin/micromamba" create -y -p "$ROOT/envs/cuda121" \
  -c conda-forge -c nvidia "cuda-nvcc=12.1" "cuda-cudart-dev=12.1" 2>&1 | tail -15

say "=== verify ==="
"$ROOT/envs/cuda121/bin/nvcc" --version 2>&1 | tail -3
ls "$ROOT/envs/cuda121/include" 2>/dev/null | head -5
