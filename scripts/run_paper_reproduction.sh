#!/usr/bin/env bash
# SkillHandoffBench Phase 4 · RoboCombine Table 1 复现运行器
#
# 用法：
#   bash scripts/run_paper_reproduction.sh preflight [oracle_hse|full_inst]
#        Gate D：2 个任务 × 3 episodes（论文协议的缩小版，用于验证链路）
#   bash scripts/run_paper_reproduction.sh full <track> [batch] [ntasks]
#        Gate E：19 任务 × 20 episodes（可分批；batch 用于独立输出目录）
#   bash scripts/run_paper_reproduction.sh list
#        列出 spec 里的 19 个任务
#
# 关键协议（与 Gate A 审计一致，见 docs/13）：
#   --episodes 20           论文 19×20=380（spec 默认只有 5，必须显式覆盖）
#   --max-steps-per-episode 1500   spec 默认
#   --clear-cache false     论文 chunk-preserving HSE / README 要求；runner 默认是 true，绝不沿用默认
#   --base-seed 42          仅在没有 priority seed receipt 时生效；真实 seed 由 receipt 记录
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PYTHON_BIN:-$SHB_ROOT/envs/motus/bin/python}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
OUT_ROOT="${ORACLE_OUTPUT:-$SHB_ROOT/results/paper_table1}"
LOG_DIR="$SHB_ROOT/logs/paper_table1"
mkdir -p "$OUT_ROOT" "$LOG_DIR"

export CUDA_VISIBLE_DEVICES="${SHB_GPU:-0}"
export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export MOTUS_SAVE_IMAGES="${MOTUS_SAVE_IMAGES:-0}"
export LD_LIBRARY_PATH="$SHB_ROOT/envs/xlib/usr/lib64:${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}:${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}:$SHB_ROOT/envs/cuda_home/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

run_split() {  # <label> <track> <episodes> <output-subdir> [extra args...]
  local label="$1" track="$2" eps="$3" sub="$4"; shift 4
  local out="$OUT_ROOT/$sub"
  mkdir -p "$out"
  say "START $label track=$track episodes=$eps -> $out"
  ( cd "$RC" && timeout --signal=TERM "${MAX_MINUTES:-720}"m \
      "$PY" handoff_eval/runner/run_split.py \
        --spec robocombine \
        --track "$track" \
        --policy Motus \
        --checkpoint "$CKPT" \
        --checkpoint-label motus_robotwin2_official \
        --motus-wan-dir "$WAN" \
        --motus-vlm-dir "$VLM" \
        --task-config robocombine_eval \
        --episodes "$eps" \
        --max-steps-per-episode 1500 \
        --clear-cache false \
        --base-seed 42 \
        --output-root "$out" "$@" ) > "$LOG_DIR/$label.log" 2>&1
  local code=$?
  say "END   $label exit=$code"
  printf '{"label":"%s","track":"%s","episodes":%s,"output":"%s","exit":%s,"ts":"%s"}\n' \
    "$label" "$track" "$eps" "$out" "$code" "$(date -Is)" >> "$OUT_ROOT/runs.jsonl"
  return $code
}

PREFLIGHT_TASKS=(--task-filter living_room_tidy_2tasks --task-filter office_desk_2tasks)

main() {
  local mode="${1:-}"
  case "$mode" in
    list)
      ( cd "$RC" && "$PY" handoff_eval/runner/run_split.py --spec robocombine --list-tasks )
      ;;
    preflight)
      local track="${2:-oracle_hse}"
      run_split "gateD_${track}" "$track" 3 "gateD/$track" "${PREFLIGHT_TASKS[@]}"
      ;;
    deep)
      # 与论文 N=20 对齐，但只跑两个预检任务（资源受限时的分批策略；任务固定、不按成绩挑选）
      local track="${2:-oracle_hse}"
      run_split "gateE_deep_${track}" "$track" 20 "gateE_deep/$track" "${PREFLIGHT_TASKS[@]}"
      ;;
    full)
      local track="${2:?need track}" batch="${3:-b1}" ntasks="${4:-0}"
      local extra=("${PREFLIGHT_TASKS[@]}")   # 占位；full 模式不用 task-filter
      extra=()
      if [ "$ntasks" -gt 0 ]; then
        local i=0
        while IFS= read -r t; do
          [ -z "$t" ] && continue
          extra+=(--task-filter "$t")
          i=$((i+1))
          [ "$i" -ge "$ntasks" ] && break
        done < <( cd "$RC" && "$PY" handoff_eval/runner/run_split.py --spec robocombine --list-tasks )
      fi
      run_split "gateE_${track}_${batch}" "$track" 20 "gateE/$track/$batch" "${extra[@]}"
      ;;
    *) echo "usage: $0 {list|preflight <track>|full <track> [batch] [ntasks]}"; exit 2 ;;
  esac
}

main "$@"
