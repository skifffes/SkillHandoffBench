#!/usr/bin/env bash
# SkillHandoffBench Phase 2 · Gate D：启用/停用日志的 A/B 对照。
#
# 三次运行，**同一任务同一 seed**（living_room_tidy_2tasks / 4300000 / 1 episode）：
#   R1 off          无任何 trace 环境变量
#   R2 actions_only 只记录 action 序列（最小开销）
#   R3 full         记录 action + 关节/末端/物体/夹爪/cache 等完整状态
#
# 判定（由 compare_trace_ab.py 自动做）：
#   - R1.R2.R3 的 evaluation_statistics 关键字段必须逐位相同；
#   - 三份 task.log 归一化（去掉 step_time 与时序）后必须逐行相同；
#   - R2 与 R3 记录的 action 序列必须逐元素相同（容差 0，可放宽到 1e-9）；
#   - trace 代码不得调用任何 RNG（静态检查）。
#
# 用法：bash scripts/run_trace_ab.sh
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PY:-$SHB_ROOT/envs/motus/bin/python}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
TASK="${TASK:-living_room_tidy_2tasks}"
EPISODES="${EPISODES:-1}"
BASE_SEED="${BASE_SEED:-42}"
P2="$SHB_ROOT/results/phase2"
TRACE_DIR="$P2/trace"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export CUDA_VISIBLE_DEVICES="${SHB_GPU:-0}"
export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export MOTUS_SAVE_IMAGES="${MOTUS_SAVE_IMAGES:-0}"
VK_LIB_DIR="${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}"
XLIB_DIR="${XLIB_DIR:-$SHB_ROOT/envs/xlib/usr/lib64}"
CUDA_HOME_LOCAL="${CUDA_HOME_LOCAL:-$SHB_ROOT/envs/cuda_home}"
CONDA_CC_LIB="${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}"
export LD_LIBRARY_PATH="$XLIB_DIR:$VK_LIB_DIR:$CONDA_CC_LIB:$CUDA_HOME_LOCAL/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

mkdir -p "$TRACE_DIR"

run_one() {  # <tag> <trace_env...>
  local tag="$1"; shift
  local out="$P2/trace/$tag"
  mkdir -p "$out"
  say "=== $tag ==="
  ( cd "$RC" && env "$@" timeout --signal=TERM 1800 "$PY" handoff_eval/runner/run_split.py \
      --spec robocombine --track oracle_hse --policy Motus \
      --checkpoint "$CKPT" --checkpoint-label motus_robotwin2_official \
      --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
      --episodes "$EPISODES" --task-filter "$TASK" \
      --base-seed "$BASE_SEED" --clear-cache false \
      --output-root "$out" ) 2>&1 | tee "$TRACE_DIR/$tag.run.log"
  say "=== $tag exit=${PIPESTATUS[0]} ==="
}

# R1: 完全不开 trace
run_one ab_off

# R2: 只记录 action
run_one ab_actions_only "SHB_TRACE_JSONL=$TRACE_DIR/actions_only.jsonl" "SHB_TRACE_ACTIONS_ONLY=1"

# R3: 完整状态
run_one ab_full "SHB_TRACE_JSONL=$TRACE_DIR/full.jsonl"

say "done; traces in $TRACE_DIR"
ls -la "$TRACE_DIR"
