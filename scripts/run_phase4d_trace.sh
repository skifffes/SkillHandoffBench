#!/usr/bin/env bash
# Phase 4D：4 个 interaction 任务 × 2 个固定 seed × oracle_hse，带被动 trace。
#
# 与历史 run 完全相同的协议参数（checkpoint / episodes / steps / clear-cache / base-seed），
# 唯一新增：SHB_TRACE_JSONL（被动记录，未设时不生效，见 docs/08 的 A/B 非干预证据）。
#
# 用法：
#   bash scripts/run_phase4d_trace.sh 1     # 第 1 组（room_comfort, kitchen_switch）
#   bash scripts/run_phase4d_trace.sh 2     # 第 2 组（smart_home, bakery_close）
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PYTHON_BIN:-$SHB_ROOT/envs/motus/bin/python}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
OUT="$SHB_ROOT/results/phase4d_trace"
LOG="$SHB_ROOT/logs/phase4d_trace"
mkdir -p "$OUT" "$LOG"

export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export MOTUS_SAVE_IMAGES=0
export LD_LIBRARY_PATH="$SHB_ROOT/envs/xlib/usr/lib64:/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib:/scratch/lijh/.conda/envs/gdino_fix/lib:$SHB_ROOT/envs/cuda_home/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# <task> <seed1> <seed2> <gpu>
run_task() {
  local task="$1" s1="$2" s2="$3" gpu="$4"
  local dir="$OUT/$task"
  local seeds="$OUT/${task}_seeds.txt"
  mkdir -p "$dir"
  printf '%s\n%s\n' "$s1" "$s2" > "$seeds"
  say "START $task seeds=$s1,$s2 gpu=$gpu -> $dir"
  ( cd "$RC" && env CUDA_VISIBLE_DEVICES="$gpu" SHB_TRACE_JSONL="$OUT/${task}.jsonl" \
      timeout --signal=TERM 7200 "$PY" script/eval_policy.py \
        --config "$RC/policy/Motus/deploy_policy.yml" --overrides \
        --task_name "$task" --task_config robocombine_eval --policy_name Motus \
        --seed 42 --episode_num 2 \
        --ckpt_setting "$CKPT" --ckpt_setting_label motus_robotwin2_official \
        --save_dir "$dir" --log_dir "$dir" \
        --hse_variant oracle_hse --clear_cache false --max_steps_per_episode 1500 \
        --wan_path "$WAN" --vlm_path "$VLM" \
        --priority_seeds_file "$seeds" ) > "$LOG/${task}.log" 2>&1
  say "END   $task exit=$? (log: $LOG/${task}.log)"
}

case "${1:-}" in
  1)
    run_task room_comfort_2tasks    4300001 4300000 ${GPU_A:-2} &
    sleep 8
    run_task kitchen_switch_2tasks  4300002 4300029 ${GPU_B:-3} &
    wait
    ;;
  2)
    run_task smart_home_2tasks      4300017 4300011 ${GPU_A:-2} &
    sleep 8
    run_task bakery_close_2tasks    4300006 4300004 ${GPU_B:-3} &
    wait
    ;;
  *) echo "usage: $0 {1|2}"; exit 2 ;;
esac
