#!/usr/bin/env bash
# SkillHandoffBench Phase 2: Gate B / Gate C 的统一入口。
#
# Gate B：Motus + full_inst，2 任务 × 5 episodes，**与 Phase 1 oracle_hse 完全相同的
#         任务、初始状态（同一 base-seed 42 → seed 4300000..4300004）、判据、步数上限**。
# Gate C：Motus + oracle_hse，5 个新任务 × 3 episodes（seed 4300000..4300002），共 15 次。
#
# 设计要点
#   - 不改官方判据、不改任务文件、不改 checkpoint；
#   - 每个条件在**跑之前**先落盘 seed 计划（results/phase2/seed_plan.json）；
#   - 运行前后各记一次 GPU / 磁盘 / 进程快照（results/phase2/system_snapshots.log）；
#   - 官方 run_split.py 原样调用（只通过 CLI 传参）。
#
# 用法：
#   bash scripts/run_phase2.sh b        # Gate B（10 rollouts）
#   bash scripts/run_phase2.sh c        # Gate C（15 rollouts）
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PY:-$SHB_ROOT/envs/motus/bin/python}"
ASSETS="${ROBOCOMBINE_ASSETS_DIR:-$RC/assets}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
GPU="${SHB_GPU:-0}"
MAX_MINUTES="${MAX_MINUTES:-75}"
BASE_SEED="${BASE_SEED:-42}"
CLEAR_CACHE="${CLEAR_CACHE:-false}"
P2="$SHB_ROOT/results/phase2"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export CUDA_VISIBLE_DEVICES="$GPU"
export ROBOCOMBINE_ASSETS_DIR="$ASSETS"
export PYTHONPATH="$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export MOTUS_SAVE_IMAGES="${MOTUS_SAVE_IMAGES:-0}"
VK_LIB_DIR="${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}"
XLIB_DIR="${XLIB_DIR:-$SHB_ROOT/envs/xlib/usr/lib64}"
CUDA_HOME_LOCAL="${CUDA_HOME_LOCAL:-$SHB_ROOT/envs/cuda_home}"
CONDA_CC_LIB="${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}"
EXTRA_LIBS="$XLIB_DIR:$VK_LIB_DIR:$CONDA_CC_LIB:$CUDA_HOME_LOCAL/lib64"
export LD_LIBRARY_PATH="$EXTRA_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

snapshot() {  # <label>
  local label="$1"
  mkdir -p "$P2"
  {
    echo "=== $label $(date -Is) ==="
    echo "--- nvidia-smi ---"
    nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader
    echo "--- disk ---"
    df -h /scratch | tail -1
    echo "--- processes ---"
    pgrep -af "eval_policy|run_split" | grep -v pgrep || echo "(none)"
  } >> "$P2/system_snapshots.log" 2>&1
  say "snapshot($label) -> $P2/system_snapshots.log"
}

# 跑一组：<tag> <track> <episodes> <task1> [task2 ...]
run_set() {
  local tag="$1" track="$2" eps="$3"; shift 3
  local out="$P2/$tag"
  mkdir -p "$out" "$P2"
  local args=()
  for t in "$@"; do args+=(--task-filter "$t"); done
  say "=== $tag: track=$track episodes=$eps tasks=$* ==="
  snapshot "pre-$tag"
  local t0; t0=$(date +%s)
  ( cd "$RC" && timeout --signal=TERM "$((MAX_MINUTES * 60))" "$PY" handoff_eval/runner/run_split.py \
      --spec robocombine --track "$track" --policy Motus \
      --checkpoint "$CKPT" --checkpoint-label motus_robotwin2_official \
      --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
      --episodes "$eps" "${args[@]}" \
      --base-seed "$BASE_SEED" --clear-cache "$CLEAR_CACHE" \
      --output-root "$out" ) 2>&1 | tee "$P2/$tag.log"
  local code=${PIPESTATUS[0]}
  local dt; dt=$(( $(date +%s) - t0 ))
  say "=== $tag done: exit=$code wall=${dt}s ==="
  snapshot "post-$tag"
  echo "{\"tag\":\"$tag\",\"track\":\"$track\",\"episodes\":$eps,\"tasks\":\"$*\",\"exit\":$code,\"wall_s\":$dt}" >> "$P2/runs.jsonl"
  return $code
}

write_seed_plan() {
  local tag="$1" track="$2" eps="$3"; shift 3
  "$PY" - "$tag" "$track" "$eps" "$BASE_SEED" "$*" <<'PYEOF'
import json, os, sys
from datetime import datetime
tag, track, eps, base, tasks = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split()
st = 100000 * (1 + base)
plan = {
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "tag": tag, "track": track, "episodes_per_task": eps, "base_seed": base,
    "rule": "official: st_seed = 100000*(1+base_seed); seeds consumed in ascending order, "
            "each seed first runs the official expert demo (play_once) and is skipped if the expert fails",
    "planned_seeds_per_task": [st + i for i in range(eps)],
    "tasks": tasks,
}
p = os.path.join(os.environ.get("P2", "results/phase2"), "seed_plan.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
data = []
if os.path.exists(p):
    data = json.load(open(p))
data.append(plan)
json.dump(data, open(p, "w"), indent=2, ensure_ascii=False)
print("seed plan written:", p)
PYEOF
}

main() {
  local mode="${1:-}"
  export P2
  case "$mode" in
    b)
      write_seed_plan gateB_full_inst full_inst 5 living_room_tidy_2tasks office_desk_2tasks
      run_set gateB_full_inst full_inst 5 living_room_tidy_2tasks office_desk_2tasks
      ;;
    c)
      write_seed_plan gateC_screening oracle_hse 3 \
        arrange_sign_2tasks breakfast_prep_2tasks desk_arrange_2tasks office_organize_2tasks bakery_close_2tasks
      run_set gateC_screening oracle_hse 3 \
        arrange_sign_2tasks breakfast_prep_2tasks desk_arrange_2tasks office_organize_2tasks bakery_close_2tasks
      ;;
    *) echo "usage: $0 {b|c}"; exit 2 ;;
  esac
}

main "$@"
