#!/usr/bin/env python3
"""SkillHandoffBench Phase 3A · Gate A：评测结果完整性检查（只读）。

对每个 `<run-root>/**/tasks/<task>/` 目录输出一行判定，字段严格分开：

  process_exit_code       子进程退出码（来自 runner 日志的 `END task=... code=-11`；未知则 None）
  evaluation_complete     统计文件可解析、字段齐全、episode 数与种子数一致、终局事件存在
  environment_success     环境判据（所有子任务完成 + 夹爪张开）为真
  ordered_success         官方 `sr_ordered` 语义：子任务**按顺序**完成（s1_step <= s2_step）
  post_eval_crash_suspected  退出码为负（信号）但 stats/_result.txt 已写 → 疑似"评测后崩溃"

**不会**把 SIGSEGV 隐藏或改写成 0；也不会因为文件存在就认定数据有效。

用法：
  python3 scripts/check_phase2_integrity.py --run-root <dir> [--run-root ...] \
      [--exit-log <log with 'END task=... code=N'>] [--out report.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

REQUIRED_TOP = {"metadata", "subtask_completion", "failure_analysis", "episode_details"}
REQUIRED_META = {"task_name", "total_episodes", "total_successes", "overall_success_rate", "num_subtasks"}

EXIT_PAT = re.compile(r"END task=(\S+)\s+code=(-?\d+)")


def load_exit_codes(paths):
    m = {}
    for p in paths:
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                for task, code in EXIT_PAT.findall(line):
                    m.setdefault(task, []).append(int(code))
        except FileNotFoundError:
            pass
    return m


def check_task_dir(task_dir, exit_codes):
    task = os.path.basename(task_dir.rstrip(os.sep))
    stats_path = os.path.join(task_dir, "evaluation_statistics.json")
    log_path = os.path.join(task_dir, "task.log")
    result_path = os.path.join(task_dir, "_result.txt")
    cmd_path = os.path.join(task_dir, "command.sh")

    out = {
        "task_dir": task_dir,
        "task": task,
        "process_exit_code": (exit_codes.get(task)[0] if exit_codes.get(task) else None),
        "evaluation_complete": False,
        "environment_success": None,
        "ordered_success": None,
        "post_eval_crash_suspected": None,
        "problems": [],
    }

    # --- 1) stats 可解析 + 字段齐全 ---
    try:
        d = json.load(open(stats_path, encoding="utf-8"))
    except Exception as exc:
        out["problems"].append(f"stats_unreadable:{type(exc).__name__}")
        return out
    missing_top = REQUIRED_TOP - set(d)
    meta = d.get("metadata", {})
    missing_meta = REQUIRED_META - set(meta)
    if missing_top:
        out["problems"].append(f"missing_top:{sorted(missing_top)}")
    if missing_meta:
        out["problems"].append(f"missing_meta:{sorted(missing_meta)}")

    eps = d.get("episode_details") or []
    n_meta = meta.get("total_episodes")
    # --- 2) episode 数 vs seed 数 ---
    if n_meta != len(eps):
        out["problems"].append(f"episode_count_mismatch:meta={n_meta},details={len(eps)}")
    seeds = [e.get("seed") for e in eps]
    if len(set(seeds)) != len(seeds):
        out["problems"].append(f"duplicate_seeds:{seeds}")
    if any(s is None for s in seeds):
        out["problems"].append("missing_seed")

    # --- 3) 终局事件存在（每 episode 都有 total_steps，且 task.log 的步数与之匹配）---
    total_steps = [e.get("total_steps") for e in eps]
    if any(t is None for t in total_steps):
        out["problems"].append("missing_total_steps")
    last_logged_step = None
    if os.path.exists(log_path):
        maxstep = -1
        for line in open(log_path, encoding="utf-8", errors="replace"):
            for m in re.finditer(r"^\[Step\s+(\d+)\]", line.replace("\r", "\n"), re.M):
                maxstep = max(maxstep, int(m.group(1)))
        last_logged_step = maxstep if maxstep >= 0 else None
    else:
        out["problems"].append("task_log_missing")
    out["last_logged_step"] = last_logged_step
    if last_logged_step is not None and total_steps and all(t is not None for t in total_steps):
        # 日志是**多 episode 顺序追加**的，最后一段应对应最后一个 episode 的步数
        if last_logged_step > max(total_steps) + 1:
            out["problems"].append(f"log_step_exceeds_stats:log={last_logged_step},max={max(total_steps)}")

    # --- 4) _result.txt（main() 末尾才写）---
    out["result_txt"] = os.path.exists(result_path)
    if not out["result_txt"]:
        out["problems"].append("result_txt_missing")

    # --- 5) 运行配置归属（checkpoint / task / track）---
    if os.path.exists(cmd_path):
        cmd = open(cmd_path, encoding="utf-8").read()
        out["command_has_checkpoint"] = "Motus_robotwin2" in cmd
        out["command_task_matches"] = f"--task_name {task}" in cmd
        out["track"] = ("oracle_hse" if "--hse_variant oracle_hse" in cmd else
                        "full_inst" if "--hse_variant full_inst" in cmd else
                        "ordered_hse" if "--hse_variant ordered_hse" in cmd else "unknown")
        for k in ("command_has_checkpoint", "command_task_matches"):
            if not out[k]:
                out["problems"].append(f"{k}_false")
    else:
        out["problems"].append("command_sh_missing")

    # --- 6) 判据语义：environment_success / ordered_success ---
    env_ok, ord_ok = [], []
    for e in eps:
        s1, s2 = e.get("s1_completed"), e.get("s2_completed")
        g = (e.get("gripper_status") or {}).get("gripper_open")
        env_ok.append(bool(e.get("success")))
        # 官方 sr_ordered：按顺序完成（步数非空且 s1_step <= s2_step）
        st1, st2 = e.get("s1_step"), e.get("s2_step")
        ord_ok.append(bool(s1 and s2 and st1 is not None and st2 is not None and st1 <= st2))
    out["environment_success"] = f"{sum(env_ok)}/{len(env_ok)}" if eps else None
    out["ordered_success"] = f"{sum(ord_ok)}/{len(ord_ok)}" if eps else None

    out["evaluation_complete"] = not out["problems"]

    # --- 7) 评测后崩溃判定 ---
    code = out["process_exit_code"]
    out["post_eval_crash_suspected"] = bool(code is not None and code < 0 and out["result_txt"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", action="append", required=True)
    ap.add_argument("--exit-log", action="append", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    exit_codes = load_exit_codes(args.exit_log)
    rows = []
    for root in args.run_root:
        for stats in sorted(glob.glob(os.path.join(root, "**", "tasks", "*", "evaluation_statistics.json"), recursive=True)):
            rows.append(check_task_dir(os.path.dirname(stats), exit_codes))

    print(f"{'task':32s} {'exit':>5s} {'complete':>8s} {'env_succ':>8s} {'ordered':>8s} {'crash?':>6s}  problems")
    for r in rows:
        print(f"{r['task'][:32]:32s} {str(r['process_exit_code']):>5s} {str(r['evaluation_complete']):>8s} "
              f"{str(r['environment_success']):>8s} {str(r['ordered_success']):>8s} "
              f"{str(r['post_eval_crash_suspected']):>6s}  {','.join(r['problems']) or '-'}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump({"rows": rows}, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"-> {args.out}")
    bad = [r for r in rows if not r["evaluation_complete"]]
    print(f"\n{len(rows)} task dirs, {len(bad)} with problems")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
