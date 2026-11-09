#!/usr/bin/env python3
"""SkillHandoffBench Phase 4 · Table 1 复现完整性检查 + 对照。

对 `results/paper_table1/**/tasks/<task>/evaluation_statistics.json` 逐任务输出：
  episodes / env_success / sr_ordered / stage1 / 实际 seeds / 退出码 / 完整性判定
并与论文 Table 1（Motus 三列）对照，计算差值。

用法：
  python3 scripts/check_paper_reproduction.py --root results/paper_table1 \
      --track oracle_hse [--expected-episodes 20] [--json out.json]

只读；不修改任何运行产物。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# 论文 Table 1（Motus），单位 %，每格 20 rollouts
PAPER = {
    "arrange_sign_2tasks":      {"oracle_hse": 10.0, "ordered_hse": 5.0,  "full_inst": 0.0},
    "bedside_2tasks":           {"oracle_hse": 30.0, "ordered_hse": 25.0, "full_inst": 30.0},
    "breakfast_prep_2tasks":    {"oracle_hse": 75.0, "ordered_hse": 80.0, "full_inst": 20.0},
    "checkout_counter_2tasks":  {"oracle_hse": 30.0, "ordered_hse": 15.0, "full_inst": 15.0},
    "counter_cleanup_2tasks":   {"oracle_hse": 15.0, "ordered_hse": 10.0, "full_inst": 15.0},
    "desk_arrange_2tasks":      {"oracle_hse": 10.0, "ordered_hse": 10.0, "full_inst": 5.0},
    "hobby_desk_2tasks":        {"oracle_hse": 35.0, "ordered_hse": 10.0, "full_inst": 15.0},
    "living_room_tidy_2tasks":  {"oracle_hse": 10.0, "ordered_hse": 30.0, "full_inst": 5.0},
    "office_desk_2tasks":       {"oracle_hse": 15.0, "ordered_hse": 35.0, "full_inst": 10.0},
    "office_organize_2tasks":   {"oracle_hse": 15.0, "ordered_hse": 25.0, "full_inst": 15.0},
    "reception_desk_2tasks":    {"oracle_hse": 15.0, "ordered_hse": 20.0, "full_inst": 5.0},
    "stationery_sort_2tasks":   {"oracle_hse": 10.0, "ordered_hse": 5.0,  "full_inst": 10.0},
    "store_display_2tasks":     {"oracle_hse": 20.0, "ordered_hse": 20.0, "full_inst": 5.0},
    "tabletop_arrange_2tasks":  {"oracle_hse": 0.0,  "ordered_hse": 0.0,  "full_inst": 20.0},
    "workspace_setup_2tasks":   {"oracle_hse": 50.0, "ordered_hse": 25.0, "full_inst": 15.0},
    "bakery_close_2tasks":      {"oracle_hse": 35.0, "ordered_hse": 10.0, "full_inst": 5.0},
    "kitchen_switch_2tasks":    {"oracle_hse": 0.0,  "ordered_hse": 0.0,  "full_inst": 0.0},
    "room_comfort_2tasks":      {"oracle_hse": 0.0,  "ordered_hse": 0.0,  "full_inst": 0.0},
    "smart_home_2tasks":        {"oracle_hse": 0.0,  "ordered_hse": 5.0,  "full_inst": 0.0},
}
PAPER_OVERALL = {"oracle_hse": 19.7, "ordered_hse": 17.4, "full_inst": 10.0}

EXIT_PAT = re.compile(r"END task=(\S+)\s+code=(-?\d+)")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - m) / d, (c + m) / d)


def exit_codes(logs):
    m = {}
    for p in logs:
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                for task, code in EXIT_PAT.findall(line):
                    m.setdefault(task, []).append(int(code))
        except OSError:
            pass
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--track", required=True, choices=["oracle_hse", "ordered_hse", "full_inst"])
    ap.add_argument("--expected-episodes", type=int, default=20)
    ap.add_argument("--log-glob", action="append", default=[])
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    logs = []
    for g in args.log_glob:
        logs.extend(glob.glob(g, recursive=True))
    codes = exit_codes(logs)

    rows = []
    pattern = os.path.join(args.root, "**", f"*{args.track}*", "**", "tasks", "*", "evaluation_statistics.json")
    for stats in sorted(glob.glob(pattern, recursive=True)):
        task_dir = os.path.dirname(stats)
        task = os.path.basename(task_dir)
        problems = []
        try:
            d = json.load(open(stats, encoding="utf-8"))
        except Exception as exc:
            rows.append({"task": task, "problems": [f"unreadable:{type(exc).__name__}"]})
            continue
        meta = d.get("metadata", {})
        eps = d.get("episode_details") or []
        n = meta.get("total_episodes")
        succ = meta.get("total_successes")
        if n != len(eps):
            problems.append(f"ep_count_mismatch:{n}!={len(eps)}")
        if args.expected_episodes and n != args.expected_episodes:
            problems.append(f"episodes_not_{args.expected_episodes}:{n}")
        seeds = [e.get("seed") for e in eps]
        if len(set(seeds)) != len(seeds):
            problems.append("dup_seeds")
        # sr_ordered：按序完成（s1_step <= s2_step 且都非空）
        ordered = sum(1 for e in eps
                      if e.get("s1_completed") and e.get("s2_completed")
                      and e.get("s1_step") is not None and e.get("s2_step") is not None
                      and e["s1_step"] <= e["s2_step"])
        s1 = sum(1 for e in eps if e.get("s1_completed"))
        lo, hi = wilson(ordered, len(eps)) if eps else (0.0, 0.0)
        paper = PAPER.get(task, {}).get(args.track)
        ours = (100.0 * ordered / len(eps)) if eps else None
        rows.append({
            "task": task,
            "episodes": n,
            "env_success": f"{succ}/{n}",
            "sr_ordered": f"{ordered}/{len(eps)}",
            "sr_ordered_pct": round(ours, 2) if ours is not None else None,
            "ci95": [round(100 * lo, 1), round(100 * hi, 1)] if eps else None,
            "stage1": f"{s1}/{len(eps)}",
            "seeds": seeds,
            "exit_codes": codes.get(task),
            "paper_pct": paper,
            "diff_pct": round(ours - paper, 2) if (ours is not None and paper is not None) else None,
            "problems": problems,
        })

    tot_ord = sum(int(r["sr_ordered"].split("/")[0]) for r in rows if "sr_ordered" in r)
    tot_ep = sum(r["episodes"] for r in rows if r.get("episodes"))
    print(f"track={args.track}  tasks={len(rows)}  episodes={tot_ep}  "
          f"ordered={tot_ord}  ours={100*tot_ord/tot_ep:.2f}%  paper={PAPER_OVERALL[args.track]}%"
          if tot_ep else f"track={args.track}: no completed tasks yet")
    print(f"{'task':30s} {'eps':>4s} {'env':>7s} {'ord':>7s} {'ours%':>6s} {'paper%':>7s} {'diff':>7s}  problems")
    for r in rows:
        if "episodes" not in r:
            print(f"{r['task'][:30]:30s}  {'-':>4s}  {', '.join(r['problems'])}")
            continue
        print(f"{r['task'][:30]:30s} {r['episodes']:>4d} {r['env_success']:>7s} {r['sr_ordered']:>7s} "
              f"{r['sr_ordered_pct']:>6.2f} {str(r['paper_pct']):>7s} {str(r['diff_pct']):>7s}  "
              f"{','.join(r['problems']) or '-'}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        json.dump({"track": args.track, "rows": rows,
                   "totals": {"episodes": tot_ep, "ordered": tot_ord,
                              "ours_pct": round(100 * tot_ord / tot_ep, 2) if tot_ep else None,
                              "paper_pct": PAPER_OVERALL[args.track]}},
                  open(args.json, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"-> {args.json}")
    return 0 if all(not r.get("problems") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
