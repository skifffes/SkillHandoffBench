#!/usr/bin/env bash
# 等指定 PID 结束后，依次跑 Gate E 的 deep 批次（2 任务 × 20 episodes，oracle → full_inst）。
# 用法：bash scripts/watch_paper_gateE.sh <pid-to-wait-for>
set -uo pipefail
SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
PID="${1:?usage: $0 <pid>}"
while kill -0 "$PID" 2>/dev/null; do sleep 20; done
cd "$SHB_ROOT" || exit 1
echo "[watch] $(date +%H:%M:%S) preflight pid $PID finished; starting deep oracle_hse"
bash scripts/run_paper_reproduction.sh deep oracle_hse
echo "[watch] $(date +%H:%M:%S) deep oracle_hse done; starting deep full_inst"
bash scripts/run_paper_reproduction.sh deep full_inst
echo "[watch] $(date +%H:%M:%S) all deep batches finished"
