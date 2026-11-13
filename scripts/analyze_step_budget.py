#!/usr/bin/env python3
"""离线分析：步数预算敏感性 + 完成任务的事件语义（不需要 GPU）。

回答两个问题：
  Q1 我们的成功有多少发生在较晚的步数？→ 若论文的最大步数更小，会掉多少？
  Q2 room_comfort / kitchen_switch / smart_home / bakery_close 这些"我们远高于论文"的任务，
     到底是"真的做完并收尾"还是"子任务标志触发过、但终局条件没满足"？

数据来源（只读）：results/paper_table1/full/**/tasks/*/{evaluation_statistics.json,*_subtask_patterns.json}
输入口径：每个 (track, task) 取 episode 数最多的那次 run，不做任何挑选。

用法：
  python3 scripts/analyze_step_budget.py --root results/paper_table1 --out results/paper_table1/step_budget.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict

CUTOFFS = [150, 300, 500, 750, 1000, 1250, 1500]
INTERACTION = ["bakery_close_2tasks", "kitchen_switch_2tasks", "room_comfort_2tasks", "smart_home_2tasks"]
REVERSE = ["hobby_desk_2tasks", "tabletop_arrange_2tasks"]


def best_runs(root):
    """每个 (track, task) 取 episode 最多的那一次 run 的 (stats, patterns)。"""
    picked = {}
    for stats in glob.glob(os.path.join(root, "**", "tasks", "*", "evaluation_statistics.json"), recursive=True):
        parts = stats.split(os.sep)
        track = next((p for p in parts if p in ("oracle_hse", "full_inst")), None)
        if not track:
            continue
        task = parts[-2]
        try:
            d = json.load(open(stats, encoding="utf-8"))
            n = int(d["metadata"]["total_episodes"])
        except Exception:
            continue
        if n < 20:
            continue
        key = (track, task)
        if key in picked and picked[key][0] >= n:
            continue
        tdir = os.path.dirname(stats)
        pat = glob.glob(os.path.join(tdir, "*_subtask_patterns.json"))
        pats = json.load(open(pat[0], encoding="utf-8")) if pat else {}
        picked[key] = (n, d, pats)
    return picked


def ordered_at(ep, cutoff):
    s1, s2 = ep.get("s1_step"), ep.get("s2_step")
    return (s1 is not None and s2 is not None and s1 <= s2 <= cutoff)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/paper_table1")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    picked = best_runs(args.root)
    tasks = sorted({t for (_, t) in picked})
    tracks = ["oracle_hse", "full_inst"]

    print("## Q1 步数预算敏感性（ordered@T，T = 允许的最大步数）\n")
    header = "| Task | Track | N | " + " | ".join(f"@{c}" for c in CUTOFFS) + " |"
    print(header)
    print("| --- | --- | ---: | " + " | ".join("---:" for _ in CUTOFFS) + " |")

    agg = defaultdict(lambda: defaultdict(int))
    for (track, task), (n, d, _p) in sorted(picked.items()):
        eps = d["episode_details"]
        cells = []
        for c in CUTOFFS:
            k = sum(1 for e in eps if ordered_at(e, c))
            cells.append(f"{k}")
        print(f"| {task.replace('_2tasks','')} | {track.split('_')[0]} | {len(eps)} | " + " | ".join(cells) + " |")
        for c, cell in zip(CUTOFFS, cells):
            agg[track][c] += int(cell)
            if task in INTERACTION:
                agg[track + "_inter"][c] += int(cell)
            else:
                agg[track + "_other"][c] += int(cell)

    print()
    for grp, label in (("oracle_hse", "Oracle 全部"), ("full_inst", "Full 全部"),
                       ("oracle_hse_inter", "Oracle 四个 interaction"), ("full_inst_inter", "Full 四个 interaction"),
                       ("oracle_hse_other", "Oracle 其余任务"), ("full_inst_other", "Full 其余任务")):
        row = agg[grp]
        if not row:
            continue
        print(f"{label}: " + "  ".join(f"@{c}={row[c]}" for c in CUTOFFS))

    print("\n## Q2 四个 interaction 任务的事件语义（每 track 汇总）\n")
    print("| Task | Track | ordered | env成功 | **两标志按序但终局夹爪闭** | S2 未触发 | S1 未触发 |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    detail = {}
    for task in INTERACTION + REVERSE:
        for track in tracks:
            if (track, task) not in picked:
                continue
            _n, d, _p = picked[(track, task)]
            eps = d["episode_details"]
            ordn = sum(1 for e in eps if ordered_at(e, 1500))
            env = sum(1 for e in eps if e.get("success"))
            both_but_grip = 0
            no_s2 = 0
            no_s1 = 0
            for e in eps:
                s1, s2 = e.get("s1_step"), e.get("s2_step")
                g = e.get("success")
                if s1 is None:
                    no_s1 += 1
                elif s2 is None:
                    no_s2 += 1
                elif not g:
                    both_but_grip += 1
            print(f"| {task.replace('_2tasks','')} | {track.split('_')[0]} | {ordn} | {env} | **{both_but_grip}** | {no_s2} | {no_s1} |")
            detail[f"{track}/{task}"] = {"ordered": ordn, "env": env, "both_but_gripper_closed": both_but_grip,
                                         "s2_missing": no_s2, "s1_missing": no_s1,
                                         "episodes": [{k: e.get(k) for k in
                                                       ("seed", "s1_step", "s2_step", "switch_step", "total_steps", "success")}
                                                      for e in eps]}

    if args.out:
        payload = {"cutoffs": CUTOFFS,
                   "aggregate": {k: dict(v) for k, v in agg.items()},
                   "interaction_detail": detail}
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
