#!/usr/bin/env bash
# RoboCombine Table 1 全量评测的**可断线后台运行器**（19 任务 × 2 轨道 × 20 eps）。
#
# 设计目标（对应 docs/21 §2 的操作规范）：
#   1. 完全脱离 SSH：用 setsid + nohup 启动，关掉本地电脑/VPN 都不影响。
#   2. 一次只跑 1 个 task × 1 个 track × 20 eps，避免 55 min 外层超时截断。
#   3. 断点续跑安全：已满 20 个 completed episode 的 (track, task) 直接跳过。
#   4. 绝不向已有 save_dir 追加（每个 attempt 一个全新 output-root）。
#   5. 失败/截断（exit=124 或 completed<20）自动换目录重试，最多 2 次；仍失败就记录并继续。
#   6. 所有退出码、命令、日志落盘；任何时刻可用 paper_table1_status.sh 查看进度。
#
# 用法：
#   bash scripts/run_all_paper_table1.sh --dry-run        # 只打印还剩什么，不跑
#   bash scripts/run_all_paper_table1.sh --tracks oracle_hse
#   setsid nohup bash scripts/run_all_paper_table1.sh > logs/paper_table1/full/supervisor.out 2>&1 &
#
# 说明：`--episodes 20` / `--clear-cache false` / `--base-seed 42` 与已完成的 4 组逐字一致。
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="${MOTUS_PYTHON_BIN:-$SHB_ROOT/envs/motus/bin/python}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
STATE="$SHB_ROOT/results/paper_table1/full"
LOGD="$SHB_ROOT/logs/paper_table1/full"
EPISODES="${EPISODES:-20}"
MAX_STEPS="${MAX_STEPS:-1500}"
# 单个 (task,track,20eps) 的墙钟上限；实测最长约 7h，给到 6h 会误杀，因此 8h。
RUN_TIMEOUT_SEC="${RUN_TIMEOUT_SEC:-28800}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-2}"

DRY=0
TRACKS=()
TASK_FILTER=()
SHARD_SPEC="${SHARD_SPEC:-1/1}"   # <k>/<N>：把所有 (track,task) 组合按序切成 N 份，取第 k 份
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --tracks) shift; IFS=',' read -r -a TRACKS <<< "${1:-}" ;;
    --tasks) shift; IFS=',' read -r -a TASK_FILTER <<< "${1:-}" ;;
    --gpu) shift; SHB_GPU="${1:-0}" ;;
    --shard) shift; SHARD_SPEC="${1:-1/1}" ;;
    --episodes) shift; EPISODES="$1" ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done
