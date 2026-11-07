#!/usr/bin/env bash
# SkillHandoffBench Phase 3A 运行器（Gate B / Gate C / Gate D）。
#
# 为什么要直接调 eval_policy 而不是 run_split：
#   - Gate B 要**重复同一个已知 seed**（4300003 / 4300000），run_split 只按 st_seed 递增，
#     唯一能钉住 seed 的官方入口是 eval_policy 的 `--priority_seeds_file`（run_split 只有在
#     spec 里带 seed_receipt 时才会传它，而公开 spec 里没有 seed_receipt）。
#   - Gate C 的 B0 是**原子任务**（RoboTwin 上游 envs），RoboCombine 的 spec 里没有这些任务名，
#     所以同样走 eval_policy + `--task_name`。
# 其余参数与 Phase 2 的 oracle_hse 运行逐项一致（checkpoint / clear_cache=false / 1500 步 / clean 场景）。
#
# 用法：
#   bash scripts/run_phase3.sh b     # Gate B：2 个已知失败案例 × 各重复 2 次 = 4 rollouts
#   bash scripts/run_phase3.sh c     # Gate C：B0 原子基线 2 任务 × 5 seeds = 10 rollouts
#   bash scripts/run_phase3.sh d     # Gate D：新种子 A→B 2 任务 × 5 seeds = 10 rollouts（带 trace）
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PY:-$SHB_ROOT/envs/motus/bin/python}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
P3="$SHB_ROOT/results/phase3"
MAX_MINUTES="${MAX_MINUTES:-45}"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export CUDA_VISIBLE_DEVICES="${SHB_GPU:-0}"
export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export MOTUS_SAVE_IMAGES=0
VK_LIB_DIR="${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}"
XLIB_DIR="${XLIB_DIR:-$SHB_ROOT/envs/xlib/usr/lib64}"
CUDA_HOME_LOCAL="${CUDA_HOME_LOCAL:-$SHB_ROOT/envs/cuda_home}"
CONDA_CC_LIB="${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}"
export LD_LIBRARY_PATH="$XLIB_DIR:$VK_LIB_DIR:$CONDA_CC_LIB:$CUDA_HOME_LOCAL/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

# run_one <tag> <task> <episodes> <seeds-file|-> <hse_variant> <custom_instruction|-> <trace_jsonl|->
run_one() {
  local tag="$1" task="$2" eps="$3" seeds="$4" variant="$5" instr="$6" trace="$7"
  local dir="$P3/$tag/$task"
  mkdir -p "$dir"
  local extra=()
  [ "$seeds" != "-" ] && extra+=(--priority_seeds_file "$seeds")
  [ "$instr" != "-" ] && extra+=(--custom_instruction "$instr")
  say "=== $tag/$task episodes=$eps variant=$variant seeds=${seeds} instr=${instr} ==="
  ( cd "$RC" && \
    env ${trace:+SHB_TRACE_JSONL=$trace} timeout --signal=TERM "$((MAX_MINUTES*60))" \
    "$PY" script/eval_policy.py \
      --config "$RC/policy/Motus/deploy_policy.yml" \
      --overrides \
      --task_name "$task" --task_config robocombine_eval --policy_name Motus \
      --seed 42 --episode_num "$eps" \
      --ckpt_setting "$CKPT" --ckpt_setting_label motus_robotwin2_official \
      --save_dir "$dir" --log_dir "$dir" \
      --hse_variant "$variant" --clear_cache false --max_steps_per_episode 1500 \
      --wan_path "$WAN" --vlm_path "$VLM" \
      "${extra[@]}" ) > "$P3/$tag/$task.run.log" 2>&1
  local code=$?
  say "=== $tag/$task exit=$code ==="
  echo "{\"tag\":\"$tag\",\"task\":\"$task\",\"episodes\":$eps,\"seeds_file\":\"$seeds\",\"variant\":\"$variant\",\"trace\":\"$trace\",\"exit\":$code}" >> "$P3/runs.jsonl"
}

seedfile() {  # <name> <seed...>
  local name="$1"; shift
  local f="$P3/seeds/$name.txt"
  mkdir -p "$P3/seeds"
  printf '%s\n' "$@" > "$f"
  echo "$f"
}

main() {
  local mode="${1:-}"
  mkdir -p "$P3"
  case "$mode" in
    b)
      # 已知失败案例复查：同一 seed 重复 2 次（priority 文件里重复写两次）
      local f1 f2
      f1=$(seedfile desk_arrange_4300003 4300003 4300003)
      f2=$(seedfile office_organize_4300000 4300000 4300000)
      run_one gateB desk_arrange_2tasks 2 "$f1" oracle_hse - -
      run_one gateB office_organize_2tasks 2 "$f2" oracle_hse - -
      ;;
    c)
      # B0 原子基线：官方 RoboTwin 原子任务 env + 5 个独立原子初始状态
      local s
      s=$(seedfile b0_5300000_5300004 5300000 5300001 5300002 5300003 5300004)
      run_one gateC place_phone_stand 5 "$s" full_inst "Place phone on stand" -
      run_one gateC stamp_seal 5 "$s" full_inst "Stamp seal" -
      ;;
    d)
      # 新种子 A→B：oracle_hse + 被动 trace（Gate D 要求记录"首次有效接触"，所以打开接触统计）
      export SHB_TRACE_CONTACTS="${SHB_TRACE_CONTACTS:-1}"
      local s
      s=$(seedfile ab_4400000_4400004 4400000 4400001 4400002 4400003 4400004)
      mkdir -p "$P3/trace"
      run_one gateD desk_arrange_2tasks 5 "$s" oracle_hse - "$P3/trace/desk_arrange.jsonl"
      run_one gateD office_organize_2tasks 5 "$s" oracle_hse - "$P3/trace/office_organize.jsonl"
      ;;
    *) echo "usage: $0 {b|c|d}"; exit 2 ;;
  esac
}

main "$@"
