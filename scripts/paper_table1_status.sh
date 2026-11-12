#!/usr/bin/env bash
# 随时查看 RoboCombine Table 1 全量进度（只读，可在任何 ssh 里跑）。
#   bash scripts/paper_table1_status.sh
#   bash scripts/paper_table1_status.sh --json     # 机器可读
set -uo pipefail
SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
PY="${MOTUS_PYTHON_BIN:-$SHB_ROOT/envs/motus/bin/python}"
STATE="$SHB_ROOT/results/paper_table1/full"
JSON=0
[ "${1:-}" = "--json" ] && JSON=1

"$PY" - "$STATE" "$SHB_ROOT" "$JSON" <<'PY'
import glob, json, os, subprocess, sys, datetime

state, root, as_json = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
spec = json.load(open(os.path.join(root, "third_party/RoboCombine/handoff_eval/specs/robocombine.json"), encoding="utf-8"))
tasks = [t["task_name"] for t in spec["tasks"]]

# 已经完成的历史深跑（gateE_deep）也算进总账
def eps_and_metrics(d, task=None):
    eps = ordered = env = 0
    pat = (os.path.join(d, "**", "tasks", task, "evaluation_statistics.json") if task
           else os.path.join(d, "**", "tasks", "*", "evaluation_statistics.json"))
    for p in glob.glob(pat, recursive=True):
        try:
            x = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        e = x.get("episode_details") or []
        eps = max(eps, int(x["metadata"].get("total_episodes", 0)))
        seq = ((x.get("subtask_completion") or {}).get("sequential") or {}).get("subtask_1_to_2") or {}
        if "count" in seq:
            ordered = max(ordered, int(seq["count"]))
            env += sum(1 for r in e if r.get("success"))
            continue
        for r in e:
            if r.get("success"):
                env += 1
            if (r.get("s1_completed") and r.get("s2_completed")
                    and r.get("s1_step") is not None and r.get("s2_step") is not None
                    and r["s1_step"] <= r["s2_step"]):
                ordered += 1
    return eps, ordered, env

rows = []
for track in ("oracle_hse", "full_inst"):
    # 1) 历史 deep run（2 个任务）
    for p in sorted(glob.glob(os.path.join(root, "results/paper_table1/gateE_deep", track, "**", "tasks", "*"), recursive=True)):
        t = os.path.basename(p)
        if t not in tasks:
            continue
        run_dir = p.split("/tasks/")[0]   # p 是 <run>/tasks/<task>，需要的是 <run>
        eps, o, e = eps_and_metrics(run_dir, t)
        rows.append({"track": track, "task": t, "completed": eps, "ordered": o, "env": e, "src": "gateE_deep"})
    # 2) 全量 runner 的产物
    for t in tasks:
        best = None
        cands = sorted(glob.glob(os.path.join(state, track, t, "attempt*")))
        cands += sorted(glob.glob(os.path.join(state, "shard*of5", track, t, "attempt*")))
        for d in cands:
            eps, o, e = eps_and_metrics(d, t)
            if eps and (best is None or eps > best["completed"]):
                best = {"track": track, "task": t, "completed": eps, "ordered": o, "env": e,
                        "src": os.path.basename(d)}
        if best:
            rows.append(best)

# 归并（同一 track/task 取 completed 最大）
merged = {}
for r in rows:
    k = (r["track"], r["task"])
    if k not in merged or r["completed"] > merged[k]["completed"]:
        merged[k] = r

def has_running():
    try:
        out = subprocess.run(["pgrep", "-fc", "eval_policy.py"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() not in ("", "0")
    except Exception:
        return False

running = has_running()
if as_json:
    print(json.dumps({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                      "running": running, "rows": list(merged.values())}, indent=2, ensure_ascii=False))
    raise SystemExit(0)

print(f"RoboCombine Table 1 全量进度   {datetime.datetime.now():%Y-%m-%d %H:%M}   "
      f"{'GPU 作业运行中' if running else '当前无 GPU 作业'}")
print(f"{'track':10s} {'task':30s} {'done':>6s} {'ordered':>8s} {'env':>5s}  {'状态':<10s} 来源")
tot_done = tot = 0
for track in ("oracle_hse", "full_inst"):
    for t in tasks:
        r = merged.get((track, t))
        done = r["completed"] if r else 0
        tot_done += done
        tot += 20
        st = "COMPLETE" if done >= 20 else ("PARTIAL" if done else "NOT_RUN")
        extra = f"{r['ordered']:>8d} {r['env']:>5d}" if r else f"{'-':>8s} {'-':>5s}"
        print(f"{track:10s} {t:30s} {done:>4d}/20 {extra}  {st:<10s} {r['src'] if r else '-'}")
print(f"\n总计 completed episodes: {tot_done} / {tot}  (需要 {tot}；缺 {tot-tot_done})")
PY
