#!/usr/bin/env bash
# 卡死检测器：轮询所有 eval_policy 进程，若其 task.log 超过 STALE_MIN 分钟没有更新，
# 判定为规划器死循环（Phase 3/4 在 office_organize 上见过多次），kill 掉该进程。
# supervisor 会看到 completed<20 并按自己的 RETRY 逻辑处理（换新 attempt 目录）。
#
# 用法：setsid nohup bash scripts/watchdog_stale.sh > logs/paper_table1/full/watchdog.out 2>&1 &
set -uo pipefail
STALE_MIN="${STALE_MIN:-25}"
INTERVAL="${INTERVAL:-300}"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

say "watchdog 启动：stale=${STALE_MIN}min interval=${INTERVAL}s"
while true; do
  sleep "$INTERVAL"
  now=$(date +%s)
  # 逐个 eval_policy 进程检查
  for pid in $(pgrep -f "script/eval_policy.py" 2>/dev/null); do
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)
    task=$(printf '%s' "$cmd" | sed -n 's/.*--task_name \([^ ]*\).*/\1/p')
    save=$(printf '%s' "$cmd" | sed -n 's/.*--save_dir \([^ ]*\).*/\1/p')
    [ -z "$task" ] && continue
    log=""
    if [ -n "$save" ] && [ -f "$save/tasks/$task/task.log" ]; then
      log="$save/tasks/$task/task.log"
    fi
    [ -z "$log" ] && continue
    mtime=$(date -r "$log" +%s 2>/dev/null || echo "$now")
    age=$(( (now - mtime) / 60 ))
    if [ "$age" -ge "$STALE_MIN" ]; then
      say "STALE ${age}min -> kill pid=$pid task=$task log=$log"
      kill -9 "$pid" 2>/dev/null
      # 一并杀掉它的 timeout/run_split 父进程，让 supervisor 尽快走到 RETRY
      ppid=$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null)
      pppid=$(awk '{print $4}' "/proc/$ppid/stat" 2>/dev/null)
      for p in "$ppid" "$pppid"; do
        [ -n "${p:-}" ] && grep -q "run_split\|timeout" "/proc/$p/cmdline" 2>/dev/null && kill -9 "$p" 2>/dev/null
      done
    fi
  done
done