[ ${#TRACKS[@]} -eq 0 ] && TRACKS=(oracle_hse full_inst)

# shard 必须在解析参数之后再算（否则 --shard 传进来的值会被默认值覆盖）
SHARD_ID="${SHARD_SPEC%/*}"; SHARD_N="${SHARD_SPEC#*/}"
if [ "$SHARD_N" != "1" ]; then
  STATE="$STATE/shard${SHARD_ID}of${SHARD_N}"
fi
export SHARD_ID SHARD_N

mkdir -p "$STATE" "$LOGD"

# 单实例锁：防止两个 supervisor 同时抢同一张卡（flock 在 /usr/bin/flock 可用）
exec 9>"$STATE/supervisor.lock"
if ! flock -n 9; then
  echo "已有 supervisor 在运行（lock: $STATE/supervisor.lock），本进程退出。"
  exit 3
fi

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

export CUDA_VISIBLE_DEVICES="${SHB_GPU:-0}"
export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}${PYTHONPATH:+:$PYTHONPATH}"
export MOTUS_SAVE_IMAGES=0
export LD_LIBRARY_PATH="$SHB_ROOT/envs/xlib/usr/lib64:${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}:${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}:$SHB_ROOT/envs/cuda_home/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

list_tasks() {
  "$PY" - <<'PY'
import json, os
spec = os.environ["RC"] + "/handoff_eval/specs/robocombine.json"
for t in json.load(open(spec, encoding="utf-8"))["tasks"]:
    print(t["task_name"])
PY
}

# 已完成 episode 数（从 episode_details 数，不信 metadata）
completed_eps() {  # <dir>
  local dir="$1"
  "$PY" - "$dir" <<'PY' 2>/dev/null || echo 0
import glob, json, os, sys
d = sys.argv[1]
best = 0
for p in glob.glob(os.path.join(d, "**", "tasks", "*", "evaluation_statistics.json"), recursive=True):
    try:
        best = max(best, int(json.load(open(p, encoding="utf-8"))["metadata"]["total_episodes"]))
    except Exception:
        pass
print(best)
PY
}

# 任意 attempt 目录里已满 EPISODES 就跳过
pair_done() {  # <track> <task>
  local track="$1" task="$2" d
  # 历史深跑（gateE_deep）已完成的任务也算数，避免重复烧卡
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    [ -f "$d/evaluation_statistics.json" ] || continue
    if "$PY" -c 'import json,sys;d=json.load(open(sys.argv[1],encoding="utf-8"));raise SystemExit(0 if int(d["metadata"]["total_episodes"])>=int(sys.argv[2]) else 1)' \
         "$d/evaluation_statistics.json" "$EPISODES"; then
      return 0
    fi
  done < <(find "$SHB_ROOT/results/paper_table1/gateE_deep/$track" -type d -path "*/tasks/$task" -name "$task" 2>/dev/null)
  # 也检查非 shard 的根目录（否则分片后会重跑已完成的任务，如 breakfast_prep）
  for d in "$SHB_ROOT/results/paper_table1/full/$track/$task"/attempt* "$STATE/$track/$task"/attempt*; do
    [ -d "$d" ] || continue
    [ "$(completed_eps "$d")" -ge "$EPISODES" ] && return 0
  done
  return 1
}

run_one() {  # <track> <task> <attempt>
  local track="$1" task="$2" attempt="$3"
  local dir="$STATE/$track/$task/attempt$attempt"
  local log="$LOGD/${track}__${task}__a${attempt}.log"
  mkdir -p "$dir"
  say "START $track/$task attempt=$attempt -> $dir"
  ( exec 9>&-   # 子进程不继承锁 fd
    cd "$RC" && timeout --signal=TERM "$RUN_TIMEOUT_SEC" \
      "$PY" handoff_eval/runner/run_split.py \
        --spec robocombine --track "$track" --policy Motus \
        --checkpoint "$CKPT" --checkpoint-label motus_robotwin2_official \
        --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
        --task-config robocombine_eval \
        --episodes "$EPISODES" --max-steps-per-episode "$MAX_STEPS" \
        --clear-cache false --base-seed 42 \
        --task-filter "$task" \
        --output-root "$dir" ) > "$log" 2>&1
  local code=$?
  local done_eps; done_eps="$(completed_eps "$dir")"
  say "END   $track/$task attempt=$attempt exit=$code completed=$done_eps/$EPISODES"
  "$PY" - "$STATE/runs.jsonl" "$track" "$task" "$attempt" "$code" "$done_eps" "$dir" <<'PY'
import json, sys, datetime
path, track, task, attempt, code, eps, d = sys.argv[1:8]
rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
       "track": track, "task": task, "attempt": int(attempt),
       "exit": int(code), "completed_episodes": int(eps),
       "output": d, "episodes_requested": int(__import__("os").environ.get("EPISODES", 20))}
open(path, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  return "$code"
}

# GPU 空闲检查：显存被占 >45GB 就等 60s（避免和别人撞车）
wait_gpu_free() {
  local used
  local dev="${CUDA_VISIBLE_DEVICES:-0}"
  used=$(nvidia-smi -i "$dev" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  while [ "${used:-0}" -gt 2000 ]; do
    say "GPU $dev 忙（${used} MiB），等 60s"
    sleep 60 9>&-   # 关键：别让子进程继承 flock fd，否则 kill 主进程后锁仍被 sleep 持有
    used=$(nvidia-smi -i "$dev" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  done
}

main() {
  export RC
  local tasks; tasks="$(list_tasks)"
  if [ ${#TASK_FILTER[@]} -gt 0 ]; then
    local keep=""
    for t in $tasks; do
      for want in "${TASK_FILTER[@]}"; do
        [ "$t" = "$want" ] && keep="$keep $t"
      done
    done
    tasks="$(echo $keep | tr ' ' '\n' | sed '/^$/d')"
    say "任务过滤：$(echo "$tasks" | tr '\n' ' ')"
  fi
  [ -z "$tasks" ] && { echo "读不到 19 任务清单"; exit 1; }
  local total=0 remain=0
  for track in "${TRACKS[@]}"; do for task in $tasks; do total=$((total+1)); done; done

  say "计划：${#TRACKS[@]} 轨道 × $(echo "$tasks" | wc -l) 任务 = $total 个 (track,task) 组合，每组合 $EPISODES eps"

  local idx=0
  for track in "${TRACKS[@]}"; do
    for task in $tasks; do
      idx=$((idx+1))
      if [ "$SHARD_N" -gt 1 ] && [ $(( (idx - 1) % SHARD_N )) -ne $(( SHARD_ID - 1 )) ]; then
        continue
      fi
      if pair_done "$track" "$task"; then
        say "SKIP  $track/$task（已满 $EPISODES eps）"
        continue
      fi
      remain=$((remain+1))
      if [ "$DRY" -eq 1 ]; then
        say "TODO  $track/$task"
        continue
      fi
      # 关键：重跑时不要复用旧 attempt 目录（避免 skip_successful 改变样本总体）
      local attempt=1 n
      if [ -d "$STATE/$track/$task" ]; then
        n=$(ls -1d "$STATE/$track/$task"/attempt* 2>/dev/null | sed 's/.*attempt//' | sort -n | tail -1)
        [ -n "${n:-}" ] && attempt=$((n + 1))
      fi
      local ok=0
      while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
        wait_gpu_free
        run_one "$track" "$task" "$attempt"
        if [ "$(completed_eps "$STATE/$track/$task/attempt$attempt")" -ge "$EPISODES" ]; then ok=1; break; fi
        say "RETRY $track/$task（attempt $attempt 未满 $EPISODES）"
        attempt=$((attempt+1))
      done
      [ "$ok" -eq 0 ] && say "GIVEUP $track/$task（已重试 $MAX_ATTEMPTS 次，保留全部原始产物）"
    done
  done

  if [ "$DRY" -eq 1 ]; then
    say "dry-run 结束：还需跑 $remain 个组合"
  else
    say "全部结束。用 scripts/paper_table1_status.sh 查看汇总。"
  fi
}

main
